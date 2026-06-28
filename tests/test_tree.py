"""Unit tests for the pure path-resolution regexes in tree.py.

File playback resolves a virtual path back to one provider stream by pulling the
trailing stream_id out of the filename, so these regexes are load-bearing.
"""
import pytest

import tree


@pytest.mark.parametrize("filename, expected", [
    ("Heat (1995) - 9988.mp4", "9988"),
    ("Show - S01E01 - Symptoms - ProvA - 42.mkv", "42"),
    ("Movie (2015) {tmdb-1} {imdb-tt2} - 7.mkv", "7"),
])
def test_streamid_regex_extracts_trailing_id(filename, expected):
    m = tree._STREAMID_RE.search(filename)
    assert m and m.group(1) == expected


@pytest.mark.parametrize("filename", [
    "no stream id here.mkv",
    "folder name (1999)",
])
def test_streamid_regex_no_match(filename):
    assert tree._STREAMID_RE.search(filename) is None


@pytest.mark.parametrize("name, expected", [
    ("Season 03", "03"),
    ("Season 3", "3"),
    ("season 12", "12"),
])
def test_season_regex(name, expected):
    m = tree._SEASON_RE.match(name)
    assert m and m.group(1) == expected


def test_season_regex_rejects_non_season():
    assert tree._SEASON_RE.match("Specials") is None


def test_tmdb_and_imdb_regexes():
    folder = "Cool Hand Luke (1967) {tmdb-76341} {imdb-tt0061811}"
    assert tree._TMDB_RE.search(folder).group(1) == "76341"
    assert tree._IMDB_RE.search(folder).group(1) == "tt0061811"
