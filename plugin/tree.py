"""Virtual filesystem tree implementation with live DB queries"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict

try:
    from .integration import _get_dispatcharr_base_url, DispatcharrIntegrator
except ImportError:
    from integration import _get_dispatcharr_base_url, DispatcharrIntegrator

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Type of filesystem node"""
    DIRECTORY = "directory"
    FILE = "file"


@dataclass
class FSNode:
    """Virtual filesystem node"""
    name: str
    node_type: NodeType
    children: List['FSNode'] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    _children_map: dict = field(default_factory=dict, repr=False)

    def is_directory(self) -> bool:
        return self.node_type == NodeType.DIRECTORY

    def is_file(self) -> bool:
        return self.node_type == NodeType.FILE

    def find_child(self, name: str) -> Optional['FSNode']:
        """Find child by name - O(1) lookup"""
        return self._children_map.get(name)

    def add_child(self, child: 'FSNode'):
        """Add a child node - O(1)"""
        self.children.append(child)
        self._children_map[child.name] = child

    def get_file_size(self) -> int:
        """Get file size (from metadata)"""
        return self.metadata.get("size", 0)

    def get_content_type(self) -> str:
        """Get content type (from metadata)"""
        return self.metadata.get("content_type", "application/octet-stream")


@dataclass
class FileNode(FSNode):
    """File node in virtual filesystem"""
    def __init__(self, name: str, stream_url: str, size: int = 0, content_type: str = "application/octet-stream"):
        super().__init__(name, NodeType.FILE)
        self.metadata["stream_url"] = stream_url
        self.metadata["size"] = size
        self.metadata["content_type"] = content_type


@dataclass
class DirectoryNode(FSNode):
    """Directory node in virtual filesystem"""
    def __init__(self, name: str):
        super().__init__(name, NodeType.DIRECTORY)

    def add_directory(self, name: str) -> 'DirectoryNode':
        """Add or get existing directory"""
        existing = self.find_child(name)
        if existing:
            if not existing.is_directory():
                raise ValueError(f"'{name}' exists but is not a directory")
            return existing  # type: ignore[return-value]

        new_dir = DirectoryNode(name)
        self.add_child(new_dir)
        return new_dir

    def add_file(self, name: str, stream_url: str, size: int = 0, content_type: str = "application/octet-stream") -> FileNode:
        """Add file to directory"""
        new_file = FileNode(name, stream_url, size, content_type)
        self.add_child(new_file)
        return new_file


class VirtualTree:
    """Virtual filesystem tree with live DB queries (no manifest caching)"""

    def __init__(self):
        self.root = DirectoryNode("")
        self._movies_root = None
        self._series_root = None
        self._movies_all = None
        self._series_all = None

    def build(self):
        """Build the complete virtual tree structure"""
        self._movies_root = self.root.add_directory("Movies")
        self._series_root = self.root.add_directory("Series")
        self._movies_all = self._movies_root.add_directory("All")
        self._series_all = self._series_root.add_directory("All")

    def resolve_path_with_db(self, path: str) -> Optional[FSNode]:
        """Resolve path with on-demand directory creation"""
        if not path or path == "/":
            return self.root

        components = [c for c in path.split("/") if c]

        if not components:
            return self.root

        # Root level: Movies, Series
        if len(components) == 1:
            if components[0] in ["Movies", "Series"]:
                if components[0] == "Movies":
                    if not self._movies_root:
                        self._movies_root = self.root.add_directory("Movies")
                        self._movies_all = self._movies_root.add_directory("All")
                    return self._movies_root
                else:
                    if not self._series_root:
                        self._series_root = self.root.add_directory("Series")
                        self._series_all = self._series_root.add_directory("All")
                    return self._series_root

        # Movies path: /Movies/All/ or /Movies/{Category}/
        if len(components) >= 2 and components[0] == "Movies":
            return self._resolve_movies_path(components[1:])

        # Series path: /Series/All/{Show}/ or /Series/{Category}/{Show}/ or /Series/All/{Show}/S01/
        if len(components) >= 2 and components[0] == "Series":
            return self._resolve_series_path(components[1:])

        return None

    def _resolve_movies_path(self, components: List[str]) -> Optional[FSNode]:
        """Resolve Movies path with individual movie folders"""
        # /Movies/All/
        if len(components) == 1 and components[0] == "All":
            if not self._movies_root:
                return None
            if not self._movies_all:
                self._movies_all = self._movies_root.add_directory("All")
            return self._movies_all

        # /Movies/{Category}/
        if len(components) == 1:
            category = components[0]
            if not self._movies_root:
                return None
            cat_dir = self._movies_root.find_child(category)
            if not cat_dir:
                cat_dir = self._movies_root.add_directory(category)
            return cat_dir

        # /Movies/All/{MovieFolder}/ or /Movies/{Category}/{MovieFolder}/
        if len(components) == 2:
            movie_folder_name = components[1]
            parent = self._resolve_movies_path([components[0]])
            if not parent or not isinstance(parent, DirectoryNode):
                return None

            # Check if folder already exists
            existing = parent.find_child(movie_folder_name)
            if existing:
                return existing

            # Parse folder name: "Title (Year) {imdb-ttXXX} {tmdb-YYY}"
            # Extract title, year, imdb_id, tmdb_id
            import re
            folder_match = re.match(r'^(.+?)\s*\((\d{4})\)(?:\s*\{(?:imdb-tt\d+|tmdb-\d+)(?:\s+(?:imdb-tt\d+|tmdb-\d+))*\})?$', movie_folder_name)
            if folder_match:
                title, year = folder_match.groups()[:2]
                category = None if components[0] == "All" else components[0]
                movie_folder = self._resolve_movie_folder(title, int(year), None, category)
                if movie_folder:
                    parent.add_child(movie_folder)
                    return movie_folder

            return None

        # /Movies/All/{MovieFolder}/{Filename}
        if len(components) == 3:
            parent = self._resolve_movies_path(components[:2])
            if not parent or not isinstance(parent, DirectoryNode):
                return None

            filename = components[2]
            existing = parent.find_child(filename)
            if existing:
                return existing

            # Parse filename: "Title (Year) - Provider - StreamID - Quality {ids}.ext"
            import re
            # Split on ' - ' from the right: [Title (Year), Provider, StreamID, Quality {ids}.ext]
            parts = filename.rsplit(' - ', 3)
            if len(parts) < 3:
                return None

            provider = parts[1]
            stream_part = parts[2]
            stream_match = re.match(r'^(\d+)(?:\s*-\s*\S+)?\.\w+$', stream_part)
            if not stream_match:
                return None

            stream_id = stream_match.group(1)

            # Extract title and year from first part
            title_part = parts[0]
            prefix_match = re.match(r'^(.+?)\s*\((\d{4})\)', title_part)
            if not prefix_match:
                return None

            title = prefix_match.group(1)
            year = int(prefix_match.group(2))

            category = None if components[0] == "All" else components[0]
            file_node = self._resolve_movie_by_filename(title, year, stream_id, category)
            if file_node:
                parent.add_child(file_node)
                return file_node

            return None

        return None

    def _resolve_movie_folder(self, title: str, year: int, tmdb_id: str | None, category: str | None) -> Optional[DirectoryNode]:
        """Resolve a movie folder by querying DB and create with files"""
        try:
            from apps.vod.models import M3UMovieRelation
            from django.db.models import F, Q
        except ImportError:
            return None

        # Build query
        query = Q(movie__year=year)
        if tmdb_id:
            query &= Q(movie__tmdb_id=tmdb_id)
        else:
            # Try to match title in provider name
            query &= Q(movie__name__contains=title)

        relations = M3UMovieRelation.objects.filter(
            query,
            category__m3u_relations__enabled=True,
            category__m3u_relations__m3u_account=F("m3u_account"),
        ).select_related('movie', 'category', 'm3u_account').distinct()

        if category:
            relations = relations.filter(category__name=category)

        if not relations:
            return None

        # Create folder node
        base_url = _get_dispatcharr_base_url()
        integrator = DispatcharrIntegrator()
        movie = relations[0].movie
        tmdb_id_val = movie.tmdb_id if hasattr(movie, 'tmdb_id') else None
        imdb_id_val = movie.imdb_id if hasattr(movie, 'imdb_id') else None

        # Build folder name
        folder_name = integrator.build_folder_name(movie.name, movie.year, tmdb_id_val, imdb_id_val)
        movie_folder = DirectoryNode(folder_name)
        movie_folder.metadata["movie_uuid"] = str(movie.uuid)

        # Add file(s) to folder (one per stream)
        for rel in relations:
            stream_url = f"{base_url}/proxy/vod/movie/{movie.uuid}?stream_id={rel.stream_id}"
            size = (movie.duration_secs or 6000) * 250 * 1024

            provider_short = rel.m3u_account.name[:20] if rel.m3u_account else "Unknown"
            filename = integrator.build_filename(
                movie.name, movie.year, provider_short, rel.stream_id,
                rel.container_extension or "mkv", tmdb_id_val, imdb_id_val
            )

            file_node = FileNode(filename, stream_url, size, "video/x-matroska")
            movie_folder.add_child(file_node)

        return movie_folder

    def _resolve_movie_by_filename(self, title: str, year: int, stream_id: str, category: Optional[str] = None) -> Optional[FileNode]:
        """Resolve a movie file by title, year, and stream_id via DB lookup"""
        try:
            from apps.vod.models import M3UMovieRelation
            from django.db.models import F, Q
        except ImportError:
            return None

        base_url = _get_dispatcharr_base_url()
        integrator = DispatcharrIntegrator()

        # Build query
        query = Q(movie__year=year, stream_id=stream_id)
        if title:
            query &= Q(movie__name__contains=title)

        relations = M3UMovieRelation.objects.filter(
            query,
            category__m3u_relations__enabled=True,
            category__m3u_relations__m3u_account=F("m3u_account"),
        ).select_related('movie', 'm3u_account', 'category').distinct()

        if category:
            relations = relations.filter(category__name=category)

        for rel in relations:
            tmdb_id_val = rel.movie.tmdb_id if hasattr(rel.movie, 'tmdb_id') else None

            filename = integrator.build_filename(
                rel.movie.name, rel.movie.year, "", rel.stream_id,
                rel.container_extension or "mkv", tmdb_id_val
            )

            stream_url = f"{base_url}/proxy/vod/movie/{rel.movie.uuid}?stream_id={rel.stream_id}"
            size = (rel.movie.duration_secs or 6000) * 250 * 1024
            return FileNode(filename, stream_url, size, "video/x-matroska")

        return None

    def _resolve_series_path(self, components: List[str]) -> Optional[FSNode]:
        """Resolve Series path"""
        # /Series/All/
        if len(components) == 1 and components[0] == "All":
            if not self._series_root:
                return None
            if not self._series_all:
                self._series_all = self._series_root.add_directory("All")
            return self._series_all

        # /Series/{Category}/
        if len(components) == 1:
            category = components[0]
            if not self._series_root:
                return None
            cat_dir = self._series_root.find_child(category)
            if not cat_dir:
                cat_dir = self._series_root.add_directory(category)
            return cat_dir

        # /Series/All/{Show Name}/ or /Series/{Category}/{Show Name}/
        if len(components) == 2:
            show_name = components[1]
            parent = self._resolve_series_path([components[0]])
            if not parent or not isinstance(parent, DirectoryNode):
                return None

            show_dir = parent.find_child(show_name)
            if not show_dir:
                # Look up series in DB by name (with year handling)
                series_obj = self._find_series_by_display_name(show_name)
                if series_obj:
                    show_dir = parent.add_directory(show_name)
                    show_dir.metadata["series_uuid"] = str(series_obj.uuid)

            return show_dir

        # /Series/All/{Show}/S01/ (season directory)
        if len(components) == 3:
            parent = self._resolve_series_path(components[:2])
            if not parent or not isinstance(parent, DirectoryNode):
                return None

            season_name = components[2]
            season_dir = parent.find_child(season_name)
            if not season_dir:
                season_dir = parent.add_directory(season_name)

            return season_dir

        # /Series/All/{Show}/S01/{episode file}
        if len(components) >= 4:
            parent = self._resolve_series_path(components[:3])
            if not parent or not isinstance(parent, DirectoryNode):
                return None

            show_name = components[1]
            season_name = components[2]
            filename = components[-1]
            existing = parent.find_child(filename)
            if existing:
                return existing
            category = components[0]
            file_node = self._resolve_episode_by_filename(category, show_name, season_name, filename)
            if file_node:
                parent.add_child(file_node)
                return file_node
            return None

        return None

    def _find_series_by_display_name(self, display_name: str):
        """Find a Series object by its display name (handles 'Name (Year)' format)"""
        try:
            from apps.vod.models import Series
        except ImportError:
            return None

        # Try exact name match first (name already contains year)
        series = Series.objects.filter(name=display_name).first()
        if series:
            return series

        # Try parsing "Name (Year)" format
        match = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', display_name)
        if match:
            name_part = match.group(1)
            year_part = int(match.group(2))
            series = Series.objects.filter(name=name_part, year=year_part).first()
            if series:
                return series

        return None

    def get_enabled_categories(self, content_type: str = 'movie') -> List[str]:
        """Get list of enabled category names from DB"""
        try:
            from apps.vod.models import VODCategory
        except ImportError:
            return []

        return list(
            VODCategory.objects.filter(
                category_type=content_type,
                m3u_relations__enabled=True
            ).values_list('name', flat=True).distinct().order_by('name')
        )

    def get_movies_from_db(self, category: Optional[str] = None) -> List[DirectoryNode]:
        """Get movie folders from DB (live query, only enabled categories)"""
        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            return []

        try:
            from apps.vod.models import M3UMovieRelation
            from django.db.models import F
        except ImportError:
            return []

        base_url = _get_dispatcharr_base_url()

        relations = M3UMovieRelation.objects.filter(
            category__m3u_relations__enabled=True,
            category__m3u_relations__m3u_account=F("m3u_account"),
        ).select_related('movie', 'category', 'm3u_account').distinct()

        if category:
            relations = relations.filter(category__name=category)

        # Group by movie UUID
        movies_map = {}
        for rel in relations:
            movie_uuid = str(rel.movie.uuid)
            if movie_uuid not in movies_map:
                movies_map[movie_uuid] = {
                    'movie': rel.movie,
                    'relations': []
                }
            movies_map[movie_uuid]['relations'].append(rel)

        result = []
        for movie_data in movies_map.values():
            movie = movie_data['movie']
            relations = movie_data['relations']

            tmdb_id_val = movie.tmdb_id if hasattr(movie, 'tmdb_id') else None
            folder_name = integrator.build_folder_name(movie.name, movie.year, tmdb_id_val)

            movie_folder = DirectoryNode(folder_name)
            movie_folder.metadata["movie_uuid"] = str(movie.uuid)

            # Add file(s) to folder (one per stream)
            for rel in relations:
                stream_url = f"{base_url}/proxy/vod/movie/{movie.uuid}?stream_id={rel.stream_id}"
                size = (movie.duration_secs or 6000) * 250 * 1024

                filename = integrator.build_filename(
                    movie.name, movie.year, "", rel.stream_id,
                    rel.container_extension or "mkv", tmdb_id_val
                )

                file_node = FileNode(filename, stream_url, size, "video/x-matroska")
                movie_folder.add_child(file_node)

            result.append(movie_folder)

        return result

    def _resolve_episode_by_filename(self, category: str, series_name: str, season_name: str, filename: str) -> Optional[FileNode]:
        """Resolve an episode file by series name, season, and stream_id"""
        try:
            from apps.vod.models import M3UEpisodeRelation, Series
            from django.db.models import F, Q
        except ImportError:
            return None

        # Parse folder name to get series name and year: "Breaking Bad (2008) {tmdb-1396}"
        import re
        folder_match = re.match(r'^(.+?)\s*\((\d{4})\)(?:\s*\{tmdb-(\d+)\})?$', series_name)
        if not folder_match:
            return None

        clean_series_name, year, tmdb_id = folder_match.groups()

        # Find series by name and year
        series_query = Q(name__contains=clean_series_name, year=int(year))
        if tmdb_id:
            series_query &= Q(tmdb_id=tmdb_id)

        series = Series.objects.filter(series_query).first()
        if not series:
            return None

        # Parse filename: "Breaking Bad (2008) - S01E01 - 12345.mkv"
        file_match = re.match(r'^.+\s*-\s*S(\d{2})E(\d{2})\s*-\s*(\d+)\.\w+$', filename)
        if not file_match:
            return None

        season_number = int(file_match.group(1))
        episode_number = int(file_match.group(2))
        stream_id = file_match.group(3)

        if season_name != f"S{season_number:02d}":
            return None

        relations = M3UEpisodeRelation.objects.filter(
            stream_id=stream_id,
            episode__series=series,
            episode__season_number=season_number,
            episode__episode_number=episode_number,
            series_relation__series=series,
            series_relation__category__m3u_relations__enabled=True,
            series_relation__category__m3u_relations__m3u_account=F("m3u_account"),
        ).select_related('episode', 'm3u_account', 'series_relation', 'series_relation__category').distinct()
        if category != "All":
            relations = relations.filter(series_relation__category__name=category)

        base_url = _get_dispatcharr_base_url()

        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()

        for rel in relations:
            tmdb_id_val = series.tmdb_id if hasattr(series, 'tmdb_id') else None
            imdb_id_val = series.imdb_id if hasattr(series, 'imdb_id') else None
            provider = rel.m3u_account.name[:20] if rel.m3u_account else "Unknown"

            # Parse filename to extract season/episode
            import re
            se_match = re.match(r'^.+\s*-\s*S(\d{2})E(\d{2})\s+-\s*(\d+)', filename)
            if not se_match:
                continue

            season_num = int(se_match.group(1))
            episode_num = int(se_match.group(2))
            stream_id = se_match.group(3)

            if season_num != season_number or episode_num != episode_number:
                continue

            if stream_id != rel.stream_id:
                continue

            stream_url = f"{base_url}/proxy/vod/episode/{rel.episode.uuid}?stream_id={rel.stream_id}"
            size = (rel.episode.duration_secs or 0) * 250 * 1024
            return FileNode(filename, stream_url, size, "video/x-matroska")

        return None

    def get_series_from_db(self, category: Optional[str] = None) -> List[DirectoryNode]:
        """Get series folders from DB (live query, only enabled categories)"""
        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            return []

        try:
            from apps.vod.models import M3USeriesRelation
            from django.db.models import F
        except ImportError:
            return []

        queryset = M3USeriesRelation.objects.filter(
            category__m3u_relations__enabled=True,
            category__m3u_relations__m3u_account=F("m3u_account"),
        ).select_related('series').order_by('series__name', 'series__year').distinct()

        if category:
            queryset = queryset.filter(category__name=category)

        result = []
        seen_series_ids = set()
        for relation in queryset:
            series = relation.series
            if series.id in seen_series_ids:
                continue
            seen_series_ids.add(series.id)

            tmdb_id_val = series.tmdb_id if hasattr(series, 'tmdb_id') else None
            imdb_id_val = series.imdb_id if hasattr(series, 'imdb_id') else None
            folder_name = integrator.build_folder_name(series.name, series.year, tmdb_id_val, imdb_id_val)

            dir_node = DirectoryNode(folder_name)
            dir_node.metadata["series_uuid"] = str(series.uuid)
            result.append(dir_node)

        return result

    def find_series_uuid_by_name(self, series_name: str) -> Optional[str]:
        """Find series UUID by display name (live DB query)"""
        series_obj = self._find_series_by_display_name(series_name)
        if series_obj:
            return str(series_obj.uuid)
        return None

    def get_seasons_from_db(self, series_uuid: str) -> List[DirectoryNode]:
        """Get seasons/episodes from DB with clean naming"""
        logger.debug("get_seasons_from_db called for UUID: %s", series_uuid)

        try:
            from apps.vod.models import Series
        except ImportError:
            return []

        try:
            series = Series.objects.get(uuid=series_uuid)
        except Series.DoesNotExist:
            logger.warning("Series %s not found", series_uuid)
            return []

        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            logger.warning("Django not available for get_seasons_from_db")
            return []

        episodes = integrator.get_series_episodes(series_uuid)
        logger.debug("get_seasons_from_db found %d episodes for UUID: %s", len(episodes), series_uuid)
        base_url = _get_dispatcharr_base_url()

        seasons = {}
        tmdb_id_val = series.tmdb_id if hasattr(series, 'tmdb_id') else None
        imdb_id_val = series.imdb_id if hasattr(series, 'imdb_id') else None

        for episode in episodes:
            season_key = f"S{episode['season_number']:02d}"
            if season_key not in seasons:
                seasons[season_key] = DirectoryNode(season_key)

            for stream in episode.get('streams', []):
                stream_url = stream['stream_url']
                ext = stream['extension'] or "mkv"
                size = stream.get('size', 0)
                stream_id = stream['stream_id']
                provider = stream['account_name'][:20] if stream['account_name'] else "Unknown"

                # Extract quality from series name if available
                _, quality = integrator.clean_movie_name(series.name)

                filename = integrator.build_episode_filename(
                    episode['name'], series.name, series.year,
                    episode['season_number'], episode['episode_number'],
                    ext, tmdb_id_val, imdb_id_val
                )

                # Reformat: Title (Year) - S01E01 - Provider - StreamID - Quality {ids}
                clean_series = integrator.clean_movie_name(series.name)[0]
                season_key_ep = f"S{episode['season_number']:02d}"
                episode_key = f"{season_key_ep}E{episode['episode_number']:02d}"

                ids = []
                if imdb_id_val:
                    ids.append(f'imdb-{imdb_id_val}')
                if tmdb_id_val:
                    ids.append(f'tmdb-{tmdb_id_val}')

                id_str = f" {{{' '.join(ids)}}}" if ids else ""
                quality_str = f" - {quality}" if quality else ""

                filename = f"{clean_series} ({series.year}) - {episode_key} - {provider} - {stream_id}{quality_str}{id_str}.{ext}"

                file_node = FileNode(filename, stream_url, size, "video/x-matroska")
                seasons[season_key].add_child(file_node)

        return list(seasons.values())
