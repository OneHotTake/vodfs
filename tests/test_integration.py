"""Test Dispatcharr API client"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx
from plugin.dispatcharr import DispatcharrClient
from plugin.tree import VirtualTree


class TestDispatcharrClient:
    """Test Dispatcharr API client"""

    def test_client_initialization(self):
        """Test client initializes with base URL and API key"""
        client = DispatcharrClient("http://localhost:8080", "test-api-key")
        assert client.base_url == "http://localhost:8080"
        client._client.close()

    def test_get_movies_success(self):
        """Test successful movie fetch"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": 1, "title": "Test Movie", "sizeOnDisk": 1000, "genres": ["Action"]}
        ]
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.Client, 'get', return_value=mock_response):
            client = DispatcharrClient("http://localhost:8080", "test-key")
            movies = client.get_movies()
            assert len(movies) == 1
            assert movies[0]["title"] == "Test Movie"
            client._client.close()

    def test_get_movies_failure(self):
        """Test movie fetch handles errors gracefully"""
        with patch.object(httpx.Client, 'get', side_effect=httpx.HTTPError("Connection error")):
            client = DispatcharrClient("http://localhost:8080", "test-key")
            movies = client.get_movies()
            assert movies == []
            client._client.close()

    def test_get_series_success(self):
        """Test successful series fetch"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": 1, "title": "Test Series", "genres": ["Drama"]}
        ]
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.Client, 'get', return_value=mock_response):
            client = DispatcharrClient("http://localhost:8080", "test-key")
            series = client.get_series()
            assert len(series) == 1
            assert series[0]["title"] == "Test Series"
            client._client.close()

    def test_get_stream_url(self):
        """Test stream URL generation"""
        client = DispatcharrClient("http://localhost:8080", "test-key")
        url = client.get_stream_url(123, "movie")
        assert url == "http://localhost:8080/api/v3/stream/movie/123"
        client._client.close()


class TestTreeHydration:
    """Test tree hydration with Dispatcharr data"""

    def test_hydrate_movies(self):
        """Test hydrating movies from Dispatcharr data"""
        tree = VirtualTree()
        tree.build()

        movies_data = [
            {"id": 1, "title": "Test Movie", "sizeOnDisk": 1000, "genres": ["Action"]},
            {"id": 2, "title": "Another Movie", "sizeOnDisk": 2000, "genres": ["Comedy"]}
        ]

        tree.hydrate_from_dispatcharr(movies_data, [])

        # Check All directory
        movies_all = tree.get_movies_all()
        assert movies_all is not None
        assert len(movies_all.children) == 2

        # Check files exist
        test_file = movies_all.find_child("Test Movie.mkv")
        assert test_file is not None
        assert test_file.metadata["stream_url"] == "/api/v3/stream/movie/1"

    def test_hydrate_series(self):
        """Test hydrating series from Dispatcharr data"""
        tree = VirtualTree()
        tree.build()

        series_data = [
            {"id": 1, "title": "Test Series", "genres": ["Drama"]},
            {"id": 2, "title": "Another Series", "genres": ["Comedy"]}
        ]

        tree.hydrate_from_dispatcharr([], series_data)

        # Check All directory
        series_all = tree.get_series_all()
        assert series_all is not None
        assert len(series_all.children) == 2

        # Check series directories exist
        test_series = series_all.find_child("Test Series")
        assert test_series is not None
        assert test_series.metadata["series_id"] == 1

    def test_hydrate_with_genres(self):
        """Test movies are added to genre categories"""
        tree = VirtualTree()
        tree.build()

        movies_data = [
            {"id": 1, "title": "Action Movie", "sizeOnDisk": 1000, "genres": ["Action", "Thriller"]}
        ]

        tree.hydrate_from_dispatcharr(movies_data, [])

        # Check Action category
        action_dir = tree.get_movies_root().find_child("Action")
        assert action_dir is not None
        assert len(action_dir.children) == 1

        # Check Thriller category
        thriller_dir = tree.get_movies_root().find_child("Thriller")
        assert thriller_dir is not None
        assert len(thriller_dir.children) == 1