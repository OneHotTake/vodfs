"""Unit tests for the Plex-correct naming/parsing helpers in integration.py.

These are pure functions (no DB), so the suite runs in milliseconds. They guard
the highest-risk surface in VODFS: every Plex/scraper match depends on how a noisy
provider VOD name is normalised into a clean title + year.
"""
from types import SimpleNamespace

import pytest

import integration
from integration import (
    parse_title,
    format_external_ids,
    sanitize_filename,
    estimate_size,
    episode_display_title,
    _strip_inline_quality,
    DispatcharrIntegrator,
)


# --- parse_title: year extraction + junk truncation -----------------------------

def test_truncates_at_first_parenthesised_year_and_strips_quality():
    # The motivating case: provider duplicates the year and appends cast credits.
    p = parse_title("Cool Hand Luke 4K (1967) PAUL NEWMAN (1967)")
    assert p["title"] == "Cool Hand Luke"
    assert p["year"] == 1967


def test_bare_year_integral_to_title_is_preserved():
    # "2049" is part of the title; "(2017)" is the real release year.
    p = parse_title("Blade Runner 2049 (2017)")
    assert p["title"] == "Blade Runner 2049"
    assert p["year"] == 2017


def test_trailing_bare_year_without_parens_is_not_doubled():
    p = parse_title("Wicked: For Good - 2025")
    assert p["title"] == "Wicked: For Good"
    assert p["year"] == 2025


def test_title_that_is_only_a_year_keeps_year_as_title():
    p = parse_title("1992")
    assert p["title"] == "1992"
    assert p["year"] is None


def test_explicit_year_field_is_preferred_over_name():
    p = parse_title("Die Hard", year_field=1988)
    assert p["title"] == "Die Hard"
    assert p["year"] == 1988


def test_strips_language_and_quality_prefix_with_bracket_subs():
    p = parse_title("4K-EN - Deadpool  (2016) [MULTI-SUB]")
    assert p["title"] == "Deadpool"
    assert p["year"] == 2016
    assert p["language"] == "en"
    assert p["multi"] is True


def test_strips_leading_list_number_prefix():
    p = parse_title("117. Die Hard (1988)")
    assert p["title"] == "Die Hard"
    assert p["year"] == 1988


# --- inline quality stripping: must not eat real-word titles ---------------------

@pytest.mark.parametrize("raw, expected", [
    ("The 4K Max", "The Max"),          # 4K removed, MAX (real word) kept
    ("Movie 1080p HEVC", "Movie"),      # both format tokens removed
    ("Mad Max Fury Road", "Mad Max Fury Road"),  # nothing stripped
    ("BluRay Heist", "Heist"),
])
def test_strip_inline_quality(raw, expected):
    assert " ".join(_strip_inline_quality(raw).split()) == expected


def test_max_survives_full_parse():
    # Regression guard: "Max"/"HBO"/"Cam" are deliberately excluded from inline strip.
    assert parse_title("Mad Max: Fury Road (2015)")["title"] == "Mad Max: Fury Road"


# --- external IDs (one-per-brace, Plex requirement) -----------------------------

def test_format_external_ids_both():
    assert format_external_ids(76341, "tt1392190") == " {tmdb-76341} {imdb-tt1392190}"


def test_format_external_ids_adds_tt_prefix():
    assert format_external_ids(None, "1392190") == " {imdb-tt1392190}"


def test_format_external_ids_empty():
    assert format_external_ids(None, None) == ""


# --- filename sanitisation ------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("Mad Max: Fury Road", "Mad Max Fury Road"),   # colon is illegal on FS
    ("a/b\\c", "a b c"),
    ("name?*<>|", "name"),
    ("", "Unknown"),
])
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


# --- episode title extraction ---------------------------------------------------

def test_episode_display_title_from_sxxexx():
    name = "A+ - Berlin ER (2025) (DE) - S01E01 - Symptoms"
    assert episode_display_title(name) == "Symptoms"


def test_episode_display_title_empty_when_only_marker():
    assert episode_display_title("Show - S02E05") == ""


# --- size estimation ------------------------------------------------------------

def test_size_from_metadata_uses_db_bitrate():
    from integration import size_from_metadata
    cp = {"detailed_info": {"bitrate": 2546, "duration_secs": 6180}}
    assert size_from_metadata(cp, 6180) == 2546 * 125 * 6180   # kbps*1000/8*secs


def test_size_from_metadata_accepts_json_string():
    from integration import size_from_metadata
    import json
    cp = json.dumps({"detailed_info": {"bitrate": 1227, "duration_secs": 3600}})
    assert size_from_metadata(cp, 3600) == 1227 * 125 * 3600


def test_size_from_metadata_falls_back_to_estimate():
    from integration import size_from_metadata, estimate_size
    # no bitrate -> duration estimate
    assert size_from_metadata({"detailed_info": {}}, 1000) == estimate_size(1000)
    # absurd bitrate -> rejected, estimate
    assert size_from_metadata({"detailed_info": {"bitrate": 9_000_000}}, 1000) == estimate_size(1000)
    # junk custom_properties -> estimate
    assert size_from_metadata("not json", 1000) == estimate_size(1000)
    assert size_from_metadata(None, 1000) == estimate_size(1000)


def test_estimate_size_from_duration():
    assert estimate_size(100) == 100 * (2_000_000 // 8)


def test_estimate_size_fallback():
    assert estimate_size(None) == 2 * 1024 * 1024 * 1024


# --- DispatcharrIntegrator naming (uses lightweight fakes, no DB) ----------------

def test_movie_folder_name_full_pipeline():
    movie = SimpleNamespace(name="ES|Mad Max 4K: Fury Road (2015)",
                            year=2015, tmdb_id=76341, imdb_id="tt1392190")
    folder = DispatcharrIntegrator().movie_folder_name(movie)
    # Prefix stripped, 4K removed, Max kept, colon sanitised, ids one-per-brace.
    assert folder == "Mad Max Fury Road (2015) {tmdb-76341} {imdb-tt1392190}"


def test_folder_name_from_fields_matches_model_path():
    # The streamed-listing path builds names from raw .values() fields; it must
    # produce the same result as the model-object path.
    di = DispatcharrIntegrator()
    movie = SimpleNamespace(name="ES|Mad Max 4K: Fury Road (2015)",
                            year=2015, tmdb_id=76341, imdb_id="tt1392190")
    from_fields = di.folder_name_from_fields(movie.name, movie.year,
                                             movie.tmdb_id, movie.imdb_id)
    assert from_fields == di.movie_folder_name(movie)
    assert from_fields == "Mad Max Fury Road (2015) {tmdb-76341} {imdb-tt1392190}"


def test_movie_filename_includes_stream_id_and_ext():
    movie = SimpleNamespace(name="Heat (1995)", year=1995, tmdb_id=None, imdb_id=None)
    rel = SimpleNamespace(stream_id="9988", container_extension="mp4")
    fn = DispatcharrIntegrator().movie_filename(movie, rel)
    assert fn == "Heat (1995) - 9988.mp4"


def test_movie_filename_with_provider_label():
    movie = SimpleNamespace(name="Heat (1995)", year=1995, tmdb_id=None, imdb_id=None)
    rel = SimpleNamespace(stream_id="9988", container_extension=None)
    fn = DispatcharrIntegrator().movie_filename(movie, rel, provider_label="ProvA")
    assert fn == "Heat (1995) - ProvA - 9988.mkv"   # default ext mkv


def test_season_dir_name():
    assert DispatcharrIntegrator.season_dir_name(3) == "Season 03"
    assert DispatcharrIntegrator.season_dir_name("bad") == "Season 01"


def test_episode_filename():
    series = SimpleNamespace(name="Berlin ER (2025)", year=2025, tmdb_id=None, imdb_id=None)
    rel = SimpleNamespace(stream_id="42", container_extension="mkv")
    fn = DispatcharrIntegrator().episode_filename(
        series, 1, 1, "Berlin ER - S01E01 - Symptoms", rel)
    assert fn == "Berlin ER (2025) - S01E01 - Symptoms - 42.mkv"


# --- proxy URL building ---------------------------------------------------------

def test_get_proxy_url(monkeypatch):
    monkeypatch.setenv("VODFS_DISPATCHARR_BASE_URL", "http://host:9191")
    url = DispatcharrIntegrator().get_proxy_url("movie", "abc-uuid", "555")
    assert url == "http://host:9191/proxy/vod/movie/abc-uuid?stream_id=555"


def test_get_proxy_url_rejects_unknown_type():
    with pytest.raises(ValueError):
        DispatcharrIntegrator().get_proxy_url("trailer", "u", "1")


def test_base_url_falls_back_on_non_http_scheme(monkeypatch):
    monkeypatch.setenv("VODFS_DISPATCHARR_BASE_URL", "file:///etc/passwd")
    assert integration._get_dispatcharr_base_url() == integration._DEFAULT_BASE_URL
