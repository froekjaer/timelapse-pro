"""
Site-Wide Look Matching Configuration Client for Edge Nodes

Handles database-driven configuration with local caching for offline operation.
Polls headend for config changes and caches locally.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)


class SiteLookConfigClient:
    """
    Client for fetching and caching Site-Wide Look Matching configuration.

    Features:
    - Fetches config from headend API
    - Caches locally for offline operation
    - Configurable polling interval
    - Thread-safe operations
    """

    def __init__(self, config: dict):
        """
        Initialize config client.

        Args:
            config: Dictionary containing:
                - headend_url: Base URL of headend API
                - edge_node_id: This edge node's identifier
                - cache_path: Where to cache config locally
                - poll_interval_seconds: How often to poll for changes
                - cache_ttl_seconds: How long to use cache if offline
        """
        self._headend_url = config.get('headend_url', 'http://localhost:8000')
        self._edge_node_id = config.get('edge_node_id', 'unknown-edge')
        self._cache_path = Path(config.get('cache_path', '/var/lib/timelapse/site_look_config.json'))
        self._poll_interval = config.get('poll_interval_seconds', 300)  # 5 min default
        self._cache_ttl = config.get('cache_ttl_seconds', 86400)  # 24 hour default

        self._config: Optional[dict] = None
        self._config_version: int = 0
        self._last_fetch: Optional[float] = None
        self._last_poll: Optional[float] = None

        self._lock = threading.RLock()

        # Load cached config on startup
        self._load_cached()

        # Start background polling thread
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None

    def _load_cached(self) -> bool:
        """Load configuration from local cache."""
        try:
            if self._cache_path.exists():
                with open(self._cache_path) as f:
                    cached = json.load(f)

                cached_at = cached.get('cached_at', 0)
                expires_at = cached.get('expires_at', 0)

                # Check if cache is still valid
                if expires_at and time.time() < expires_at:
                    self._config = cached.get('config')
                    self._config_version = cached.get('version', 0)
                    self._last_fetch = cached_at

                    log.info(f"Loaded cached config (v{self._config_version})")
                    return True
                else:
                    log.warning("Cached config expired")
                    return False
        except Exception as exc:
            log.error(f"Failed to load cached config: {exc}")
            return False

    def _save_cached(self, config: dict, version: int) -> None:
        """Save configuration to local cache."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)

            now = time.time()
            expires_at = now + self._cache_ttl

            cached = {
                'version': version,
                'cached_at': now,
                'expires_at': expires_at,
                'config': config,
            }

            with open(self._cache_path, 'w') as f:
                json.dump(cached, f, indent=2)

            log.debug(f"Saved cached config (v{version}, expires {datetime.fromtimestamp(expires_at)})")
        except Exception as exc:
            log.error(f"Failed to save cached config: {exc}")

    def _fetch_from_api(self) -> Optional[dict]:
        """Fetch configuration from headend API."""
        try:
            url = f"{self._headend_url}/api/admin/site-look/edge/{self._edge_node_id}/config"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Extract config from API response
                config = data.get('config', {})
                version = data.get('version', 0)

                return {'config': config, 'version': version}
            elif response.status_code == 404:
                log.warning("Config endpoint not found - using defaults")
                return self._get_defaults()
            else:
                log.error(f"API returned status {response.status_code}")
                return None

        except requests.RequestException as exc:
            log.error(f"Failed to fetch config from API: {exc}")
            return None

    def _get_defaults(self) -> dict:
        """Return default configuration if API unavailable."""
        return {
            'config': {
                'enabled': True,
                'storage_path': '/var/lib/timelapse/site_looks',
                'reference_quality_threshold': 75.0,
                'auto_create_reference': True,
                'auto_update_reference': False,
                'lut_auto_generate': True,
                'lut_regeneration_interval_hours': 168,
            },
            'version': 0,
        }

    def fetch_config(self, force: bool = False) -> dict:
        """
        Fetch configuration, using cache if available.

        Args:
            force: Force refresh from API

        Returns:
            Configuration dictionary
        """
        with self._lock:
            now = time.time()

            # Check if we need to refresh
            need_refresh = (
                force or
                self._config is None or
                self._last_fetch is None or
                (now - self._last_fetch) > self._poll_interval
            )

            if need_refresh:
                log.info("Fetching config from headend...")
                self._last_poll = now

                result = self._fetch_from_api()

                if result:
                    self._config = result['config']
                    self._config_version = result['version']
                    self._last_fetch = now

                    # Save to cache
                    self._save_cached(self._config, self._config_version)

                    log.info(f"Config updated (v{self._config_version})")
                else:
                    # API failed - use cache if available
                    if self._config is None:
                        log.warning("No config available - using defaults")
                        self._config = self._get_defaults()['config']
                        self._last_fetch = now

            return self._config

    def get_config(self) -> dict:
        """Get current configuration (thread-safe)."""
        with self._lock:
            if self._config is None:
                return self.fetch_config()
            return dict(self._config)

    def get_value(self, key: str, default=None):
        """Get a specific configuration value."""
        config = self.get_config()
        return config.get(key, default)

    def start_polling(self) -> None:
        """Start background polling thread."""
        with self._lock:
            if self._polling:
                return

            self._polling = True
            self._poll_thread = threading.Thread(
                target=self._poll_loop,
                daemon=True,
                name="SiteLookConfigPoller"
            )
            self._poll_thread.start()
            log.info(f"Started config polling (interval: {self._poll_interval}s)")

    def stop_polling(self) -> None:
        """Stop background polling thread."""
        with self._lock:
            self._polling = False
            if self._poll_thread:
                self._poll_thread.join(timeout=5)
                self._poll_thread = None
            log.info("Stopped config polling")

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._polling:
            try:
                time.sleep(self._poll_interval)
                if self._polling:
                    self.fetch_config(force=True)
            except Exception as exc:
                log.error(f"Error in polling loop: {exc}")

    def invalidate_cache(self) -> None:
        """Invalidate local cache (force refresh on next access)."""
        with self._lock:
            self._last_fetch = None
            log.info("Cache invalidated")

    def get_status(self) -> dict:
        """Get client status for monitoring."""
        with self._lock:
            return {
                'edge_node_id': self._edge_node_id,
                'config_version': self._config_version,
                'last_fetch': self._last_fetch,
                'last_poll': self._last_poll,
                'poll_interval': self._poll_interval,
                'cache_ttl': self._cache_ttl,
                'polling': self._polling,
                'cache_path': str(self._cache_path),
            }


# Global client instance
_client: Optional[SiteLookConfigClient] = None


def init_config_client(config: dict) -> SiteLookConfigClient:
    """Initialize global config client."""
    global _client
    _client = SiteLookConfigClient(config)
    _client.start_polling()
    return _client


def get_config_client() -> Optional[SiteLookConfigClient]:
    """Get global config client instance."""
    return _client
