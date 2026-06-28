"""Dispatcharr VOD integration: live DB access + Plex-correct naming.

The provider-supplied VOD names are noisy (quality/language prefixes, embedded
years, junk tags). `parse_title` normalises them into a clean title + year +
language hint so Plex's "Plex Movie"/"Plex TV Series" agents can match. External
IDs (tmdb/imdb) are emitted one-per-brace as Plex requires.
"""

import os
import re
import json
import logging
import threading
import urllib.request
from collections import defaultdict
from typing import List, Dict, Any, Optional

try:
    from apps.vod.models import Series, Episode
    from apps.vod.models import M3USeriesRelation, M3UEpisodeRelation
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    Series = Episode = None
    M3USeriesRelation = M3UEpisodeRelation = None


logger = logging.getLogger(__name__)


_DEFAULT_BASE_URL = "http://127.0.0.1:9191"


def _get_dispatcharr_base_url() -> str:
    """Get the Dispatcharr base URL from the environment.

    This is operator-configured and points at the trusted internal Dispatcharr
    instance (all proxy/probe requests go here). We only validate the scheme so a
    misconfigured value can't make urllib speak a non-HTTP scheme (file://, etc.).
    """
    url = os.environ.get("VODFS_DISPATCHARR_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    try:
        from urllib.parse import urlparse
        if urlparse(url).scheme not in ("http", "https"):
            logger.warning("Ignoring non-HTTP VODFS_DISPATCHARR_BASE_URL; using default")
            return _DEFAULT_BASE_URL
    except Exception:
        return _DEFAULT_BASE_URL
    return url


# --- Provider-name normalisation -------------------------------------------------

# Language codes that may appear in a provider prefix; mapped to ISO-639-1 later.
_LANG = {
    'EN', 'FR', 'DE', 'IT', 'ES', 'PT', 'NL', 'PL', 'RU', 'AR', 'TR', 'SV', 'SE',
    'NO', 'DA', 'DK', 'FI', 'EL', 'GR', 'RO', 'CS', 'CZ', 'HU', 'HE', 'HI', 'JA',
    'KO', 'ZH', 'UK', 'BG', 'HR', 'SR', 'MULTI', 'MULTISUB', 'VOSTFR', 'VOST',
    'VOSE', 'LAT', 'VO', 'DUAL',
}
# Quality / provider tags that may appear in a prefix (D+, A+ = Disney+/Apple TV+).
_QUAL = {
    '4K', 'UHD', 'HD', 'FHD', 'SD', 'HDR', 'HDR10', 'DV', '3D', 'HEVC', 'H265',
    'X265', 'H264', 'X264', '1080P', '720P', '2160P', '480P', 'HDTS', 'HDCAM',
    'CAM', 'TS', 'WEB', 'WEBDL', 'WEBRIP', 'BLURAY', 'BRRIP', 'DVDRIP', 'REMUX',
    'D+', 'A+', 'N', 'P+', 'HBO', 'MAX',
}
_LANG_MAP = {
    'MULTI': 'mul', 'MULTISUB': 'mul', 'VOST': 'mul', 'VOSTFR': 'fr', 'VOSE': 'es',
    'LAT': 'es', 'SE': 'sv', 'DK': 'da', 'GR': 'el', 'CZ': 'cs',
}
_YEAR_RE = re.compile(r'(?:^|[^\d])((?:19|20)\d{2})(?:[^\d]|$)')
# A *parenthesised/bracketed* year is the canonical release marker. Anything after
# the first one is provider junk (duplicate years, cast credits) we truncate away.
_PAREN_YEAR_RE = re.compile(r'[(\[]\s*((?:19|20)\d{2})\s*[)\]]')
# Resolution/codec/source tokens that providers wedge mid-title. Deliberately a
# *narrower* set than _QUAL: ambiguous real-word codes (MAX, HBO, CAM, WEB, TS, DV)
# are excluded so titles like "Mad Max" survive an inline strip.
_QUAL_INLINE = {
    '4K', 'UHD', 'FHD', 'QHD', 'HDR', 'HDR10', 'HEVC', 'H265', 'X265', 'H264',
    'X264', 'XVID', '1080P', '720P', '2160P', '480P', '4320P', 'HDTS', 'HDCAM',
    'WEBDL', 'WEBRIP', 'BRRIP', 'BLURAY', 'DVDRIP', 'REMUX',
}
_TAG_RE = re.compile(
    r'[\[(]\s*(?:MULTI[- ]?SUB|MULTISUB|SUB|DUAL|VOST(?:FR|E)?|HDTS|HDCAM|CAM|HDR|'
    r'HEVC|MAIN CARD|PRELIMS|EARLY PRELIMS|UNCUT|EXTENDED|REMASTERED|IMAX|3D|REPACK|'
    r'\d{3,4}P)\s*[\])]', re.IGNORECASE)
# Characters that are illegal/awkward in file names on common filesystems.
_ILLEGAL_FS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _looks_like_prefix(token: str) -> bool:
    """Is a pre-delimiter token a provider/quality/language code, not a real title?"""
    t = (token or '').strip()
    if not t or len(t) > 12:
        return False
    parts = [p for p in re.split(r'[-\s|]+', t.upper()) if p]
    if not parts:
        return False
    for p in parts:
        if p in _QUAL or p in _LANG:
            continue
        if re.fullmatch(r'[A-Z0-9]{1,4}\+?', p):  # short codes: 4K, EN, D+, N, P+
            continue
        return False
    return True


def _extract_lang(prefix: str) -> Optional[str]:
    for p in re.split(r'[-\s|]+', (prefix or '').upper()):
        if p in _LANG:
            return _LANG_MAP.get(p, p.lower()[:2])
    return None


_ISO1 = {
    'EN': 'en', 'FR': 'fr', 'DE': 'de', 'IT': 'it', 'ES': 'es', 'PT': 'pt',
    'NL': 'nl', 'PL': 'pl', 'RU': 'ru', 'AR': 'ar', 'TR': 'tr', 'SV': 'sv',
    'NO': 'no', 'DA': 'da', 'FI': 'fi', 'EL': 'el', 'RO': 'ro', 'CS': 'cs',
    'HU': 'hu', 'HE': 'he', 'HI': 'hi', 'JA': 'ja', 'KO': 'ko', 'ZH': 'zh',
    'UK': 'uk', 'HINDI': 'hi', 'ENG': 'en', 'SPA': 'es', 'FRE': 'fr', 'GER': 'de',
}


def _bracket_langs(name: str):
    """Extract (audio_langs, sub_langs, dubbed, multi) from [TAG] groups."""
    audio, subs = [], []
    dubbed = multi = False
    for grp in re.findall(r'\[([^\]]*)\]', name):
        up = grp.upper()
        toks = re.split(r'[-\s,/]+', up)
        if 'DUB' in toks:
            dubbed = True
        if 'MULTI' in up or 'DUAL' in up:
            multi = True
        is_sub = 'SUB' in up
        is_audio = 'AUDIO' in up or 'DUB' in toks or 'DUAL' in up
        for t in toks:
            iso = _ISO1.get(t)
            if not iso:
                continue
            if is_sub and iso not in subs:
                subs.append(iso)
            if is_audio and iso not in audio:
                audio.append(iso)
    return audio, subs, dubbed, multi


def parse_title(raw: str, year_field: Any = None) -> Dict[str, Any]:
    """Normalise a provider VOD name into {title, year, language, audio, subs, ...}."""
    name = re.sub(r'\s+', ' ', (raw or '').strip())
    language = None
    audio_langs, sub_langs, dubbed, multi = _bracket_langs(name)

    # 1. Strip a leading provider/quality/language prefix delimited by '|' or ' - '.
    if '|' in name:
        left, right = name.split('|', 1)
        if _looks_like_prefix(left):
            language = _extract_lang(left)
            name = right.strip()
    if ' - ' in name:
        left, right = name.split(' - ', 1)
        if _looks_like_prefix(left):
            language = language or _extract_lang(left)
            name = right.strip()

    # Strip a leading list-number prefix ("117. Die Hard" -> "Die Hard").
    name = re.sub(r'^\d{1,4}\.\s+', '', name)

    # 2. Year: prefer a sane year field, else extract from the name.
    has_year_field = isinstance(year_field, int) and 1900 <= year_field <= 2100
    year = year_field if has_year_field else None
    if ' ' not in name and name.count('.') >= 2:  # dotted release name
        name = name.replace('.', ' ')
    name_before_year = name
    paren = _PAREN_YEAR_RE.search(name)
    if paren:
        # Truncate at the first parenthesised year so "Cool Hand Luke 4K (1967)
        # PAUL NEWMAN (1967)" yields "Cool Hand Luke" rather than a folder name
        # scrapers can't match. A bare year that is part of the title (e.g.
        # "Blade Runner 2049") sits before the paren and is preserved.
        if year is None:
            year = int(paren.group(1))
        work = name[:paren.start()]
    else:
        matches = _YEAR_RE.findall(name)
        if year is None and matches:
            year = int(matches[-1])
        work = name
        if matches:  # remove the bare year token wherever it sits
            work = re.sub(r'[\(\[]?\b' + matches[-1] + r'\b[\)\]]?', ' ', name)

    work = _finalize(work)
    if not work:
        # The whole title was a year-like token (e.g. a movie named "1992").
        work = _finalize(name_before_year)
        if not has_year_field:
            year = None

    if language and language in _ISO1.values() and language not in audio_langs:
        audio_langs.insert(0, language)
    return {'title': work, 'year': year, 'language': language,
            'audio': audio_langs, 'subs': sub_langs, 'dubbed': dubbed, 'multi': multi}


def _strip_inline_quality(name: str) -> str:
    """Drop standalone resolution/codec/source tokens (4K, 1080p, HEVC, BluRay) that
    providers leave inside a title. Only unambiguous tokens in _QUAL_INLINE are
    removed, so real-word codes (Max, HBO, Cam) stay put."""
    return re.sub(
        r'\b[A-Za-z0-9]{2,7}\b',
        lambda m: ' ' if m.group(0).upper() in _QUAL_INLINE else m.group(0),
        name,
    )


def _finalize(name: str) -> str:
    """Strip junk tags, bracket groups, trailing country codes; collapse whitespace."""
    name = _TAG_RE.sub(' ', name)
    name = re.sub(r'\[[^\]]*\]', ' ', name)                  # all [tag] groups
    name = _strip_inline_quality(name)                       # mid-title 4K/1080p/...
    name = re.sub(r'\s*\((?:[A-Za-z]{2})\)\s*$', ' ', name)  # trailing country code
    name = re.sub(r'[\[(]\s*[\])]', ' ', name)               # empty brackets
    return re.sub(r'\s+', ' ', name).strip(' -._')


def sanitize_filename(name: str) -> str:
    """Make a tree component safe as a single path segment."""
    name = _ILLEGAL_FS.sub(' ', name or '')
    return re.sub(r'\s+', ' ', name).strip() or 'Unknown'


def format_external_ids(tmdb_id: Any = None, imdb_id: Any = None) -> str:
    """Return ' {tmdb-N} {imdb-ttX}' with each id in its own brace (Plex requirement)."""
    ids = []
    if tmdb_id:
        ids.append('{tmdb-%s}' % str(tmdb_id).strip())
    if imdb_id:
        v = str(imdb_id).strip()
        if v:
            v = v if v.startswith('tt') else 'tt' + v
            ids.append('{imdb-%s}' % v)
    return (' ' + ' '.join(ids)) if ids else ''


def _title_with_year(parsed: Dict[str, Any]) -> str:
    base = parsed['title']
    if parsed.get('year'):
        base += ' (%d)' % parsed['year']
    return base


def _ext(relation) -> str:
    return (getattr(relation, 'container_extension', None) or 'mkv').lstrip('.')


def _provider_suffix(provider_label: str, relation) -> str:
    """' - <provider> - <stream_id>' (or just ' - <stream_id>'); the stream_id
    makes the filename unique and lets the file resolve back to one provider stream."""
    sid = getattr(relation, 'stream_id', '')
    return ' - %s - %s' % (provider_label, sid) if provider_label else ' - %s' % sid


def episode_display_title(episode_name: str) -> str:
    """Extract just the episode title from a provider episode name.

    'A+ - Berlin ER (2025) (DE) - S01E01 - Symptoms' -> 'Symptoms'
    """
    if not episode_name:
        return ''
    m = re.search(r'[Ss]\d{1,3}[Ee]\d{1,4}\s*-\s*(.+)$', episode_name)
    if m:
        return sanitize_filename(m.group(1).strip())
    # Fall back to the trailing segment after the last ' - ' if it isn't SxxExx.
    parts = episode_name.rsplit(' - ', 1)
    tail = parts[-1].strip() if len(parts) > 1 else ''
    if tail and not re.match(r'^[Ss]\d', tail):
        return sanitize_filename(tail)
    return ''


class DispatcharrIntegrator:
    """Integration with Dispatcharr VOD models and the native VOD proxy."""

    def is_available(self) -> bool:
        return DJANGO_AVAILABLE

    # --- naming (Plex-correct) ---------------------------------------------------

    def parse(self, raw: str, year_field: Any = None) -> Dict[str, Any]:
        return parse_title(raw, year_field)

    @staticmethod
    def folder_name_from_fields(name, year=None, tmdb_id=None, imdb_id=None) -> str:
        """Plex-correct folder name from raw fields (no model instance needed).

        Lets streamed listings build names straight from a ``.values()`` row,
        avoiding the per-item model-object overhead that OOMs huge libraries.
        """
        p = parse_title(name, year)
        return sanitize_filename(_title_with_year(p) + format_external_ids(tmdb_id, imdb_id))

    def movie_folder_name(self, movie) -> str:
        return self.folder_name_from_fields(
            movie.name, getattr(movie, 'year', None),
            getattr(movie, 'tmdb_id', None), getattr(movie, 'imdb_id', None))

    def movie_filename(self, movie, relation, provider_label: str = '') -> str:
        p = parse_title(movie.name, getattr(movie, 'year', None))
        base = _title_with_year(p) + format_external_ids(
            getattr(movie, 'tmdb_id', None), getattr(movie, 'imdb_id', None))
        ext = _ext(relation)
        return sanitize_filename(base + _provider_suffix(provider_label, relation)) + '.' + ext

    def series_folder_name(self, series) -> str:
        return self.folder_name_from_fields(
            series.name, getattr(series, 'year', None),
            getattr(series, 'tmdb_id', None), getattr(series, 'imdb_id', None))

    @staticmethod
    def season_dir_name(season_number: int) -> str:
        try:
            return 'Season %02d' % int(season_number)
        except (TypeError, ValueError):
            return 'Season 01'

    def episode_filename(self, series, season_number: int, episode_number: int,
                         episode_name: str, relation, provider_label: str = '') -> str:
        p = parse_title(series.name, getattr(series, 'year', None))
        head = _title_with_year(p)
        se = 'S%02dE%02d' % (int(season_number or 0), int(episode_number or 0))
        ep_title = episode_display_title(episode_name)
        name = '%s - %s' % (head, se)
        if ep_title:
            name += ' - %s' % ep_title
        name += _provider_suffix(provider_label, relation)
        return sanitize_filename(name) + '.' + _ext(relation)

    # --- proxy URLs --------------------------------------------------------------

    def get_proxy_url(self, content_type: str, uuid: str, stream_id: str) -> str:
        """Native Dispatcharr VOD proxy URL. The proxy streams bytes with Range
        support and a correct Content-Length, so Plex can analyse/seek."""
        base_url = _get_dispatcharr_base_url()
        if content_type not in ("movie", "episode"):
            raise ValueError("Unknown content type: %s" % content_type)
        return "%s/proxy/vod/%s/%s?stream_id=%s" % (base_url, content_type, uuid, stream_id)

    # --- episodes ----------------------------------------------------------------

    def get_series_episodes(self, series_uuid: str) -> List[Dict[str, Any]]:
        """Return episodes (with provider streams) for a series."""
        if not self.is_available():
            logger.warning("Django models not available")
            return []

        try:
            series = Series.objects.get(uuid=series_uuid)
        except Series.DoesNotExist:
            logger.warning("Series %s not found", series_uuid)
            return []

        episodes = list(series.episodes.all().order_by('season_number', 'episode_number'))
        episode_ids = [e.id for e in episodes]

        try:
            from django.db.models import F
        except ImportError:
            F = None

        relations_by_episode = defaultdict(list)
        if episode_ids and F is not None:
            relations = M3UEpisodeRelation.objects.filter(
                episode_id__in=episode_ids,
                series_relation__series=series,
                series_relation__category__m3u_relations__enabled=True,
                series_relation__category__m3u_relations__m3u_account=F("m3u_account"),
                m3u_account__is_active=True,
            ).select_related('episode', 'm3u_account', 'series_relation',
                             'series_relation__category').distinct()
            for rel in relations:
                relations_by_episode[rel.episode_id].append(rel)

        result = []
        for episode in episodes:
            streams = []
            for rel in relations_by_episode.get(episode.id, []):
                stream_url = self.get_proxy_url("episode", str(episode.uuid), rel.stream_id)
                streams.append({
                    "stream_id": rel.stream_id,
                    "account_name": rel.m3u_account.name if rel.m3u_account else "Unknown",
                    "stream_url": stream_url,
                    "extension": rel.container_extension or "mkv",
                    "size": size_from_metadata(rel.custom_properties, episode.duration_secs),
                    "relation": rel,
                })
            result.append({
                "uuid": str(episode.uuid),
                "name": episode.name,
                "season_number": episode.season_number,
                "episode_number": episode.episode_number,
                "air_date": episode.air_date,
                "streams": streams,
            })
        return result


# Typical streaming bitrate (~2 Mbps). Used only as a fallback when the real
# Content-Length is unknown; the native proxy reports the true size on read.
_BYTES_PER_SEC = 2_000_000 // 8


def estimate_size(duration_secs: Optional[int]) -> int:
    if duration_secs and duration_secs > 0:
        return int(duration_secs) * _BYTES_PER_SEC
    return 2 * 1024 * 1024 * 1024  # 2 GiB fallback so clients never see a 0-byte file


def size_from_bitrate(custom_properties, duration_secs: Optional[int] = None) -> Optional[int]:
    """Exact size from Dispatcharr's stored provider bitrate, or None if unavailable.

    Xtream ``get_vod_info`` detail carries an average ``bitrate`` (kbps) + duration;
    where present (the title's detailed info has been fetched in Dispatcharr),
    bitrate*duration equals what a probe returns — exact, with no provider contact.
    Returns None when there's no usable bitrate so the caller can fall through to a
    probe (the real size is mandatory: an undersized estimate truncates the file and
    makes it unplayable)."""
    cp = custom_properties or {}
    if not isinstance(cp, dict):
        try:
            cp = json.loads(cp)
        except (ValueError, TypeError):
            cp = {}
    info = cp.get('detailed_info')
    if isinstance(info, dict):
        try:
            br = int(info.get('bitrate') or 0)
            dur = int(info.get('duration_secs') or duration_secs or 0)
        except (ValueError, TypeError):
            br = dur = 0
        if 100 <= br <= 200_000 and dur > 0:   # sane kbps; *1000/8 -> bytes
            return br * 125 * dur
    return None


def size_from_metadata(custom_properties, duration_secs: Optional[int] = None) -> int:
    """Bitrate-derived exact size if available, else the duration estimate. No probe —
    used for directory listings (cosmetic; rclone re-HEADs each file for the real size)."""
    return size_from_bitrate(custom_properties, duration_secs) or estimate_size(duration_secs)


# --- accurate size probing ------------------------------------------------------
# The real byte size is MANDATORY for playback: rclone caps reads at the size we
# report, so an undersized estimate truncates the container and Plex sees "no video
# or audio stream" (file unplayable). We therefore probe the native proxy for the
# true size (Content-Range) when Dispatcharr has no stored bitrate to derive it from.
# Probing is ON by default. To avoid one upstream request per title during a scan,
# either run Dispatcharr's VOD detailed-info refresh (populates bitrate -> exact size
# with no probe) or set a per-provider max-connections cap. Results are cached, and
# VODFS_PROBE_CONCURRENCY bounds concurrent probes. Set VODFS_PROBE_SIZE=false only if
# every title already has bitrate metadata.
_PROBE_ENABLED = os.environ.get("VODFS_PROBE_SIZE", "true").lower() == "true"
_size_cache: Dict[str, int] = {}
_size_cache_lock = threading.Lock()
_probe_sem = threading.Semaphore(int(os.environ.get("VODFS_PROBE_CONCURRENCY", "4")))


def probe_real_size(content_type: str, uuid: str, stream_id: str,
                    timeout: float = 10.0) -> Optional[int]:
    """Return the true byte size of a VOD item via the native proxy, or None."""
    if not _PROBE_ENABLED:
        return None
    key = "%s:%s" % (content_type, stream_id)
    with _size_cache_lock:
        if key in _size_cache:
            return _size_cache[key]
    url = "%s/proxy/vod/%s/%s?stream_id=%s" % (
        _get_dispatcharr_base_url(), content_type, uuid, stream_id)
    size = None
    try:
        with _probe_sem:
            req = urllib.request.Request(url, headers={"Range": "bytes=0-0"}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                cr = resp.headers.get("Content-Range")
                if cr and "/" in cr:
                    total = cr.rsplit("/", 1)[1].strip()
                    if total.isdigit():
                        size = int(total)
                if size is None:
                    cl = resp.headers.get("Content-Length")
                    if cl and cl.isdigit():
                        size = int(cl)
    except Exception as e:
        logger.debug("size probe failed for stream_id=%s: %s", stream_id, e)
    if size:
        with _size_cache_lock:
            _size_cache[key] = size
    return size
