"""Dispatcharr VOD integration"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from collections import defaultdict

# These imports will be available when running inside Dispatcharr
# We'll handle import errors gracefully during development
try:
    from apps.vod.models import Movie, Series, Episode, VODCategory
    from apps.m3u.models import M3UAccount, M3UMovieRelation, M3USeriesRelation, M3UEpisodeRelation
    from apps.vod.tasks import refresh_series_episodes
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    Movie = Series = Episode = VODCategory = None
    M3UAccount = M3UMovieRelation = M3USeriesRelation = M3UEpisodeRelation = None
    refresh_series_episodes = None


logger = logging.getLogger(__name__)


class DispatcharrIntegrator:
    """Integration with Dispatcharr VOD models and tasks"""

    def __init__(self, auto_hydrate: bool = True):
        self.auto_hydrate = auto_hydrate
        self._hydration_queue: Dict[str, datetime] = {}
        self._hydration_cooldown = 300  # 5 minutes cooldown

    def is_available(self) -> bool:
        """Check if Django models are available"""
        return DJANGO_AVAILABLE

    def get_all_movies(self) -> List[Dict[str, Any]]:
        """Get all movies from Dispatcharr"""
        if not self.is_available():
            logger.warning("Django models not available")
            return []

        movies = Movie.objects.all().select_related('logo')

        result = []
        for movie in movies:
            # Get M3U relations for streaming URLs
            relations = M3UMovieRelation.objects.filter(movie=movie)

            streams = []
            for rel in relations:
                stream_url = rel.get_stream_url()
                streams.append({
                    "stream_id": rel.stream_id,
                    "account_name": rel.m3u_account.name if rel.m3u_account else "Unknown",
                    "stream_url": stream_url,
                    "extension": rel.container_extension or "mkv"
                })

            result.append({
                "uuid": str(movie.uuid),
                "name": movie.name,
                "year": movie.year,
                "description": movie.description,
                "rating": movie.rating,
                "genre": movie.genre,
                "streams": streams
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
            relations = M3USeriesRelation.objects.filter(series=series)

            providers = []
            for rel in relations:
                providers.append({
                    "account_name": rel.m3u_account.name if rel.m3u_account else "Unknown",
                    "external_series_id": rel.external_series_id
                })

            result.append({
                "uuid": str(series.uuid),
                "name": series.name,
                "year": series.year,
                "description": series.description,
                "rating": series.rating,
                "genre": series.genre,
                "episode_count": episode_count,
                "providers": providers
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

        episodes = series.episodes.all().order_by('season_number', 'episode_number')

        result = []
        for episode in episodes:
            # Get M3U relations for streaming URLs
            relations = M3UEpisodeRelation.objects.filter(episode=episode)

            streams = []
            for rel in relations:
                stream_url = rel.get_stream_url()
                streams.append({
                    "stream_id": rel.stream_id,
                    "account_name": rel.m3u_account.name if rel.m3u_account else "Unknown",
                    "stream_url": stream_url,
                    "extension": rel.container_extension or "mkv"
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

    def trigger_hydration(self, series_uuid: str) -> bool:
        """Trigger episode hydration for a series"""
        if not self.auto_hydrate or not self.is_available():
            return False

        # Check cooldown
        if series_uuid in self._hydration_queue:
            last_hydration = self._hydration_queue[series_uuid]
            cooldown_remaining = self._hydration_cooldown - (datetime.now() - last_hydration).total_seconds()
            if cooldown_remaining > 0:
                logger.info("Series %s in cooldown (%d seconds remaining)", series_uuid, int(cooldown_remaining))
                return False

        # Enqueue hydration task
        try:
            # Find the series
            series = Series.objects.get(uuid=series_uuid)

            # Find active M3U accounts
            accounts = M3UAccount.objects.filter(is_active=True)

            for account in accounts:
                # Get series relation
                rel = M3USeriesRelation.objects.filter(series=series, m3u_account=account).first()
                if rel and rel.external_series_id:
                    # Queue the task (fire-and-forget)
                    if refresh_series_episodes:
                        refresh_series_episodes.delay(account.id, series.id, rel.external_series_id)
                        logger.info("Enqueued hydration for series %s (account: %s)", series.name, account.name)

            self._hydration_queue[series_uuid] = datetime.now()
            return True
        except Series.DoesNotExist:
            logger.warning("Series %s not found for hydration", series_uuid)
            return False
        except Exception as e:
            logger.exception("Failed to trigger hydration for series %s: %s", series_uuid, e)
            return False

    def get_proxy_url(self, content_type: str, uuid: str, stream_id: str) -> str:
        """Generate Dispatcharr proxy URL for content"""
        if content_type == "movie":
            return f"/proxy/vod/movie/{uuid}?stream_id={stream_id}"
        elif content_type == "episode":
            return f"/proxy/vod/episode/{uuid}?stream_id={stream_id}"
        else:
            raise ValueError(f"Unknown content type: {content_type}")

    def build_filename(self, title: str, year: int, provider_short: str, stream_id: str, ext: str) -> str:
        """Build filename following design spec"""
        # Format: {Title} ({Year}) - {ProviderShortName}-{StreamID}.{ext}
        return f"{title} ({year}) - {provider_short}-{stream_id}.{ext}"