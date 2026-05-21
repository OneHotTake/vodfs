"""Test Celery background tasks"""

import pytest
from unittest.mock import Mock, patch
from plugin.celery_worker import hydrate_movies, hydrate_series, hydrate_episodes


class TestCeleryHydrateMovies:
    """Test movie hydration task"""

    def test_hydrate_movies_success(self):
        """Test successful movie hydration"""
        tree_data = {
            "movies_all": [],
            "movies_action": [],
            "movies_comedy": []
        }

        movies = [
            {"id": 1, "title": "Action Movie", "sizeOnDisk": 1000, "genres": ["action"]},
            {"id": 2, "title": "Comedy Movie", "sizeOnDisk": 2000, "genres": ["comedy"]}
        ]

        result = hydrate_movies.run(tree_data, movies)

        assert result["status"] == "success"
        assert result["hydrated"] == 2
        assert len(tree_data["movies_all"]) == 2
        assert len(tree_data["movies_action"]) == 1
        assert len(tree_data["movies_comedy"]) == 1

    def test_hydrate_movies_no_genres(self):
        """Test movie hydration with no genres"""
        tree_data = {"movies_all": []}

        movies = [
            {"id": 1, "title": "Movie", "sizeOnDisk": 1000, "genres": []}
        ]

        result = hydrate_movies.run(tree_data, movies)

        assert result["status"] == "success"
        assert len(tree_data["movies_all"]) == 1

    def test_hydrate_movies_empty_list(self):
        """Test movie hydration with empty list"""
        tree_data = {"movies_all": []}

        result = hydrate_movies(tree_data, [])

        assert result["status"] == "success"
        assert result["hydrated"] == 0


class TestCeleryHydrateSeries:
    """Test series hydration task"""

    def test_hydrate_series_success(self):
        """Test successful series hydration"""
        tree_data = {
            "series_all": [],
            "series_drama": []
        }

        series = [
            {"id": 1, "title": "Drama Show", "genres": ["drama"]},
            {"id": 2, "title": "Another Show", "genres": []}
        ]

        result = hydrate_series(tree_data, series)

        assert result["status"] == "success"
        assert result["hydrated"] == 2
        assert len(tree_data["series_all"]) == 2
        assert len(tree_data["series_drama"]) == 1

    def test_hydrate_series_marks_unhydrated(self):
        """Test series marked as not hydrated"""
        tree_data = {"series_all": []}

        series = [{"id": 1, "title": "Show", "genres": []}]

        hydrate_series(tree_data, series)

        assert tree_data["series_all"][0]["hydrated"] is False


class TestCeleryHydrateEpisodes:
    """Test episode hydration task"""

    def test_hydrate_episodes_success(self):
        """Test successful episode hydration"""
        episodes = [
            {"id": 1, "seasonNumber": 1, "episodeNumber": 1, "title": "Pilot", "size": 500000},
            {"id": 2, "seasonNumber": 1, "episodeNumber": 2, "title": "Episode 2", "size": 600000},
            {"id": 3, "seasonNumber": 2, "episodeNumber": 1, "title": "Season 2 Premiere", "size": 700000}
        ]

        result = hydrate_episodes(1, episodes)

        assert result["status"] == "success"
        assert result["hydrated"] == 3
        assert "S01" in result["seasons"]
        assert "S02" in result["seasons"]
        assert len(result["seasons"]["S01"]) == 2
        assert len(result["seasons"]["S02"]) == 1

    def test_hydrate_episodes_empty(self):
        """Test episode hydration with empty list"""
        result = hydrate_episodes(1, [])

        assert result["status"] == "success"
        assert result["hydrated"] == 0
        assert result["seasons"] == {}

    def test_episode_filename_format(self):
        """Test episode filename format"""
        episodes = [
            {"id": 1, "seasonNumber": 1, "episodeNumber": 5, "title": "Test", "size": 100}
        ]

        result = hydrate_episodes(1, episodes)

        expected_name = "S01E05 - Test.mkv"
        assert result["seasons"]["S01"][0]["name"] == expected_name