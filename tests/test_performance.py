"""Test large library performance"""

import pytest
import time
from plugin.tree import VirtualTree


class TestLargeLibraryPerformance:
    """Test performance with large datasets"""

    def test_path_resolution_10k_items(self):
        """Test path resolution with 10K+ items"""
        tree = VirtualTree()
        tree.build()

        movies_all = tree.get_movies_all()
        assert movies_all is not None

        # Add 10K movies
        start = time.time()
        for i in range(10000):
            movies_all.add_file(f"Movie_{i:05d}.mkv", f"/api/v3/stream/movie/{i}", 1000)
        build_time = time.time() - start

        # Resolve random paths
        start = time.time()
        for i in [0, 2500, 5000, 7500, 9999]:
            node = tree.resolve_path(f"/Movies/All/Movie_{i:05d}.mkv")
            assert node is not None
            assert node.name == f"Movie_{i:05d}.mkv"
        resolve_time = time.time() - start

        # Resolution should be fast (< 10ms for 5 lookups)
        assert resolve_time < 0.01, f"Path resolution took {resolve_time:.4f}s"

    def test_directory_listing_performance(self):
        """Test directory listing with many children"""
        tree = VirtualTree()
        tree.build()

        movies_all = tree.get_movies_all()
        assert movies_all is not None

        # Add 5K movies
        for i in range(5000):
            movies_all.add_file(f"Movie_{i:05d}.mkv", f"/api/v3/stream/movie/{i}", 1000)

        # Directory listing should be fast
        start = time.time()
        children = movies_all.children
        assert len(children) == 5000
        listing_time = time.time() - start

        # Should be instant (just returning list reference)
        assert listing_time < 0.001

    def test_find_child_performance(self):
        """Test O(1) child lookup"""
        tree = VirtualTree()
        tree.build()

        movies_all = tree.get_movies_all()
        assert movies_all is not None

        # Add 10K movies
        for i in range(10000):
            movies_all.add_file(f"Movie_{i:05d}.mkv", f"/api/v3/stream/movie/{i}", 1000)

        # Lookup last item (worst case for linear search)
        start = time.time()
        for _ in range(1000):
            node = movies_all.find_child("Movie_09999.mkv")
            assert node is not None
        lookup_time = time.time() - start

        # 1000 lookups should be fast with O(1) (< 10ms)
        assert lookup_time < 0.01, f"1000 lookups took {lookup_time:.4f}s"

    def test_deep_path_resolution(self):
        """Test path resolution at various depths"""
        tree = VirtualTree()
        tree.build()

        # Add deep structure
        movies = tree.get_movies_root()
        assert movies is not None

        cat = movies.add_directory("Action")
        subcat = cat.add_directory("SubCategory")
        subcat.add_file("DeepMovie.mkv", "/api/v3/stream/movie/1", 1000)

        # Resolve deep path
        start = time.time()
        for _ in range(1000):
            node = tree.resolve_path("/Movies/Action/SubCategory/DeepMovie.mkv")
            assert node is not None
        resolve_time = time.time() - start

        assert resolve_time < 0.01