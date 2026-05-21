"""Test multi-stream file handling"""

import pytest
from plugin.tree import VirtualTree


class TestMultiStreamFilenames:
    """Test multi-stream filename generation"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

    def test_single_stream_filename(self):
        """Test single stream filename format"""
        movies_all = self.tree.get_movies_all()
        assert movies_all is not None

        movies_all.add_file("Movie (2024) - Provider1-12345.mkv", "/api/v3/stream/movie/1", 1000)

        file_node = movies_all.find_child("Movie (2024) - Provider1-12345.mkv")
        assert file_node is not None
        assert file_node.metadata["stream_url"] == "/api/v3/stream/movie/1"

    def test_multiple_streams_same_movie(self):
        """Test multiple streams for same movie"""
        movies_all = self.tree.get_movies_all()
        assert movies_all is not None

        movies_all.add_file("Movie (2024) - Provider1-12345.mkv", "/api/v3/stream/movie/1", 1000)
        movies_all.add_file("Movie (2024) - Provider2-67890.mkv", "/api/v3/stream/movie/2", 2000)
        movies_all.add_file("Movie (2024) - Provider3-54321.mkv", "/api/v3/stream/movie/3", 3000)

        assert len(movies_all.children) == 3

        file1 = movies_all.find_child("Movie (2024) - Provider1-12345.mkv")
        file2 = movies_all.find_child("Movie (2024) - Provider2-67890.mkv")
        file3 = movies_all.find_child("Movie (2024) - Provider3-54321.mkv")

        assert file1 is not None
        assert file2 is not None
        assert file3 is not None

        assert file1.metadata["stream_url"] == "/api/v3/stream/movie/1"
        assert file2.metadata["stream_url"] == "/api/v3/stream/movie/2"
        assert file3.metadata["stream_url"] == "/api/v3/stream/movie/3"

    def test_no_deduplication(self):
        """Test that duplicate titles are not deduplicated"""
        movies_all = self.tree.get_movies_all()
        assert movies_all is not None

        # Add same movie from different providers
        movies_all.add_file("Inception (2010) - Xtream-123.mkv", "/stream/1", 5000)
        movies_all.add_file("Inception (2010) - IPTV-456.mkv", "/stream/2", 6000)

        # Both should exist
        assert len(movies_all.children) == 2

    def test_stream_url_uniqueness(self):
        """Test each stream has unique URL"""
        movies_all = self.tree.get_movies_all()
        assert movies_all is not None

        movies_all.add_file("Movie1 - P1-1.mkv", "/stream/1", 100)
        movies_all.add_file("Movie1 - P2-2.mkv", "/stream/2", 200)
        movies_all.add_file("Movie2 - P1-3.mkv", "/stream/3", 300)

        urls = [child.metadata["stream_url"] for child in movies_all.children]
        assert len(urls) == len(set(urls)), "Stream URLs should be unique"


class TestMultiStreamListing:
    """Test multi-stream directory listing"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

    def test_directory_shows_all_streams(self):
        """Test directory listing shows all streams"""
        movies_all = self.tree.get_movies_all()
        assert movies_all is not None

        # Add multiple streams
        movies_all.add_file("Movie (2024) - ProviderA-1.mkv", "/stream/a1", 1000)
        movies_all.add_file("Movie (2024) - ProviderB-2.mkv", "/stream/b2", 2000)
        movies_all.add_file("Other Movie (2023) - ProviderA-3.mkv", "/stream/a3", 3000)

        # All should be listed
        assert len(movies_all.children) == 3

        # Verify each file is accessible
        for child in movies_all.children:
            assert child.is_file()
            assert "stream_url" in child.metadata