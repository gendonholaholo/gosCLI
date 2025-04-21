"""Concrete implementation of the multi-level Caching Service.

Manages L1 (in-memory) and L2 (file-based) caches with configurable TTLs
and sliding window expiration. Includes placeholders for L3 vector cache.
"""

import logging
import time
import os
import pickle
import hashlib
import shutil
from typing import Any, Optional, Dict
from pathlib import Path
from dataclasses import dataclass
import asyncio

# Domain Layer Imports
from goscli.domain.interfaces.cache import CacheService
from goscli.domain.models.common import CacheKey

# TODO: Consider using a more robust disk cache library like `diskcache`

logger = logging.getLogger(__name__)

# Default Configuration Constants (TODO: Make these configurable via settings/env)
DEFAULT_L1_MAX_ITEMS = 100
DEFAULT_L1_TTL_SECONDS = 15 * 60  # 15 minutes
DEFAULT_L2_TTL_SECONDS = 24 * 60 * 60 # 24 hours
# Use pathlib for proper cross-platform path handling
DEFAULT_L2_CACHE_DIR = Path.home() / ".goscli_cache" / "l2_cache"
# L3 Placeholders
DEFAULT_L3_TTL_SECONDS = 7 * 24 * 60 * 60 # 7 days

@dataclass
class CacheEntry:
    """Internal representation of a cache entry with expiry."""
    value: Any
    expiry_time: float # Unix timestamp when the entry expires

class CachingServiceImpl(CacheService):
    """Multi-level cache implementation (L1 Memory, L2 File)."""

    def __init__(
        self,
        l1_max_items: int = DEFAULT_L1_MAX_ITEMS,
        l1_ttl: int = DEFAULT_L1_TTL_SECONDS,
        l2_ttl: int = DEFAULT_L2_TTL_SECONDS,
        l2_dir: Path = DEFAULT_L2_CACHE_DIR,
        # TODO: Add L3 configuration (client, embedding model, etc.)
    ):
        """Initializes the caching service."""
        # L1 Cache (In-Memory)
        self.l1_cache: Dict[CacheKey, CacheEntry] = {}
        self.l1_max_items = l1_max_items
        self.l1_ttl = l1_ttl

        # L2 Cache (File-Based)
        # Ensure l2_dir is a Path object for cross-platform compatibility
        self.l2_dir = Path(l2_dir) if not isinstance(l2_dir, Path) else l2_dir
        self.l2_ttl = l2_ttl
        self._setup_l2_dir()

        # TODO: Initialize L3 Cache (Vector DB client etc.)
        # self.l3_client = None

        logger.info(f"CachingService initialized. L1(ttl={l1_ttl}s, max={l1_max_items}), L2(dir={self.l2_dir}, ttl={l2_ttl}s)")

    def _setup_l2_dir(self) -> None:
        """Creates the L2 cache directory if it doesn't exist."""
        try:
            self.l2_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create L2 cache directory {self.l2_dir}: {e}")
            # Degrade gracefully? Disable L2?
            raise

    def _get_l2_filepath(self, key: CacheKey) -> Path:
        """Generates a safe file path for an L2 cache key."""
        # Hash the key to create a relatively safe filename
        hashed_key = hashlib.sha256(str(key).encode()).hexdigest()
        # Use subdirectories to avoid too many files in one folder
        subfolder = self.l2_dir / hashed_key[:2]
        # Ensure subfolder exists
        subfolder.mkdir(parents=True, exist_ok=True)
        return subfolder / hashed_key

    def _is_expired(self, entry: Optional[CacheEntry]) -> bool:
        """Checks if a cache entry is expired."""
        return entry is None or time.time() > entry.expiry_time

    def _prune_l1(self) -> None:
        """Removes expired items from L1 cache and evicts oldest if over limit."""
        now = time.time()
        expired_keys = [k for k, v in self.l1_cache.items() if now > v.expiry_time]
        for k in expired_keys:
            del self.l1_cache[k]

        # Simple LRU-like eviction if over size limit (needs access time tracking for true LRU)
        # For now, just remove *some* items if too large (not strictly LRU)
        while len(self.l1_cache) > self.l1_max_items:
            try:
                # Remove the first item (oldest by insertion order in Python 3.7+)
                oldest_key = next(iter(self.l1_cache))
                del self.l1_cache[oldest_key]
            except StopIteration:
                break # Cache is empty

    # --- CacheService Interface Implementation --- 

    async def get(self, key: CacheKey, level: str = 'all') -> Optional[Any]:
        """Retrieves an item from the specified cache level(s)."""
        now = time.time()

        # Check L1
        if level in ['l1', 'all']:
            self._prune_l1() # Prune before get
            l1_entry = self.l1_cache.get(key)
            if l1_entry and now <= l1_entry.expiry_time:
                 # Sliding window: Update expiry on access
                 l1_entry.expiry_time = now + self.l1_ttl
                 logger.debug(f"L1 cache hit for key: {key}")
                 return l1_entry.value

        # Check L2
        if level in ['l2', 'all']:
            l2_filepath = self._get_l2_filepath(key)
            if l2_filepath.exists():
                try:
                    async with asyncio.Lock(): # Basic file locking
                        with open(l2_filepath, 'rb') as f:
                            l2_entry: CacheEntry = pickle.load(f)
                    
                    if now <= l2_entry.expiry_time:
                        logger.debug(f"L2 cache hit for key: {key}")
                        # Promote to L1 and apply sliding TTL
                        await self.set(key, l2_entry.value, ttl=self.l1_ttl, level='l1') 
                        # Update L2 expiry (sliding window for L2 too? Optional)
                        # l2_entry.expiry_time = now + self.l2_ttl
                        # async with asyncio.Lock():
                        #    with open(l2_filepath, 'wb') as f:
                        #        pickle.dump(l2_entry, f)
                        return l2_entry.value
                    else:
                        logger.debug(f"L2 cache expired for key: {key}. Removing file.")
                        l2_filepath.unlink(missing_ok=True) # Remove expired file
                except (pickle.UnpicklingError, EOFError, FileNotFoundError, OSError) as e:
                     logger.warning(f"Failed to read or parse L2 cache file {l2_filepath}: {e}. Removing.")
                     try:
                         l2_filepath.unlink(missing_ok=True)
                     except OSError as unlink_err:
                         logger.warning(f"Failed to delete corrupted cache file: {unlink_err}")

        # TODO: Check L3 (Vector Cache)
        if level in ['l3', 'all']:
             # l3_result = await self._get_from_l3(key)
             # if l3_result:
             #     logger.debug(f"L3 cache hit for key: {key}")
             #     await self.set(key, l3_result, level='l1') # Promote
             #     return l3_result
             pass # Placeholder

        logger.debug(f"Cache miss for key: {key} across checked levels: {level}")
        return None

    async def set(
        self, key: CacheKey, value: Any, ttl: Optional[int] = None, level: str = 'all'
    ) -> None:
        """Stores an item in the specified cache level(s)."""
        now = time.time()

        if level in ['l1', 'all']:
            l1_expiry = now + (ttl if ttl is not None else self.l1_ttl)
            entry = CacheEntry(value=value, expiry_time=l1_expiry)
            self.l1_cache[key] = entry
            self._prune_l1() # Ensure size limit after adding
            logger.debug(f"Stored item in L1 cache: key={key}")

        if level in ['l2', 'all']:
            l2_expiry = now + (ttl if ttl is not None else self.l2_ttl)
            entry = CacheEntry(value=value, expiry_time=l2_expiry)
            l2_filepath = self._get_l2_filepath(key)
            try:
                # Ensure parent directory exists (already handled in _get_l2_filepath)
                # Write atomically using temp file (basic approach)
                temp_filepath = l2_filepath.with_suffix('.tmp')
                async with asyncio.Lock(): # Basic file locking
                    with open(temp_filepath, 'wb') as f:
                        pickle.dump(entry, f)
                    # Use os.replace for atomic operation (works on Windows and Unix)
                    os.replace(str(temp_filepath), str(l2_filepath))
                logger.debug(f"Stored item in L2 cache: key={key}, file={l2_filepath}")
            except (pickle.PicklingError, OSError) as e:
                logger.error(f"Failed to write to L2 cache file {l2_filepath}: {e}")
                # Clean up temp file if it exists
                try:
                    if temp_filepath.exists():
                        temp_filepath.unlink(missing_ok=True)
                except OSError:
                    pass  # Ignore cleanup errors

        # TODO: Store in L3 (Vector Cache)
        if level in ['l3', 'all']:
            # await self._set_in_l3(key, value, ttl)
            pass # Placeholder

    async def delete(self, key: CacheKey, level: str = 'all') -> None:
        """Deletes an item from the specified cache level(s)."""
        if level in ['l1', 'all']:
            if key in self.l1_cache:
                del self.l1_cache[key]
                logger.debug(f"Deleted item from L1 cache: key={key}")

        if level in ['l2', 'all']:
            l2_filepath = self._get_l2_filepath(key)
            if l2_filepath.exists():
                try:
                    l2_filepath.unlink(missing_ok=True)
                    logger.debug(f"Deleted item from L2 cache: key={key}, file={l2_filepath}")
                    # Try removing empty parent directory
                    try:
                        parent_dir = l2_filepath.parent
                        if parent_dir != self.l2_dir and not any(parent_dir.iterdir()):
                            parent_dir.rmdir()
                            logger.debug(f"Removed empty cache subdirectory: {parent_dir}")
                    except OSError:
                        pass # Ignore if directory is not empty
                except OSError as e:
                     logger.warning(f"Failed to delete L2 cache file {l2_filepath}: {e}")

        # TODO: Delete from L3 (Vector Cache)
        if level in ['l3', 'all']:
            # await self._delete_from_l3(key)
            pass # Placeholder

    async def clear(self, level: str = 'all') -> None:
        """Clears all items from the specified cache level(s)."""
        if level in ['l1', 'all']:
            self.l1_cache.clear()
            logger.info("Cleared L1 (in-memory) cache.")

        if level in ['l2', 'all']:
            if self.l2_dir.exists():
                try:
                    # Use shutil rmtree with error handling for Windows 
                    # where files might be locked or in use
                    shutil.rmtree(self.l2_dir, ignore_errors=True)
                    self._setup_l2_dir() # Recreate base directory
                    logger.info(f"Cleared L2 (file) cache at: {self.l2_dir}")
                except OSError as e:
                    logger.error(f"Failed to clear L2 cache directory {self.l2_dir}: {e}")
            else:
                 logger.info("L2 cache directory does not exist, nothing to clear.")

        # TODO: Clear L3 (Vector Cache)
        if level in ['l3', 'all']:
             # await self._clear_l3()
             logger.info("Clearing L3 (vector) cache (Not Implemented).")
             pass # Placeholder

    # --- Placeholder L3 Methods ---
    # async def _get_from_l3(self, key: CacheKey) -> Optional[Any]: ...
    # async def _set_in_l3(self, key: CacheKey, value: Any, ttl: Optional[int]) -> None: ...
    # async def _delete_from_l3(self, key: CacheKey) -> None: ...
    # async def _clear_l3(self) -> None: ... 