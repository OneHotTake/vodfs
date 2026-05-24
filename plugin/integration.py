"""Dispatcharr VOD integration"""

import os
import logging
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
        episodes = series.episodes.all().order_by('season_number', 'episode_number')

        result = []
        for episode in episodes:
            # Get M3U relations for streaming URLs
            relations = M3UEpisodeRelation.objects.filter(episode=episode)

            streams = []
            for rel in relations:
                # Use Dispatcharr proxy URL instead of direct provider URL
                stream_url = f"{base_url}/proxy/vod/episode/{episode.uuid}"

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

    def build_filename(self, title: str, year: int, provider_short: str, stream_id: str, ext: str) -> str:
        """Build filename following design spec"""
        # Format: {Title} ({Year}) - {ProviderShortName}-{StreamID}.{ext}
        return f"{title} ({year}) - {provider_short}-{stream_id}.{ext}"