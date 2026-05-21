"""Dispatcharr API client"""

import logging
from typing import Dict, List, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class DispatcharrClient:
    """HTTP client for Dispatcharr API"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Api-Key": self._api_key},
            timeout=30.0
        )

    def __del__(self):
        """Close HTTP client on deletion"""
        self._client.close()

    def get_movies(self) -> List[Dict[str, Any]]:
        """Fetch all movies from Dispatcharr"""
        try:
            response = self._client.get("/api/v3/movie")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch movies: %s", e)
            return []

    def get_series(self) -> List[Dict[str, Any]]:
        """Fetch all series from Dispatcharr"""
        try:
            response = self._client.get("/api/v3/series")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch series: %s", e)
            return []

    def get_movie_file(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get movie file information"""
        try:
            response = self._client.get(f"/api/v3/moviefile?movieId={movie_id}")
            response.raise_for_status()
            data = response.json()
            return data[0] if data else None
        except httpx.HTTPError as e:
            logger.error("Failed to fetch movie file for %d: %s", movie_id, e)
            return None

    def get_episode_file(self, episode_id: int) -> Optional[Dict[str, Any]]:
        """Get episode file information"""
        try:
            response = self._client.get(f"/api/v3/episodefile?episodeId={episode_id}")
            response.raise_for_status()
            data = response.json()
            return data[0] if data else None
        except httpx.HTTPError as e:
            logger.error("Failed to fetch episode file for %d: %s", episode_id, e)
            return None

    def get_stream_url(self, file_id: int, file_type: str = "movie") -> str:
        """Get proxy stream URL for a file"""
        return f"{self.base_url}/api/v3/stream/{file_type}/{file_id}"