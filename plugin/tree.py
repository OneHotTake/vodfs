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

    def is_directory(self) -> bool:
        return self.node_type == NodeType.DIRECTORY

    def is_file(self) -> bool:
        return self.node_type == NodeType.FILE

    def find_child(self, name: str) -> Optional['FSNode']:
        """Find child by name"""
        for child in self.children:
            if child.name == name:
                return child
        return None

    def add_child(self, child: 'FSNode'):
        """Add a child node"""
        self.children.append(child)

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
            return existing  # Type: ignore[return-value]  # We verified it's a directory

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

    def __init__(self):
        self.root = DirectoryNode("")
        self._movies_root = None
        self._series_root = None

    def build(self):
        """Build the complete virtual tree"""
        # Create top-level directories
        self._movies_root = self.root.add_directory("Movies")
        self._series_root = self.root.add_directory("Series")

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