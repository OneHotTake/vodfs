"""Test virtual filesystem tree building"""

import pytest
from plugin.tree import FSNode, NodeType, DirectoryNode, FileNode, VirtualTree


class TestFSNode:
    """Test FSNode base class"""

    def test_directory_node_creation(self):
        node = DirectoryNode("test")
        assert node.name == "test"
        assert node.is_directory()
        assert not node.is_file()
        assert len(node.children) == 0

    def test_file_node_creation(self):
        node = FileNode("test.mkv", "http://example.com/stream.mkv")
        assert node.name == "test.mkv"
        assert node.is_file()
        assert not node.is_directory()
        assert node.metadata["stream_url"] == "http://example.com/stream.mkv"

    def test_add_child(self):
        parent = DirectoryNode("parent")
        child = DirectoryNode("child")
        parent.add_child(child)
        assert len(parent.children) == 1
        assert parent.children[0] == child

    def test_find_child(self):
        parent = DirectoryNode("parent")
        child = DirectoryNode("child")
        parent.add_child(child)
        found = parent.find_child("child")
        assert found == child
        assert parent.find_child("notfound") is None


class TestDirectoryNode:
    """Test DirectoryNode specific functionality"""

    def test_add_directory(self):
        parent = DirectoryNode("parent")
        child = parent.add_directory("child")
        assert child.name == "child"
        assert child.is_directory()
        assert len(parent.children) == 1

    def test_add_directory_reuse_existing(self):
        parent = DirectoryNode("parent")
        child1 = parent.add_directory("child")
        child2 = parent.add_directory("child")
        assert child1 == child2
        assert len(parent.children) == 1

    def test_add_directory_conflict_with_file(self):
        parent = DirectoryNode("parent")
        parent.add_file("test.mkv", "http://example.com/stream.mkv")
        with pytest.raises(ValueError):
            parent.add_directory("test.mkv")

    def test_add_file(self):
        parent = DirectoryNode("parent")
        child = parent.add_file("test.mkv", "http://example.com/stream.mkv")
        assert child.name == "test.mkv"
        assert child.is_file()
        assert len(parent.children) == 1


class TestVirtualTree:
    """Test VirtualTree building and resolution"""

    def test_tree_building(self):
        tree = VirtualTree()
        tree.build()

        # Check top-level directories
        assert tree.root.find_child("Movies") is not None
        assert tree.root.find_child("Series") is not None

    def test_resolve_root(self):
        tree = VirtualTree()
        tree.build()
        node = tree.resolve_path("/")
        assert node == tree.root

    def test_resolve_top_level(self):
        tree = VirtualTree()
        tree.build()
        node = tree.resolve_path("/Movies")
        assert node is not None
        assert node.name == "Movies"
        assert node.is_directory()

    def test_resolve_nested_path(self):
        tree = VirtualTree()
        tree.build()

        # Add some structure
        movies = tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Test.mkv", "http://example.com/stream.mkv")

        # Resolve
        node = tree.resolve_path("/Movies/All/Test.mkv")
        assert node is not None
        assert node.name == "Test.mkv"
        assert node.is_file()

    def test_resolve_invalid_path(self):
        tree = VirtualTree()
        tree.build()
        node = tree.resolve_path("/Invalid/Path")
        assert node is None

    def test_get_movies_root(self):
        tree = VirtualTree()
        tree.build()
        movies = tree.get_movies_root()
        assert movies is not None
        assert movies.name == "Movies"

    def test_get_series_root(self):
        tree = VirtualTree()
        tree.build()
        series = tree.get_series_root()
        assert series is not None
        assert series.name == "Series"


class TestTreeStructure:
    """Test overall tree structure matches design"""

    def test_all_is_sibling_to_categories(self):
        """Verify 'All' is a sibling to categories, not a parent"""
        tree = VirtualTree()
        tree.build()

        movies = tree.get_movies_root()

        # Add 'All' directory
        all_dir = movies.add_directory("All")

        # Add category directories
        action_dir = movies.add_directory("Action")
        comedy_dir = movies.add_directory("Comedy")

        # Verify all are siblings
        assert len(movies.children) == 3
        assert all_dir in movies.children
        assert action_dir in movies.children
        assert comedy_dir in movies.children

        # Verify 'All' is not a parent of categories
        assert all_dir.find_child("Action") is None
        assert all_dir.find_child("Comedy") is None

    def test_movies_and_series_are_separate(self):
        """Verify Movies and Series are separate top-level directories"""
        tree = VirtualTree()
        tree.build()

        movies = tree.get_movies_root()
        series = tree.get_series_root()

        assert movies != series
        assert movies.find_child("Series") is None
        assert series.find_child("Movies") is None