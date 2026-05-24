"""Dispatcharr VOD integration"""

import os
import logging
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


def _get_dispatcharr_base_url() -> str:
    """Get Dispatcharr base URL from environment variable"""
    return os.environ.get("VODFS_DISPATCHARR_BASE_URL", "http://127.0.0.1:9191").rstrip("/")


class DispatcharrIntegrator:
    """Integration with Dispatcharr VOD models and tasks"""

    def is_available(self) -> bool:
        """Check if Django models are available"""
        return DJANGO_AVAILABLE

    def get_series_episodes(self, series_uuid: str) -> List[Dict[str, Any]]:
        """Get episodes for a series"""
        if not self.is_available():
            logger.warning("Django models not available")
            return []

        try:
            series = Series.objects.get(uuid=series_uuid)
        except Series.DoesNotExist:
            logger.warning("Series %s not found", series_uuid)
            return []

        base_url = _get_dispatcharr_base_url()
        episodes = list(series.episodes.all().order_by('season_number', 'episode_number'))
        episode_ids = [episode.id for episode in episodes]

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
            ).select_related('episode', 'm3u_account', 'series_relation', 'series_relation__category').distinct()

            for rel in relations:
                relations_by_episode[rel.episode_id].append(rel)

        result = []
        for episode in episodes:
            streams = []
            for rel in relations_by_episode.get(episode.id, []):
                # Use Dispatcharr proxy URL instead of direct provider URL
                stream_url = f"{base_url}/proxy/vod/episode/{episode.uuid}?stream_id={rel.stream_id}"

                # Estimate size from duration (if available)
                # Typical streaming bitrate: ~2 Mbps = 250 KB/s
                size = 0
                if episode.duration_secs:
                    size = episode.duration_secs * 250 * 1024  # bytes

                streams.append({
                    "stream_id": rel.stream_id,
                    "account_name": rel.m3u_account.name if rel.m3u_account else "Unknown",
                    "stream_url": stream_url,
                    "extension": rel.container_extension or "mkv",
                    "size": size
                })

            result.append({
                "uuid": str(episode.uuid),
                "name": episode.name,
                "season_number": episode.season_number,
                "episode_number": episode.episode_number,
                "air_date": episode.air_date,
                "streams": streams
            })

        return result

    def get_proxy_url(self, content_type: str, uuid: str, stream_id: str) -> str:
        """Generate Dispatcharr proxy URL for content"""
        base_url = _get_dispatcharr_base_url()
        if content_type == "movie":
            return f"{base_url}/proxy/vod/movie/{uuid}?stream_id={stream_id}"
        elif content_type == "episode":
            return f"{base_url}/proxy/vod/episode/{uuid}?stream_id={stream_id}"
        else:
            raise ValueError(f"Unknown content type: {content_type}")

    def clean_movie_name(self, name: str) -> str:
        """
        Strip quality/language prefix from IPTV provider name.
        Returns clean title only (no year, no quality prefix).

        Examples:
            "4K-EN - Deadpool (2016)" → "Deadpool"
            "4K-D+ | Dawn of the Planet of the Apes (2014)" → "Dawn of the Planet of the Apes"
            "HD FR - Matrix (1999)" → "Matrix"
            "3D IT - Avatar (2009)" → "Avatar"
        """
        # Split on ' - ' or ' | ' to remove quality prefix
        if ' - ' in name:
            title_part = name.split(' - ', 1)[1]
        elif ' | ' in name:
            title_part = name.split(' | ', 1)[1]
        else:
            title_part = name

        # Remove year from title (pattern: Title (YYYY))
        import re
        clean_name = re.sub(r'\s*\(\d{4}\)\s*$', '', title_part).strip()

        return clean_name

    def build_filename(self, title: str, year: int, provider_short: str, stream_id: str, ext: str, tmdb_id: str | None = None, imdb_id: str | None = None) -> str:
        """Build filename with clean title, external IDs, provider, and stream_id.

        Format: {CleanTitle} ({Year}) {imdb-XXX} {tmdb-XXX} - {ProviderShort} - {StreamID}.{ext}
        Note: Provider and Stream ID kept for playback resolution and human readability.
        Priority: IMDB preferred for series, TMDB preferred for movies, but both shown if available.
        """
        # Clean the title (strip quality prefix and year)
        clean_title = self.clean_movie_name(title)

        # Build base filename
        filename = f"{clean_title} ({year})"

        # Add external IDs (both IMDB and TMDB if available)
        # IMDB format: imdb-tt1234567
        # TMDB format: tmdb-123
        ids = []
        if imdb_id:
            # IMDB IDs usually have 'tt' prefix, ensure it's present
            imdb_val = imdb_id if imdb_id.startswith('tt') else f'tt{imdb_id}'
            ids.append(f'imdb-{imdb_val}')
        if tmdb_id:
            ids.append(f'tmdb-{tmdb_id}')

        if ids:
            filename += f" {{{' '.join(ids)}}}"

        # Add provider and stream ID (for playback resolution and human readability)
        filename += f" - {provider_short} - {stream_id}.{ext}"

        return filename

    def build_folder_name(self, title: str, year: int, tmdb_id: str | None = None, imdb_id: str | None = None) -> str:
        """Build folder name for movie or series with external IDs."""
        clean_title = self.clean_movie_name(title)
        folder_name = f"{clean_title} ({year})"

        # Add external IDs (both IMDB and TMDB if available)
        ids = []
        if imdb_id:
            imdb_val = imdb_id if imdb_id.startswith('tt') else f'tt{imdb_id}'
            ids.append(f'imdb-{imdb_val}')
        if tmdb_id:
            ids.append(f'tmdb-{tmdb_id}')

        if ids:
            folder_name += f" {{{' '.join(ids)}}}"

        return folder_name

    def build_episode_filename(self, episode_name: str, series_name: str, year: int,
                                season_number: int, episode_number: int, ext: str,
                                tmdb_id: str | None = None, imdb_id: str | None = None) -> str:
        """Build episode filename with clean series name and external IDs."""
        clean_series = self.clean_movie_name(series_name)
        season_key = f"S{season_number:02d}"
        episode_key = f"{season_key}E{episode_number:02d}"

        filename = f"{clean_series} ({year}) - {episode_key}"

        # Add external IDs (both IMDB and TMDB if available)
        ids = []
        if imdb_id:
            imdb_val = imdb_id if imdb_id.startswith('tt') else f'tt{imdb_id}'
            ids.append(f'imdb-{imdb_val}')
        if tmdb_id:
            ids.append(f'tmdb-{tmdb_id}')

        if ids:
            filename += f" {{{' '.join(ids)}}}"

        filename += f".{ext}"

        return filename
