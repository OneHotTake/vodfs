"""Celery worker for background hydration tasks"""

import logging
from typing import Dict, List, Any, Optional
from celery import Celery

logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery(
    "vodfs",
    broker="memory://",  # In-memory broker for testing
    backend="cache+memory://"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minute timeout
    task_soft_time_limit=240,
)


@celery_app.task(bind=True, name="vodfs.hydrate_movies")
def hydrate_movies(self, tree_data: Dict[str, Any], movies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Hydrate movies into the virtual filesystem"""
    try:
        count = 0
        for movie in movies:
            title = movie.get("title", "Unknown")
            movie_id = movie.get("id", 0)
            size = movie.get("sizeOnDisk", 0)
            genres = movie.get("genres", [])

            # Add to All directory
            if "movies_all" in tree_data:
                tree_data["movies_all"].append({
                    "name": f"{title}.mkv",
                    "stream_url": f"/api/v3/stream/movie/{movie_id}",
                    "size": size
                })
                count += 1

            # Add to category directories
            for genre in genres:
                cat_key = f"movies_{genre.lower()}"
                if cat_key in tree_data:
                    tree_data[cat_key].append({
                        "name": f"{title}.mkv",
                        "stream_url": f"/api/v3/stream/movie/{movie_id}",
                        "size": size
                    })

        return {"status": "success", "hydrated": count}
    except Exception as e:
        logger.error("Failed to hydrate movies: %s", e)
        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True, name="vodfs.hydrate_series")
def hydrate_series(self, tree_data: Dict[str, Any], series: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Hydrate series into the virtual filesystem"""
    try:
        count = 0
        for show in series:
            title = show.get("title", "Unknown")
            series_id = show.get("id", 0)
            genres = show.get("genres", [])

            # Add to All directory
            if "series_all" in tree_data:
                tree_data["series_all"].append({
                    "name": title,
                    "series_id": series_id,
                    "hydrated": False
                })
                count += 1

            # Add to category directories
            for genre in genres:
                cat_key = f"series_{genre.lower()}"
                if cat_key in tree_data:
                    tree_data[cat_key].append({
                        "name": title,
                        "series_id": series_id,
                        "hydrated": False
                    })

        return {"status": "success", "hydrated": count}
    except Exception as e:
        logger.error("Failed to hydrate series: %s", e)
        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True, name="vodfs.hydrate_episodes")
def hydrate_episodes(self, series_id: int, episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Hydrate episodes for a specific series"""
    try:
        count = 0
        seasons = {}

        for episode in episodes:
            season = episode.get("seasonNumber", 0)
            episode_num = episode.get("episodeNumber", 0)
            episode_title = episode.get("title", f"Episode {episode_num}")
            episode_id = episode.get("id", 0)

            season_key = f"S{season:02d}"
            if season_key not in seasons:
                seasons[season_key] = []

            seasons[season_key].append({
                "name": f"{season_key}E{episode_num:02d} - {episode_title}.mkv",
                "stream_url": f"/api/v3/stream/episode/{episode_id}",
                "size": episode.get("size", 0)
            })
            count += 1

        return {"status": "success", "hydrated": count, "seasons": seasons}
    except Exception as e:
        logger.error("Failed to hydrate episodes for series %d: %s", series_id, e)
        return {"status": "error", "message": str(e)}