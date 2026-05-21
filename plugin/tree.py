"""Virtual filesystem tree implementation"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any


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
    """Virtual filesystem tree builder"""

    # Default category directories
    DEFAULT_CATEGORIES = [
        "Action",
        "Comedy",
        "Drama",
        "Horror",
        "SciFi",
        "Documentary",
        "Thriller",
        "Romance",
        "Animation",
        "Fantasy"
    ]

    def __init__(self):
        self.root = DirectoryNode("")
        self._movies_root = None
        self._series_root = None
        self._movies_all = None
        self._series_all = None

    def build(self, categories=None):
        """Build the complete virtual tree"""
        # Create top-level directories
        self._movies_root = self.root.add_directory("Movies")
        self._series_root = self.root.add_directory("Series")

        # Create All directories as siblings to categories
        self._movies_all = self._movies_root.add_directory("All")
        self._series_all = self._series_root.add_directory("All")

        # Create category directories
        cats = categories or self.DEFAULT_CATEGORIES
        for category in cats:
            self._movies_root.add_directory(category)
            self._series_root.add_directory(category)

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

    def hydrate_from_dispatcharr(self, movies: list, series: list):
        """Populate tree with data from Dispatcharr"""
        # Hydrate movies
        for movie in movies:
            title = movie.get("title", "Unknown")
            movie_id = movie.get("id", 0)
            size = movie.get("sizeOnDisk", 0)
            genres = movie.get("genres", [])

            # Create stream URL
            stream_url = f"/api/v3/stream/movie/{movie_id}"

            # Add to All directory
            if self._movies_all:
                self._movies_all.add_file(f"{title}.mkv", stream_url, size)

            # Add to category directories
            for genre in genres:
                cat_dir = self._movies_root.find_child(genre.capitalize()) if self._movies_root else None
                if cat_dir and cat_dir.is_directory():
                    cat_dir.add_file(f"{title}.mkv", stream_url, size)  # type: ignore[arg-type]

        # Hydrate series
        for show in series:
            title = show.get("title", "Unknown")
            series_id = show.get("id", 0)
            genres = show.get("genres", [])

            # Create series directory
            if self._series_all:
                show_dir = self._series_all.add_directory(title)
                # Add placeholder for episodes (will be hydrated on demand)
                show_dir.metadata["series_id"] = series_id

    def hydrate_episodes(self, series_dir: 'DirectoryNode', episodes: list):
        """Populate series directory with season/episode structure"""
        seasons = {}

        for episode in episodes:
            season_num = episode.get("seasonNumber", 0)
            episode_num = episode.get("episodeNumber", 0)
            episode_title = episode.get("title", f"Episode {episode_num}")
            episode_id = episode.get("id", 0)
            size = episode.get("size", 0)

            season_key = f"S{season_num:02d}"
            if season_key not in seasons:
                seasons[season_key] = series_dir.add_directory(season_key)

            filename = f"{season_key}E{episode_num:02d} - {episode_title}.mkv"
            stream_url = f"/api/v3/stream/episode/{episode_id}"
            seasons[season_key].add_file(filename, stream_url, size)

        # Mark series as hydrated
        series_dir.metadata["hydrated"] = True