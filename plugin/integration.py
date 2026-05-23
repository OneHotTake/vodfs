"""Dispatcharr VOD integration"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from collections import defaultdict

# These imports will be available when running inside Dispatcharr
# We'll handle import errors gracefully during development
try:
    from apps.vod.models import Movie, Series, Episode, VODCategory
    from apps.vod.models import M3UMovieRelation, M3USeriesRelation, M3UEpisodeRelation
    from apps.m3u.models import M3UAccount
    from apps.vod.tasks import refresh_series_episodes
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    Movie = Series = Episode = VODCategory = None
    M3UAccount = M3UMovieRelation = M3USeriesRelation = M3UEpisodeRelation = None
    refresh_series_episodes = None


logger = logging.getLogger(__name__)


def _get_dispatcharr_base_url() -> str:
    """Get Dispatcharr base URL from environment variable"""
    return os.environ.get("VODFS_DISPATCHARR_BASE_URL", "http://127.0.0.1:9191").rstrip("/")


class DispatcharrIntegrator:
    """Integration with Dispatcharr VOD models and tasks"""

    def __init__(self, auto_hydrate: bool = True):
        self.auto_hydrate = auto_hydrate

    def is_available(self) -> bool:
        """Check if Django models are available"""
        return DJANGO_AVAILABLE

    def get_all_movies(self) -> List[Dict[str, Any]]:
        """Get all movies from Dispatcharr"""
        if not self.is_available():
            logger.warning("Django models not available")
            return []

        base_url = _get_dispatcharr_base_url()
        movies = Movie.objects.all().select_related('logo')

        result = []
        for movie in movies:
            # Get M3U relations for streaming URLs and categories
            relations = M3UMovieRelation.objects.filter(movie=movie).select_related('category')

            streams = []
            categories = []
            for rel in relations:
                # Use Dispatcharr proxy URL instead of direct provider URL
                stream_url = f"{base_url}/proxy/vod/movie/{movie.uuid}?stream_id={rel.stream_id}"
                # Estimate size from duration or use default
                # Most movies are 90-120 min, use 100 min (6000s) default at ~2 Mbps
                size = 0
                if movie.duration_secs:
                    size = movie.duration_secs * 250 * 1024  # bytes
                elif rel.custom_properties:
                    detailed = rel.custom_properties.get("detailed_info", {})
                    if detailed and "duration_secs" in detailed:
                        size = detailed["duration_secs"] * 250 * 1024
                    else:
                        size = 6000 * 250 * 1024  # 100 min default
                else:
                    size = 6000 * 250 * 1024  # 100 min default

                streams.append({
                    "stream_id": rel.stream_id,
                    "account_name": rel.m3u_account.name if rel.m3u_account else "Unknown",
                    "stream_url": stream_url,
                    "extension": rel.container_extension or "mkv",
                    "size": size
                })
                # Collect category names
                if rel.category:
                    categories.append(rel.category.name)

            result.append({
                "uuid": str(movie.uuid),
                "name": movie.name,
                "year": movie.year,
                "description": movie.description,
                "rating": movie.rating,
                "genre": movie.genre,
                "streams": streams,
                "categories": categories
            })

        return result

    def get_all_series(self) -> List[Dict[str, Any]]:
        """Get all series from Dispatcharr"""
        if not self.is_available():
            logger.warning("Django models not available")
            return []

        series_list = Series.objects.all().select_related('logo')

        result = []
        for series in series_list:
            # Get episode count
            episode_count = series.episodes.count()

            # Get M3U relations
            relations = M3USeriesRelation.objects.filter(series=series).select_related('category')

            providers = []
            categories = []
            for rel in relations:
                providers.append({
                    "account_name": rel.m3u_account.name if rel.m3u_account else "Unknown",
                    "external_series_id": rel.external_series_id
                })
                # Collect category names
                if rel.category:
                    categories.append(rel.category.name)

            result.append({
                "uuid": str(series.uuid),
                "name": series.name,
                "year": series.year,
                "description": series.description,
                "rating": series.rating,
                "genre": series.genre,
                "episode_count": episode_count,
                "providers": providers,
                "categories": categories
            })

        return result

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

    def get_movie_categories(self) -> List[Dict[str, Any]]:
        """Get all VOD categories for movies"""
        if not self.is_available():
            logger.warning("Django models not available")
            return []

        categories = VODCategory.objects.filter(category_type='movie')

        result = []
        for cat in categories:
            result.append({
                "name": cat.name,
                "category_type": cat.category_type
            })

        return result

    def get_series_categories(self) -> List[Dict[str, Any]]:
        """Get all VOD categories for series"""
        if not self.is_available():
            logger.warning("Django models not available")
            return []

        categories = VODCategory.objects.filter(category_type='series')

        result = []
        for cat in categories:
            result.append({
                "name": cat.name,
                "category_type": cat.category_type
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