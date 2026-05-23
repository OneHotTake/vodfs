"""Virtual filesystem tree implementation with lazy path resolution"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict
import logging

try:
    from .manifest import ManifestManager
    from .integration import _get_dispatcharr_base_url, DispatcharrIntegrator
except ImportError:
    from manifest import ManifestManager
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
    """Virtual filesystem tree with lazy path resolution"""

    def __init__(self, manifest_manager: Optional[ManifestManager] = None):
        self.root = DirectoryNode("")
        self._movies_root = None
        self._series_root = None
        self._movies_all = None
        self._series_all = None
        self._manifest_manager = manifest_manager or ManifestManager()

    def build(self):
        """Build the complete virtual tree structure"""
        self._movies_root = self.root.add_directory("Movies")
        self._series_root = self.root.add_directory("Series")
        self._movies_all = self._movies_root.add_directory("All")
        self._series_all = self._series_root.add_directory("All")
        self._populate_categories_from_manifest()

    def _populate_categories_from_manifest(self):
        """Populate category directories from manifest"""
        try:
            movie_categories = self._manifest_manager.get_categories('movies')
            for cat in movie_categories:
                self._movies_root.add_directory(cat)
            series_categories = self._manifest_manager.get_categories('series')
            for cat in series_categories:
                self._series_root.add_directory(cat)
            logger.info("Populated %d movie categories and %d series categories from manifest",
                       len(movie_categories), len(series_categories))
        except Exception as e:
            logger.warning("Failed to populate categories from manifest: %s", e)

    def resolve_path(self, path: str) -> Optional[FSNode]:
        """Resolve a filesystem path to a node"""
        if not path or path == "/":
            return self.root

        # Remove leading/trailing slashes and split
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

    def hydrate_from_dispatcharr(self, movies: list, series: list, integrator=None):
        """Populate tree with data from DispatcharrIntegrator"""
        # Hydrate movies
        for movie in movies:
            title = movie.get("name", "Unknown")
            year = movie.get("year", 0)
            uuid = movie.get("uuid", "")
            categories = movie.get("categories", [])
            streams = movie.get("streams", [])

            for stream in streams:
                stream_url = stream.get("stream_url", "")
                stream_id = stream.get("stream_id", "")
                account_name = stream.get("account_name", "Unknown")
                ext = stream.get("extension", "mkv")
                size = stream.get("size", 0)

                # Build filename using integrator if available
                if integrator:
                    filename = integrator.build_filename(title, year, account_name, stream_id, ext)
                else:
                    filename = f"{title} ({year}) - {account_name}-{stream_id}.{ext}"

                # Add to All directory
                if self._movies_all:
                    self._movies_all.add_file(filename, stream_url, size)

                # Add to each category this movie belongs to
                for category in categories:
                    if category and self._movies_root:
                        cat_dir = self._movies_root.add_directory(category)
                        cat_dir.add_file(filename, stream_url, size)  # type: ignore[arg-type]

        # Hydrate series
        for show in series:
            title = show.get("name", "Unknown")
            year = show.get("year", 0)
            uuid = show.get("uuid", "")
            categories = show.get("categories", [])
            providers = show.get("providers", [])

            # Create series directory in All
            if self._series_all:
                show_dir = self._series_all.add_directory(f"{title} ({year})")
                show_dir.metadata["series_uuid"] = uuid
                show_dir.metadata["hydrated"] = False

                # Store provider info for episode hydration
                show_dir.metadata["providers"] = providers

            # Add to each category this series belongs to
            for category in categories:
                if category and self._series_root:
                    cat_dir = self._series_root.add_directory(category)
                    cat_dir.add_directory(f"{title} ({year})")  # type: ignore[union-attr]

    def hydrate_episodes(self, series_dir: 'DirectoryNode', episodes: list):
        """Populate series directory with season/episode structure"""
        seasons = {}

        for episode in episodes:
            season_num = episode.get("season_number", 0)
            episode_num = episode.get("episode_number", 0)
            episode_title = episode.get("name", f"Episode {episode_num}")
            streams = episode.get("streams", [])

            season_key = f"S{season_num:02d}"
            if season_key not in seasons:
                seasons[season_key] = series_dir.add_directory(season_key)

            # Create file for each stream
            for stream in streams:
                stream_url = stream.get("stream_url", "")
                ext = stream.get("extension", "mkv")
                account = stream.get("account_name", "Unknown")
                size = stream.get("size", 0)
                filename = f"{season_key}E{episode_num:02d} - {episode_title} - {account}.{ext}"
                seasons[season_key].add_file(filename, stream_url, size)

        # Mark series as hydrated
        series_dir.metadata["hydrated"] = True

    def resolve_path_with_db(self, path: str) -> Optional[FSNode]:
        """Resolve path using manifest + targeted DB queries (lazy resolution)"""
        if not path or path == "/":
            return self.root

        # Remove leading/trailing slashes and split
        components = [c for c in path.split("/") if c]

        if not components:
            return self.root

        # Root level: Movies, Series
        if len(components) == 1:
            if components[0] in ["Movies", "Series"]:
                # Create root directories on demand
                if components[0] == "Movies":
                    if not self._movies_root:
                        self._movies_root = self.root.add_directory("Movies")
                        # Always create All directory
                        self._movies_all = self._movies_root.add_directory("All")
                    return self._movies_root
                else:  # Series
                    if not self._series_root:
                        self._series_root = self.root.add_directory("Series")
                        # Always create All directory
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
        """Resolve Movies path (lazy DB queries)"""
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
                # Create category directory
                cat_dir = self._movies_root.add_directory(category)
            return cat_dir

        # /Movies/All/{MovieFile} or /Movies/{Category}/{MovieFile}
        if len(components) >= 2:
            # Return a placeholder file node for HEAD requests
            # The actual file metadata is resolved in httpfs.py
            filename = components[-1]
            file_node = FileNode(filename, "", 0, "video/x-matroska")
            file_node.metadata["placeholder"] = True
            return file_node

        return None

    def _resolve_series_path(self, components: List[str]) -> Optional[FSNode]:
        """Resolve Series path (lazy DB queries)"""
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

            # Find or create show directory
            show_dir = parent.find_child(show_name)
            if not show_dir:
                # Look up series in manifest
                series_skeleton = self._manifest_manager.get_series_skeleton()
                for series in series_skeleton:
                    series_name = series['name']
                    if f"({series['year']})" not in series['name']:
                        series_name = f"{series['name']} ({series['year']})"
                    if series_name == show_name:
                        show_dir = parent.add_directory(show_name)
                        show_dir.metadata["series_uuid"] = series["uuid"]
                        show_dir.metadata["hydrated"] = series["has_episodes"]
                        break

            return show_dir

        # /Series/All/{Show}/S01/ (season directory)
        if len(components) >= 3:
            parent = self._resolve_series_path(components[:2])
            if not parent or not isinstance(parent, DirectoryNode):
                return None

            season_name = components[2]
            season_dir = parent.find_child(season_name)
            if not season_dir:
                # Create season directory (episodes hydrated on access)
                season_dir = parent.add_directory(season_name)

            return season_dir

        return None

    def get_movies_from_db(self, category: Optional[str] = None) -> List[FileNode]:
        """Get movies from DB (lazy query)"""
        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            return []

        try:
            from apps.vod.models import Movie, M3UMovieRelation
            from apps.vod.models import VODCategory
            from django.db.models import Q
        except ImportError:
            return []

        base_url = _get_dispatcharr_base_url()

        # Query base
        queryset = Movie.objects.all().select_related('logo')

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
                # Skip if category filter active and this relation doesn't match
                if category and rel.category and rel.category.name != category:
                    continue

                stream_url = f"{base_url}/proxy/vod/movie/{movie.uuid}?stream_id={rel.stream_id}"

                # Build filename
                provider_short = rel.m3u_account.name[:20] if rel.m3u_account else "Unknown"
                filename = integrator.build_filename(
                    movie.name, movie.year, provider_short,
                    rel.stream_id, rel.container_extension or "mkv"
                )

                # Estimate size
                size = 0
                if movie.duration_secs:
                    size = movie.duration_secs * 250 * 1024
                else:
                    size = 6000 * 250 * 1024  # 100 min default

                file_node = FileNode(filename, stream_url, size, "video/x-matroska")
                result.append(file_node)

        return result

    def get_series_from_db(self, category: Optional[str] = None) -> List[DirectoryNode]:
        """Get series from DB (lazy query)"""
        series_skeleton = self._manifest_manager.get_series_skeleton()

        result = []
        for series in series_skeleton:
            # Filter by category if specified
            if category and category not in series.get('categories', []):
                continue

            # Name may already include year from manifest
            series_name = series['name']
            # Only add year if not already in name
            if f"({series['year']})" not in series['name']:
                series_name = f"{series['name']} ({series['year']})"
            dir_node = DirectoryNode(series_name)
            dir_node.metadata["series_uuid"] = series["uuid"]
            dir_node.metadata["hydrated"] = series["has_episodes"]
            result.append(dir_node)

        return result

    def get_series_dir_from_db(self, series_uuid: str) -> Optional[DirectoryNode]:
        """Get series directory from manifest (lazy)"""
        series_data = self._manifest_manager.find_series_by_uuid(series_uuid)
        if not series_data:
            return None

        series_name = series_data['name']
        if f"({series_data['year']})" not in series_data['name']:
            series_name = f"{series_data['name']} ({series_data['year']})"
        dir_node = DirectoryNode(series_name)
        dir_node.metadata["series_uuid"] = series_data["uuid"]
        dir_node.metadata["hydrated"] = series_data["has_episodes"]
        return dir_node

    def get_seasons_from_db(self, series_uuid: str) -> List[DirectoryNode]:
        """Get seasons/episodes from DB (lazy query)"""
        logger.info("get_seasons_from_db called for UUID: %s", series_uuid)
        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            logger.warning("Django not available for get_seasons_from_db")
            return []

        # Use existing get_series_episodes method
        episodes = integrator.get_series_episodes(series_uuid)
        logger.info("get_seasons_from_db found %d episodes for UUID: %s", len(episodes), series_uuid)
        base_url = _get_dispatcharr_base_url()

        seasons = {}
        for episode in episodes:
            season_key = f"S{episode['season_number']:02d}"
            if season_key not in seasons:
                seasons[season_key] = DirectoryNode(season_key)

            # Create file for each stream
            for stream in episode.get('streams', []):
                stream_url = stream['stream_url']
                ext = stream['extension'] or "mkv"
                provider = stream['account_name'][:20] if stream['account_name'] else "Unknown"
                size = stream.get('size', 0)

                filename = f"{season_key}E{episode['episode_number']:02d} - {episode['name']} - {provider}.{ext}"
                file_node = FileNode(filename, stream_url, size, "video/x-matroska")
                seasons[season_key].add_child(file_node)

        return list(seasons.values())