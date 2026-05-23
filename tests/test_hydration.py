"""Test series episode hydration"""

import pytest
from plugin.tree import VirtualTree, DirectoryNode


class TestEpisodeHydration:
    """Test episode hydration logic"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

    def test_hydrate_episodes_creates_seasons(self):
        """Test hydration creates season directories"""
        series_all = self.tree.get_series_all()
        assert series_all is not None

        show_dir = series_all.add_directory("Test Show")
        show_dir.metadata["series_id"] = 1

        episodes = [
            {"id": 1, "seasonNumber": 1, "episodeNumber": 1, "title": "Pilot", "size": 500000},
            {"id": 2, "seasonNumber": 1, "episodeNumber": 2, "title": "Episode 2", "size": 600000},
            {"id": 3, "seasonNumber": 2, "episodeNumber": 1, "title": "Season 2 Premiere", "size": 700000}
        ]

        self.tree.hydrate_episodes(show_dir, episodes)

        # Check season directories created
        s01 = show_dir.find_child("S01")
        s02 = show_dir.find_child("S02")

        assert s01 is not None
        assert s02 is not None
        assert s01.is_directory()
        assert s02.is_directory()

    def test_hydrate_episodes_creates_files(self):
        """Test hydration creates episode files"""
        series_all = self.tree.get_series_all()
        assert series_all is not None

        show_dir = series_all.add_directory("Test Show")
        show_dir.metadata["series_id"] = 1

        episodes = [
            {"id": 1, "seasonNumber": 1, "episodeNumber": 1, "title": "Pilot", "size": 500000}
        ]

        self.tree.hydrate_episodes(show_dir, episodes)

        s01 = show_dir.find_child("S01")
        assert s01 is not None

        episode_file = s01.find_child("S01E01 - Pilot.mkv")
        assert episode_file is not None
        assert episode_file.is_file()
        assert episode_file.metadata["stream_url"] == "/api/v3/stream/episode/1"
        assert episode_file.metadata["size"] == 500000

    def test_hydrate_episodes_marks_hydrated(self):
        """Test hydration marks directory as hydrated"""
        series_all = self.tree.get_series_all()
        assert series_all is not None

        show_dir = series_all.add_directory("Test Show")
        show_dir.metadata["series_id"] = 1
        show_dir.metadata["hydrated"] = False

        episodes = [
            {"id": 1, "seasonNumber": 1, "episodeNumber": 1, "title": "Pilot", "size": 500000}
        ]

        self.tree.hydrate_episodes(show_dir, episodes)

        assert show_dir.metadata["hydrated"] is True

    def test_hydrate_episodes_empty_list(self):
        """Test hydration with empty episode list"""
        series_all = self.tree.get_series_all()
        assert series_all is not None

        show_dir = series_all.add_directory("Test Show")
        show_dir.metadata["series_id"] = 1

        self.tree.hydrate_episodes(show_dir, [])

        # Should still be marked hydrated
        assert show_dir.metadata["hydrated"] is True
        # No season directories created
        assert len(show_dir.children) == 0


class TestEmptySeriesDetection:
    """Test detection of empty Series directories"""

    def test_detect_empty_series(self):
        """Test detecting empty series directory"""
        tree = VirtualTree()
        tree.build()

        series_all = tree.get_series_all()
        assert series_all is not None

        show_dir = series_all.add_directory("Empty Show")
        show_dir.metadata["series_id"] = 1
        show_dir.metadata["hydrated"] = False

        # Should be detected as empty
        assert len(show_dir.children) == 0
        assert show_dir.metadata.get("hydrated") is False

    def test_detect_hydrated_series(self):
        """Test detecting already hydrated series"""
        tree = VirtualTree()
        tree.build()

        series_all = tree.get_series_all()
        assert series_all is not None

        show_dir = series_all.add_directory("Hydrated Show")
        show_dir.metadata["series_id"] = 1
        show_dir.metadata["hydrated"] = True

        # Add some content
        s01 = show_dir.add_directory("S01")
        s01.add_file("S01E01 - Pilot.mkv", "/api/v3/stream/episode/1", 500000)

        # Should be detected as hydrated
        assert show_dir.metadata.get("hydrated") is True
        assert len(show_dir.children) > 0