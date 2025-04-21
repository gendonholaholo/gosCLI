"""Interface for caching mechanisms.

Defines the contract for storing, retrieving, and managing cached data,
supporting multiple levels (L1, L2, L3) and TTL strategies.
"""

import abc
from typing import Any, Optional

# Import relevant domain models
from ..models.common import CacheKey

class CacheService(abc.ABC):
    """Abstract Base Class for caching operations."""

    @abc.abstractmethod
    async def get(self, key: CacheKey, level: str = 'all') -> Optional[Any]:
        """Retrieves an item from the cache asynchronously.

        Searches specified levels (or all) in order (L1, L2, L3).

        Args:
            key: The cache key to retrieve.
            level: The cache level(s) to check ('l1', 'l2', 'l3', 'all').

        Returns:
            The cached item if found and not expired, otherwise None.
        """
        pass

    @abc.abstractmethod
    async def set(
        self,
        key: CacheKey,
        value: Any,
        ttl: Optional[int] = None,
        level: str = 'all'
    ) -> None:
        """Stores an item in the specified cache level(s) asynchronously.

        Args:
            key: The cache key to store the item under.
            value: The item to store.
            ttl: Time-to-live in seconds (uses level default if None).
            level: The cache level(s) to store in ('l1', 'l2', 'l3', 'all').
        """
        pass

    @abc.abstractmethod
    async def delete(self, key: CacheKey, level: str = 'all') -> None:
        """Deletes an item from the specified cache level(s) asynchronously.

        Args:
            key: The cache key to delete.
            level: The cache level(s) to delete from ('l1', 'l2', 'l3', 'all').
        """
        pass

    @abc.abstractmethod
    async def clear(self, level: str = 'all') -> None:
        """Clears all items from the specified cache level(s) asynchronously.

        Args:
            level: The cache level(s) to clear ('l1', 'l2', 'l3', 'all').
        """
        pass

    # Optional: Add methods for more advanced cache operations if needed
    # e.g., async def find_similar(self, embedding: List[float], top_k: int = 3) -> List[Any]:
    # for vector cache (L3) 