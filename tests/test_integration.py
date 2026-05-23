"""Test Dispatcharr integration and tree hydration"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from plugin.integration import DispatcharrIntegrator
from plugin.tree import VirtualTree


class TestDispatcharrIntegrator:
    """Test Dispatcharr integration class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.integrator = DispatcharrIntegrator(auto_hydrate=True)

    def test_django_not_available(self):
        """Test behavior when Django models are not available"""
        with patch('plugin.integration.DJANGO_AVAILABLE', False):
            integrator = DispatcharrIntegrator()
            assert not integrator.is_available()
            assert integrator.get_all_movies() == []
            assert integrator.get_all_series() == []

    def test_get_proxy_url_movie(self):
        """Test proxy URL generation for movies"""
        url = self.integrator.get_proxy_url("movie", "abc123", "stream456")
        assert url == "/proxy/vod/movie/abc123?stream_id=stream456"

    def test_get_proxy_url_episode(self):
        """Test proxy URL generation for episodes"""
        url = self.integrator.get_proxy_url("episode", "def456", "stream789")
        assert url == "/proxy/vod/episode/def456?stream_id=stream789"

    def test_get_proxy_url_invalid_type(self):
        """Test proxy URL generation with invalid content type"""
        with pytest.raises(ValueError):
            self.integrator.get_proxy_url("invalid", "abc123", "stream456")

    def test_build_filename_single_stream(self):
        """Test filename building for single stream"""
        filename = self.integrator.build_filename(
            "Inception", 2010, "xtream", "12345", "mkv"
        )
        assert filename == "Inception (2010) - xtream-12345.mkv"

    def test_build_filename_multiple_streams(self):
        """Test filename building for multiple streams"""
        filenames = []
        providers = ["xtream", "iptv-org", "provider3"]
        stream_ids = ["12345", "67890", "54321"]

        for provider, stream_id in zip(providers, stream_ids):
            filename = self.integrator.build_filename(
                "Inception", 2010, provider, stream_id, "mkv"
            )
            filenames.append(filename)

        assert "Inception (2010) - xtream-12345.mkv" in filenames
        assert "Inception (2010) - iptv-org-67890.mkv" in filenames
        assert "Inception (2010) - provider3-54321.mkv" in filenames

    def test_cooldown_prevents_spam(self):
        """Test cooldown timer prevents hydration spam"""
        with patch('plugin.integration.DJANGO_AVAILABLE', True):
            with patch('plugin.integration.refresh_series_episodes') as mock_task:
                mock_series = Mock()
                mock_series.id = 1
                mock_series.name = "Test Series"

                mock_account = Mock()
                mock_account.id = 1
                mock_account.name = "Test Account"

                mock_rel = Mock()
                mock_rel.external_series_id = "ext123"

                with patch('plugin.integration.Series') as mock_series_model:
                    with patch('plugin.integration.M3UAccount') as mock_account_model:
                        with patch('plugin.integration.M3USeriesRelation') as mock_rel_model:
                            mock_series_model.objects.get.return_value = mock_series
                            mock_account_model.objects.filter.return_value.all.return_value = [mock_account]
                            mock_rel_model.objects.filter.return_value.first.return_value = mock_rel

                            result1 = self.integrator.trigger_hydration("series-uuid-1")
                            assert result1 is True

                            result2 = self.integrator.trigger_hydration("series-uuid-1")
                            assert result2 is False

    def test_auto_hydrate_disabled(self):
        """Test hydration is skipped when auto_hydrate is disabled"""
        integrator = DispatcharrIntegrator(auto_hydrate=False)

        with patch('plugin.integration.DJANGO_AVAILABLE', True):
            with patch('plugin.integration.refresh_series_episodes') as mock_task:
                result = integrator.trigger_hydration("series-uuid-1")
                assert result is False
                mock_task.delay.assert_not_called()


class TestTreeHydration:
    """Test tree hydration with real DispatcharrIntegrator data format"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()
        self.integrator = DispatcharrIntegrator()

    def test_hydrate_movies_with_streams(self):
        """Test hydrating movies with multiple streams"""
        movies = [
            {
                "uuid": "abc123",
                "name": "Test Movie",
                "year": 2024,
                "genre": "Action",
                "streams": [
                    {
                        "stream_id": "12345",
                        "account_name": "Provider1",
                        "stream_url": "/proxy/vod/movie/abc123?stream_id=12345",
                        "extension": "mkv"
                    },
                    {
                        "stream_id": "67890",
                        "account_name": "Provider2",
                        "stream_url": "/proxy/vod/movie/abc123?stream_id=67890",
                        "extension": "mkv"
                    }
                ]
            }
        ]

        self.tree.hydrate_from_dispatcharr(movies, [], self.integrator)

        movies_all = self.tree.get_movies_all()
        assert movies_all is not None
        assert len(movies_all.children) == 2

        # Check filenames match spec
        file1 = movies_all.find_child("Test Movie (2024) - Provider1-12345.mkv")
        file2 = movies_all.find_child("Test Movie (2024) - Provider2-67890.mkv")
        assert file1 is not None
        assert file2 is not None

    def test_hydrate_series_with_providers(self):
        """Test hydrating series with provider info"""
        series = [
            {
                "uuid": "series-uuid-1",
                "name": "Test Series",
                "year": 2023,
                "genre": "Drama",
                "episode_count": 0,
                "providers": [
                    {
                        "account_name": "Provider1",
                        "external_series_id": "ext123"
                    }
                ]
            }
        ]

        self.tree.hydrate_from_dispatcharr([], series, self.integrator)

        series_all = self.tree.get_series_all()
        assert series_all is not None
        assert len(series_all.children) == 1

        show_dir = series_all.find_child("Test Series (2023)")
        assert show_dir is not None
        assert show_dir.metadata["series_uuid"] == "series-uuid-1"
        assert show_dir.metadata["hydrated"] is False

    def test_hydrate_empty_movies(self):
        """Test hydration with no movies"""
        self.tree.hydrate_from_dispatcharr([], [], self.integrator)

        movies_all = self.tree.get_movies_all()
        assert movies_all is not None
        assert len(movies_all.children) == 0

    def test_hydrate_movie_without_genre(self):
        """Test movie without genre still appears in All"""
        movies = [
            {
                "uuid": "abc123",
                "name": "No Genre Movie",
                "year": 2024,
                "genre": "",
                "streams": [
                    {
                        "stream_id": "1",
                        "account_name": "Provider1",
                        "stream_url": "/proxy/vod/movie/abc123",
                        "extension": "mkv"
                    }
                ]
            }
        ]

        self.tree.hydrate_from_dispatcharr(movies, [], self.integrator)

        movies_all = self.tree.get_movies_all()
        assert movies_all is not None
        assert len(movies_all.children) == 1