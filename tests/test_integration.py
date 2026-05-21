"""Test Dispatcharr integration"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from plugin.integration import DispatcharrIntegrator


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

    @pytest.mark.skipif(not True, reason="Requires live Dispatcharr instance")
    def test_get_all_movies(self):
        """Test fetching all movies from Dispatcharr"""
        # This test requires a live Dispatcharr instance with data
        integrator = DispatcharrIntegrator()
        movies = integrator.get_all_movies()

        assert isinstance(movies, list)
        for movie in movies:
            assert "uuid" in movie
            assert "name" in movie
            assert "streams" in movie

    @pytest.mark.skipif(not True, reason="Requires live Dispatcharr instance")
    def test_get_all_series(self):
        """Test fetching all series from Dispatcharr"""
        # This test requires a live Dispatcharr instance with data
        integrator = DispatcharrIntegrator()
        series = integrator.get_all_series()

        assert isinstance(series, list)
        for s in series:
            assert "uuid" in s
            assert "name" in s
            assert "episode_count" in s

    @pytest.mark.skipif(not True, reason="Requires live Dispatcharr instance")
    def test_get_series_episodes(self):
        """Test fetching episodes for a series"""
        # This test requires a live Dispatcharr instance with data
        integrator = DispatcharrIntegrator()

        # Get first series
        series_list = integrator.get_all_series()
        if not series_list:
            pytest.skip("No series found in Dispatcharr")

        series_uuid = series_list[0]["uuid"]
        episodes = integrator.get_series_episodes(series_uuid)

        assert isinstance(episodes, list)
        for episode in episodes:
            assert "uuid" in episode
            assert "season_number" in episode
            assert "episode_number" in episode
            assert "streams" in episode

    @pytest.mark.skipif(not True, reason="Requires live Dispatcharr instance")
    def test_get_movie_categories(self):
        """Test fetching movie categories"""
        integrator = DispatcharrIntegrator()
        categories = integrator.get_movie_categories()

        assert isinstance(categories, list)
        for cat in categories:
            assert "name" in cat
            assert cat["category_type"] == "movie"

    @pytest.mark.skipif(not True, reason="Requires live Dispatcharr instance")
    def test_get_series_categories(self):
        """Test fetching series categories"""
        integrator = DispatcharrIntegrator()
        categories = integrator.get_series_categories()

        assert isinstance(categories, list)
        for cat in categories:
            assert "name" in cat
            assert cat["category_type"] == "series"


class TestProxyURLGeneration:
    """Test Dispatcharr proxy URL generation"""

    def test_get_proxy_url_movie(self):
        """Test proxy URL generation for movies"""
        integrator = DispatcharrIntegrator()
        url = integrator.get_proxy_url("movie", "abc123", "stream456")

        assert url == "/proxy/vod/movie/abc123?stream_id=stream456"

    def test_get_proxy_url_episode(self):
        """Test proxy URL generation for episodes"""
        integrator = DispatcharrIntegrator()
        url = integrator.get_proxy_url("episode", "def456", "stream789")

        assert url == "/proxy/vod/episode/def456?stream_id=stream789"

    def test_get_proxy_url_invalid_type(self):
        """Test proxy URL generation with invalid content type"""
        integrator = DispatcharrIntegrator()
        with pytest.raises(ValueError):
            integrator.get_proxy_url("invalid", "abc123", "stream456")


class TestFilenameBuilding:
    """Test filename building according to design spec"""

    def test_build_filename_single_stream(self):
        """Test filename building for single stream"""
        integrator = DispatcharrIntegrator()
        filename = integrator.build_filename(
            "Inception",
            2010,
            "xtream",
            "12345",
            "mkv"
        )

        assert filename == "Inception (2010) - xtream-12345.mkv"

    def test_build_filename_multiple_streams(self):
        """Test filename building for multiple streams"""
        integrator = DispatcharrIntegrator()

        filenames = []
        providers = ["xtream", "iptv-org", "provider3"]
        stream_ids = ["12345", "67890", "54321"]

        for provider, stream_id in zip(providers, stream_ids):
            filename = integrator.build_filename(
                "Inception",
                2010,
                provider,
                stream_id,
                "mkv"
            )
            filenames.append(filename)

        assert "Inception (2010) - xtream-12345.mkv" in filenames
        assert "Inception (2010) - iptv-org-67890.mkv" in filenames
        assert "Inception (2010) - provider3-54321.mkv" in filenames

    def test_build_filename_special_chars(self):
        """Test filename building with special characters"""
        integrator = DispatcharrIntegrator()
        filename = integrator.build_filename(
            "Movie: Special (2024)",
            2024,
            "provider",
            "stream1",
            "mkv"
        )

        # Special chars should be preserved (URL encoding happens elsewhere)
        assert "Movie: Special (2024)" in filename
        assert "- provider-stream1.mkv" in filename


class TestHydrationLogic:
    """Test episode hydration logic"""

    def test_cooldown_prevents_spam(self):
        """Test cooldown timer prevents hydration spam"""
        integrator = DispatcharrIntegrator(auto_hydrate=True)

        # First trigger should succeed (mocked)
        with patch('plugin.integration.DJANGO_AVAILABLE', True):
            with patch('plugin.integration.refresh_series_episodes') as mock_task:
                # Mock models
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

                            # First trigger
                            result1 = integrator.trigger_hydration("series-uuid-1")
                            assert result1 is True

                            # Immediate second trigger (should fail due to cooldown)
                            result2 = integrator.trigger_hydration("series-uuid-1")
                            assert result2 is False

    def test_auto_hydrate_disabled(self):
        """Test hydration is skipped when auto_hydrate is disabled"""
        integrator = DispatcharrIntegrator(auto_hydrate=False)

        with patch('plugin.integration.DJANGO_AVAILABLE', True):
            with patch('plugin.integration.refresh_series_episodes') as mock_task:
                result = integrator.trigger_hydration("series-uuid-1")
                assert result is False
                mock_task.delay.assert_not_called()

    @pytest.mark.skipif(not True, reason="Requires live Dispatcharr instance")
    def test_trigger_hydration_real(self):
        """Test triggering hydration with real Dispatcharr instance"""
        # This test requires a live Dispatcharr instance
        integrator = DispatcharrIntegrator(auto_hydrate=True)

        # Get a series with zero episodes
        series_list = integrator.get_all_series()
        target_series = None
        for series in series_list:
            if series["episode_count"] == 0:
                target_series = series
                break

        if not target_series:
            pytest.skip("No series with zero episodes found")

        # Trigger hydration
        result = integrator.trigger_hydration(target_series["uuid"])
        assert result is True

        # Verify task was enqueued (check Dispatcharr logs)