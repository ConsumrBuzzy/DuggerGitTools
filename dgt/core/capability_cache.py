"""Capability caching system for performance optimization."""

import json
import time

from loguru import logger

from .config import DGTConfig
from .schema import CapabilityCheck, ToolConfig


class CapabilityCache:
    """Cache system for tool capability detection results."""

    CACHE_VERSION = "1.0"
    DEFAULT_TTL = 24 * 60 * 60  # 24 hours in seconds

    def __init__(self, config: DGTConfig) -> None:
        """Initialize capability cache."""
        self.config = config
        self.logger = logger.bind(capability_cache=True)
        self.cache_dir = config.project_root / ".dgt" / "cache"
        self.cache_file = self.cache_dir / "capabilities.json"

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_result(self, tool_name: str, check_command: list[str]) -> bool | None:
        """Get cached capability check result."""
        try:
            if not self.cache_file.exists():
                return None

            cache_data = self._load_cache()
            cache_key = self._generate_cache_key(tool_name, check_command)

            if cache_key not in cache_data:
                return None

            cached_entry = cache_data[cache_key]

            # Check if cache entry is still valid
            if self._is_cache_valid(cached_entry):
                self.logger.debug(f"Cache hit for tool: {tool_name}")
                return cached_entry["available"]
            self.logger.debug(f"Cache expired for tool: {tool_name}")
            return None

        except Exception as e:
            self.logger.warning(f"Failed to read capability cache: {e}")
            return None

    def cache_result(self, tool_name: str, check_command: list[str], available: bool) -> None:
        """Cache capability check result."""
        try:
            cache_data = self._load_cache()
            cache_key = self._generate_cache_key(tool_name, check_command)

            cache_entry = {
                "available": available,
                "timestamp": time.time(),
                "tool_name": tool_name,
                "check_command": check_command,
                "cache_version": self.CACHE_VERSION,
            }

            cache_data[cache_key] = cache_entry

            self._save_cache(cache_data)
            self.logger.debug(f"Cached result for tool: {tool_name} (available: {available})")

        except Exception as e:
            self.logger.warning(f"Failed to write capability cache: {e}")

    def invalidate_cache(self, tool_name: str | None = None) -> None:
        """Invalidate cache entries."""
        try:
            if tool_name:
                # Invalidate specific tool
                cache_data = self._load_cache()
                keys_to_remove = [
                    key for key, entry in cache_data.items()
                    if entry.get("tool_name") == tool_name
                ]

                for key in keys_to_remove:
                    del cache_data[key]

                self._save_cache(cache_data)
                self.logger.info(f"Invalidated cache for tool: {tool_name}")
            else:
                # Invalidate all cache
                if self.cache_file.exists():
                    self.cache_file.unlink()
                self.logger.info("Invalidated all capability cache")

        except Exception as e:
            self.logger.warning(f"Failed to invalidate cache: {e}")

    def cleanup_expired_entries(self) -> int:
        """Remove expired cache entries."""
        try:
            cache_data = self._load_cache()
            current_time = time.time()

            expired_keys = [
                key for key, entry in cache_data.items()
                if not self._is_cache_valid(entry, current_time)
            ]

            for key in expired_keys:
                del cache_data[key]

            if expired_keys:
                self._save_cache(cache_data)
                self.logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

            return len(expired_keys)

        except Exception as e:
            self.logger.warning(f"Failed to cleanup cache: {e}")
            return 0

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        try:
            cache_data = self._load_cache()
            current_time = time.time()

            total_entries = len(cache_data)
            valid_entries = sum(
                1 for entry in cache_data.values()
                if self._is_cache_valid(entry, current_time)
            )
            expired_entries = total_entries - valid_entries

            # Group by tool
            tool_stats = {}
            for entry in cache_data.values():
                tool_name = entry.get("tool_name", "unknown")
                if tool_name not in tool_stats:
                    tool_stats[tool_name] = {"available": 0, "unavailable": 0}

                if entry.get("available", False):
                    tool_stats[tool_name]["available"] += 1
                else:
                    tool_stats[tool_name]["unavailable"] += 1

            return {
                "total_entries": total_entries,
                "valid_entries": valid_entries,
                "expired_entries": expired_entries,
                "cache_file": str(self.cache_file),
                "cache_size_mb": self.cache_file.stat().st_size / (1024 * 1024) if self.cache_file.exists() else 0,
                "tool_stats": tool_stats,
            }

        except Exception as e:
            self.logger.warning(f"Failed to get cache stats: {e}")
            return {}

    def _load_cache(self) -> dict:
        """Load cache data from file."""
        if not self.cache_file.exists():
            return {}

        try:
            with self.cache_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            self.logger.warning("Invalid cache file format, starting fresh")
            return {}

    def _save_cache(self, cache_data: dict) -> None:
        """Save cache data to file."""
        with self.cache_file.open("w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)

    def _generate_cache_key(self, tool_name: str, check_command: list[str]) -> str:
        """Generate cache key for tool and command."""
        import hashlib

        # Create a deterministic key from tool name and command
        command_str = "|".join(check_command)
        key_material = f"{tool_name}:{command_str}"

        return hashlib.md5(key_material.encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: dict, current_time: float | None = None) -> bool:
        """Check if cache entry is still valid."""
        if current_time is None:
            current_time = time.time()

        # Check cache version
        if cache_entry.get("cache_version") != self.CACHE_VERSION:
            return False

        # Check TTL
        timestamp = cache_entry.get("timestamp", 0)
        return (current_time - timestamp) < self.DEFAULT_TTL


class CachedCapabilityChecker:
    """Capability checker with caching support."""

    def __init__(self, config: DGTConfig) -> None:
        """Initialize cached capability checker."""
        self.config = config
        self.cache = CapabilityCache(config)
        self.logger = logger.bind(cached_checker=True)

    def check_capability(self, tool_config: ToolConfig) -> bool:
        """Check tool capability with caching."""
        # Try cache first
        cached_result = self.cache.get_cached_result(
            tool_config.name,
            tool_config.check.command,
        )

        if cached_result is not None:
            return cached_result

        # Run actual check
        result = self._run_capability_check(tool_config.check)

        # Cache the result
        self.cache.cache_result(
            tool_config.name,
            tool_config.check.command,
            result,
        )

        return result

    def _run_capability_check(self, capability_check: CapabilityCheck) -> bool:
        """Run actual capability check."""
        import subprocess

        try:
            result = subprocess.run(
                capability_check.command,
                check=False, capture_output=True,
                text=True,
                timeout=capability_check.timeout,
                cwd=self.config.project_root,
            )

            success = result.returncode == capability_check.expected_exit
            self.logger.debug(f"Capability check: {' '.join(capability_check.command)} -> {success}")
            return success

        except subprocess.TimeoutExpired:
            self.logger.debug(f"Capability check timed out: {' '.join(capability_check.command)}")
            return False
        except FileNotFoundError:
            self.logger.debug(f"Capability check not found: {capability_check.command[0]}")
            return False
        except Exception as e:
            self.logger.debug(f"Capability check error: {e}")
            return False

    def invalidate_tool_cache(self, tool_name: str) -> None:
        """Invalidate cache for specific tool."""
        self.cache.invalidate_cache(tool_name)

    def cleanup_cache(self) -> int:
        """Clean up expired cache entries."""
        return self.cache.cleanup_expired_entries()

    def get_cache_info(self) -> dict:
        """Get cache information."""
        return self.cache.get_cache_stats()
