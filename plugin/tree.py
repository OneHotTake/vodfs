"""Virtual filesystem tree implementation with live DB queries"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict
import logging

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

    def resolve_path(self, path: str) -> Optional[FSNode]:
        """Resolve a filesystem path to a node"""
        if not path or path == "/":
            return self.root

        components = [c for c in path.split("/") if c]

        current = self.root
        for component in components:
            if not current.is_directory():
                return None

            current = current.find_child(component)
            if current is None:
                return None

        return current

    def get_movies_root(self) -> Optional[DirectoryNode]:
        """Get Movies root directory"""
        return self._movies_root

    def get_series_root(self) -> Optional[DirectoryNode]:
        """Get Series root directory"""
        return self._series_root

    def get_movies_all(self) -> Optional[DirectoryNode]:
        """Get Movies/All directory"""
        return self._movies_all

    def get_series_all(self) -> Optional[DirectoryNode]:
        """Get Series/All directory"""
        return self._series_all

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
        """Resolve Movies path"""
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

        # /Movies/All/{MovieFile} or /Movies/{Category}/{MovieFile}
        if len(components) >= 2:
            filename = components[-1]
            file_node = FileNode(filename, "", 0, "video/x-matroska")
            file_node.metadata["placeholder"] = True
            return file_node

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
                    show_dir.metadata["hydrated"] = series_obj.episodes.exists()

            return show_dir

        # /Series/All/{Show}/S01/ (season directory)
        if len(components) >= 3:
            parent = self._resolve_series_path(components[:2])
            if not parent or not isinstance(parent, DirectoryNode):
                return None

            season_name = components[2]
            season_dir = parent.find_child(season_name)
            if not season_dir:
                season_dir = parent.add_directory(season_name)

            return season_dir

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
        import re
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

    def get_movies_from_db(self, category: Optional[str] = None) -> List[FileNode]:
        """Get movies from DB (live query, only enabled categories)"""
        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            return []

        try:
            from apps.vod.models import Movie, M3UMovieRelation
        except ImportError:
            return []

        base_url = _get_dispatcharr_base_url()

        # Query base - only movies in ENABLED categories
        queryset = Movie.objects.filter(
            m3umovierelation__category__m3u_relations__enabled=True
        ).select_related('logo').distinct()

        # Filter by category if specified
        if category:
            queryset = queryset.filter(
                m3umovierelation__category__name=category
            ).distinct()

        logger.info("get_movies_from_db: querying %d movies (category=%s)", queryset.count(), category)
        result = []
        for movie in queryset:
            relations = M3UMovieRelation.objects.filter(movie=movie).select_related(
                'category', 'm3u_account'
            )

            for rel in relations:
                # Skip if category is not enabled for this M3U account
                if not rel.category or not rel.category.m3u_relations.filter(
                    m3u_account=rel.m3u_account, enabled=True
                ).exists():
                    continue

                # Skip if category filter active and this relation doesn't match
                if category and rel.category.name != category:
                    continue

                stream_url = f"{base_url}/proxy/vod/movie/{movie.uuid}?stream_id={rel.stream_id}"

                provider_short = rel.m3u_account.name[:20] if rel.m3u_account else "Unknown"
                filename = integrator.build_filename(
                    movie.name, movie.year, provider_short,
                    rel.stream_id, rel.container_extension or "mkv"
                )

                size = 0
                if movie.duration_secs:
                    size = movie.duration_secs * 250 * 1024
                else:
                    size = 6000 * 250 * 1024  # 100 min default

                file_node = FileNode(filename, stream_url, size, "video/x-matroska")
                result.append(file_node)

        return result

    def get_series_from_db(self, category: Optional[str] = None) -> List[DirectoryNode]:
        """Get series from DB (live query, only enabled categories)"""
        try:
            from apps.vod.models import Series, M3USeriesRelation
        except ImportError:
            return []

        # Build query: series that have relations in enabled categories
        queryset = Series.objects.filter(
            m3u_relations__category__m3u_relations__enabled=True
        ).distinct()

        if category:
            queryset = queryset.filter(
                m3u_relations__category__name=category
            ).distinct()

        result = []
        for series in queryset:
            # Get enabled categories for this series
            series_categories = list(
                M3USeriesRelation.objects.filter(series=series)
                .filter(category__m3u_relations__enabled=True)
                .values_list('category__name', flat=True)
                .distinct()
            )

            # If category filter specified, skip series not in that category
            if category and category not in series_categories:
                continue

            series_name = series.name
            if series.year and f"({series.year})" not in series.name:
                series_name = f"{series.name} ({series.year})"

            dir_node = DirectoryNode(series_name)
            dir_node.metadata["series_uuid"] = str(series.uuid)
            dir_node.metadata["hydrated"] = series.episodes.exists()
            result.append(dir_node)

        return result

    def find_series_uuid_by_name(self, series_name: str) -> Optional[str]:
        """Find series UUID by display name (live DB query)"""
        series_obj = self._find_series_by_display_name(series_name)
        if series_obj:
            return str(series_obj.uuid)
        return None

    def get_seasons_from_db(self, series_uuid: str) -> List[DirectoryNode]:
        """Get seasons/episodes from DB (live query)"""
        logger.info("get_seasons_from_db called for UUID: %s", series_uuid)
        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            logger.warning("Django not available for get_seasons_from_db")
            return []

        episodes = integrator.get_series_episodes(series_uuid)
        logger.info("get_seasons_from_db found %d episodes for UUID: %s", len(episodes), series_uuid)
        base_url = _get_dispatcharr_base_url()

        seasons = {}
        for episode in episodes:
            season_key = f"S{episode['season_number']:02d}"
            if season_key not in seasons:
                seasons[season_key] = DirectoryNode(season_key)

            for stream in episode.get('streams', []):
                stream_url = stream['stream_url']
                ext = stream['extension'] or "mkv"
                provider = stream['account_name'][:20] if stream['account_name'] else "Unknown"
                size = stream.get('size', 0)

                filename = f"{season_key}E{episode['episode_number']:02d} - {episode['name']} - {provider}.{ext}"
                file_node = FileNode(filename, stream_url, size, "video/x-matroska")
                seasons[season_key].add_child(file_node)

        return list(seasons.values())
