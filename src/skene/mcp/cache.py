"""Analysis result caching with smart invalidation for MCP server."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles

try:
    import xxhash
except ImportError:
    xxhash = None

# Phase-specific cache key prefixes
PHASE_PREFIXES = {
    "tech_stack": "tech_stack",
    "product_overview": "product_overview",
    "current_growth_features": "current_growth_features",
    "features": "features",
    "manifest": "manifest",
    "growth_template": "growth_template",
}

# Key files that indicate project changes
MARKER_FILES = [
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "composer.lock",
]

# Source directories to track mtimes
SOURCE_DIRS = ["src", "lib", "app", "pages", "components", "api", "server", "client"]


@dataclass
class CacheEntry:
    """Cached analysis result."""

    manifest: dict[str, Any]
    metadata: dict[str, Any]
    created_at: float
    marker_hashes: dict[str, str]
    dir_mtimes: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "manifest": self.manifest,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "marker_hashes": self.marker_hashes,
            "dir_mtimes": self.dir_mtimes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheEntry:
        """Create from dictionary."""
        return cls(
            manifest=data["manifest"],
            metadata=data["metadata"],
            created_at=data["created_at"],
            marker_hashes=data["marker_hashes"],
            dir_mtimes=data["dir_mtimes"],
        )


@dataclass
class AnalysisCache:
    """Manages cached analysis results."""

    cache_dir: Path
    ttl: int = 3600  # Default 1 hour
    _memory_cache: dict[str, CacheEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get(self, repo_path: Path, params: dict[str, Any]) -> CacheEntry | None:
        """Get cached result if valid."""
        cache_key = self._compute_cache_key(repo_path, params)

        # Check memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if await self._is_valid(entry, repo_path):
                return entry
            else:
                del self._memory_cache[cache_key]

        # Check disk cache
        entry = await self._load_from_disk(cache_key)
        if entry and await self._is_valid(entry, repo_path):
            self._memory_cache[cache_key] = entry
            return entry

        return None

    async def set(self, repo_path: Path, params: dict[str, Any], manifest: dict[str, Any]) -> None:
        """Cache analysis result with invalidation markers."""
        cache_key = self._compute_cache_key(repo_path, params)
        marker_hashes = await self._compute_marker_hashes(repo_path)
        dir_mtimes = self._get_directory_mtimes(repo_path)

        entry = CacheEntry(
            manifest=manifest,
            metadata=params,
            created_at=time.time(),
            marker_hashes=marker_hashes,
            dir_mtimes=dir_mtimes,
        )

        self._memory_cache[cache_key] = entry
        await self._save_to_disk(cache_key, entry)

    async def clear(self, repo_path: Path | None = None) -> int:
        """Clear cache entries."""
        count = 0

        if repo_path is None:
            # Clear all
            count = len(self._memory_cache)
            self._memory_cache.clear()

            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
        else:
            # Clear entries matching this repo
            repo_str = str(repo_path.resolve())
            keys_to_remove = []

            for key, entry in self._memory_cache.items():
                if entry.metadata.get("repo_path") == repo_str:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._memory_cache[key]
                cache_file = self.cache_dir / f"{key}.json"
                if cache_file.exists():
                    cache_file.unlink()
                count += 1

        return count

    async def _is_valid(self, entry: CacheEntry, repo_path: Path) -> bool:
        """Check if cache entry is still valid."""
        # Check TTL
        if time.time() - entry.created_at > self.ttl:
            return False

        # Check marker file hashes
        current_hashes = await self._compute_marker_hashes(repo_path)
        if current_hashes != entry.marker_hashes:
            return False

        # Check directory mtimes
        current_mtimes = self._get_directory_mtimes(repo_path)
        if current_mtimes != entry.dir_mtimes:
            return False

        return True

    def _compute_cache_key(self, repo_path: Path, params: dict[str, Any]) -> str:
        """Compute cache key from repo path and parameters."""
        key_data = {
            "repo_path": str(repo_path.resolve()),
            "params": params,
        }
        key_str = json.dumps(key_data, sort_keys=True)
        if xxhash:
            return xxhash.xxh64(key_str.encode()).hexdigest()
        else:
            return hashlib.sha256(key_str.encode()).hexdigest()

    async def _compute_marker_hashes(self, repo_path: Path) -> dict[str, str]:
        """Compute hashes for marker files in the repository."""
        hashes: dict[str, str] = {}

        for marker in MARKER_FILES:
            marker_path = repo_path / marker
            if marker_path.exists():
                try:
                    async with aiofiles.open(marker_path, "rb") as f:
                        content = await f.read()
                        if xxhash:
                            hashes[marker] = xxhash.xxh64(content).hexdigest()
                        else:
                            hashes[marker] = hashlib.sha256(content).hexdigest()
                except (OSError, PermissionError):
                    pass

        return hashes

    def _get_directory_mtimes(self, repo_path: Path) -> dict[str, float]:
        """Get modification times for source directories."""
        mtimes: dict[str, float] = {}

        for src_dir in SOURCE_DIRS:
            dir_path = repo_path / src_dir
            if dir_path.exists() and dir_path.is_dir():
                try:
                    mtimes[src_dir] = dir_path.stat().st_mtime
                except (OSError, PermissionError):
                    pass

        return mtimes

    async def _load_from_disk(self, cache_key: str) -> CacheEntry | None:
        """Load cache entry from disk."""
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            async with aiofiles.open(cache_file, "r") as f:
                data = json.loads(await f.read())
                return CacheEntry.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError):
            cache_file.unlink(missing_ok=True)
            return None

    async def _save_to_disk(self, cache_key: str, entry: CacheEntry) -> None:
        """Save cache entry to disk."""
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            async with aiofiles.open(cache_file, "w") as f:
                await f.write(json.dumps(entry.to_dict(), indent=2, default=str))
        except OSError:
            pass

    # Phase-specific cache methods for granular tool caching

    def _compute_phase_cache_key(self, repo_path: Path, phase: str) -> str:
        """Compute cache key for a specific analysis phase."""
        if phase not in PHASE_PREFIXES:
            raise ValueError(f"Unknown phase: {phase}. Valid phases: {list(PHASE_PREFIXES.keys())}")

        key_data = {
            "repo_path": str(repo_path.resolve()),
            "phase": phase,
        }
        key_str = json.dumps(key_data, sort_keys=True)
        if xxhash:
            hash_digest = xxhash.xxh64(key_str.encode()).hexdigest()
        else:
            hash_digest = hashlib.sha256(key_str.encode()).hexdigest()
        return f"{PHASE_PREFIXES[phase]}_{hash_digest}"

    async def get_phase(self, repo_path: Path, phase: str) -> dict[str, Any] | None:
        """Get cached result for a specific analysis phase.

        Args:
            repo_path: Path to the repository
            phase: Phase name (tech_stack, product_overview, current_growth_features,
                features, manifest, growth_template)

        Returns:
            Cached phase data if valid, None otherwise
        """
        cache_key = self._compute_phase_cache_key(repo_path, phase)

        # Check memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if await self._is_valid(entry, repo_path):
                return entry.manifest  # manifest field stores the phase data
            else:
                del self._memory_cache[cache_key]

        # Check disk cache
        entry = await self._load_from_disk(cache_key)
        if entry and await self._is_valid(entry, repo_path):
            self._memory_cache[cache_key] = entry
            return entry.manifest

        return None

    async def set_phase(self, repo_path: Path, phase: str, data: dict[str, Any]) -> None:
        """Cache result for a specific analysis phase.

        Args:
            repo_path: Path to the repository
            phase: Phase name (tech_stack, product_overview, current_growth_features,
                features, manifest, growth_template)
            data: Phase analysis data to cache
        """
        cache_key = self._compute_phase_cache_key(repo_path, phase)
        marker_hashes = await self._compute_marker_hashes(repo_path)
        dir_mtimes = self._get_directory_mtimes(repo_path)

        entry = CacheEntry(
            manifest=data,  # Store phase data in manifest field
            metadata={"phase": phase, "repo_path": str(repo_path.resolve())},
            created_at=time.time(),
            marker_hashes=marker_hashes,
            dir_mtimes=dir_mtimes,
        )

        self._memory_cache[cache_key] = entry
        await self._save_to_disk(cache_key, entry)

    async def clear_phase(self, repo_path: Path, phase: str) -> bool:
        """Clear cache for a specific analysis phase.

        Args:
            repo_path: Path to the repository
            phase: Phase name to clear

        Returns:
            True if cache was cleared, False if no cache existed
        """
        cache_key = self._compute_phase_cache_key(repo_path, phase)
        cleared = False

        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            cleared = True

        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            cache_file.unlink()
            cleared = True

        return cleared
