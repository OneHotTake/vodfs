"""Lightweight persistent namespace manifest"""

import json
import os
import tempfile
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Manifest file path (persistent across container restarts)
MANIFEST_PATH = "/data/plugins/vodfs/manifest.json"
MANIFEST_VERSION = 1


class ManifestManager:
    """Manages lightweight persistent namespace index"""

    def __init__(self, manifest_path: str = MANIFEST_PATH):
        self.manifest_path = manifest_path
        self._manifest: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        """Load manifest from disk, return empty dict if not exists"""
        if self._manifest is not None:
            return self._manifest

        try:
            path = Path(self.manifest_path)
            if not path.exists():
                logger.info("No manifest found at %s", self.manifest_path)
                self._manifest = self._get_empty_manifest()
                return self._manifest

            with open(path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            # Validate version
            if manifest.get('version') != MANIFEST_VERSION:
                logger.warning("Manifest version mismatch (expected %d, got %s), ignoring",
                             MANIFEST_VERSION, manifest.get('version'))
                self._manifest = self._get_empty_manifest()
                return self._manifest

            logger.info("Loaded manifest from %s (generated_at: %s)",
                       self.manifest_path, manifest.get('generated_at'))
            self._manifest = manifest
            return manifest
        except Exception as e:
            logger.error("Failed to load manifest: %s", e)
            self._manifest = self._get_empty_manifest()
            return self._manifest

    def save(self, manifest: Dict[str, Any]) -> bool:
        """Save manifest atomically (write to temp + rename)"""
        try:
            # Create parent directory if needed
            path = Path(self.manifest_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file
            fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix='.manifest_')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2, default=str)

                # Atomic rename
                os.replace(temp_path, self.manifest_path)
                logger.info("Saved manifest to %s (generated_at: %s)",
                           self.manifest_path, manifest.get('generated_at'))
                self._manifest = manifest
                return True
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                raise
        except Exception as e:
            logger.error("Failed to save manifest: %s", e)
            return False

    def needs_rebuild(self, current_watermark: Dict[str, Any]) -> bool:
        """Check if manifest needs rebuild based on watermark comparison"""
        if not self._manifest:
            self._manifest = self.load()

        manifest_watermark = self._manifest.get('watermark', {})

        # Compare each watermark field
        comparisons = [
            ('m3u_last_synced_at', 'M3U sync timestamp'),
            ('movie_count', 'Movie count'),
            ('series_count', 'Series count'),
            ('series_with_zero_episodes', 'Zero-episode series count'),
            ('vod_max_updated_at', 'VOD max updated timestamp')
        ]

        for field, description in comparisons:
            manifest_val = manifest_watermark.get(field)
            current_val = current_watermark.get(field)

            if manifest_val != current_val:
                logger.info("Watermark change detected: %s (was: %s, now: %s)",
                           description, manifest_val, current_val)
                return True

        return False

    def get_categories(self, content_type: str = 'movies') -> list:
        """Get category list from manifest"""
        if not self._manifest:
            self._manifest = self.load()

        categories = self._manifest.get('categories', {})
        return categories.get(content_type, [])

    def get_series_skeleton(self) -> list:
        """Get series skeleton from manifest"""
        if not self._manifest:
            self._manifest = self.load()

        return self._manifest.get('series_skeleton', [])

    def find_series_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Find series in skeleton by UUID"""
        skeleton = self.get_series_skeleton()
        for series in skeleton:
            if series.get('uuid') == uuid:
                return series
        return None

    @staticmethod
    def _get_empty_manifest() -> Dict[str, Any]:
        """Return empty manifest structure"""
        return {
            "version": MANIFEST_VERSION,
            "generated_at": datetime.utcnow().isoformat(),
            "watermark": {
                "m3u_last_synced_at": None,
                "movie_count": 0,
                "series_count": 0,
                "series_with_zero_episodes": 0,
                "vod_max_updated_at": None
            },
            "categories": {
                "movies": [],
                "series": []
            },
            "series_skeleton": []
        }