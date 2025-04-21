"""Implementation of a rate limiter.

Controls the frequency of outgoing requests to prevent hitting API rate limits.
Uses a simple token bucket or sliding window algorithm.
"""

import time
import asyncio
import logging
from collections import deque

logger = logging.getLogger(__name__)

# TODO: Make parameters configurable
DEFAULT_MAX_REQUESTS = 5 # Example: Max 5 requests...
DEFAULT_TIME_WINDOW_SECONDS = 60 # ...per 60 seconds

class RateLimiter:
    """Simple sliding window rate limiter."""

    def __init__(
        self,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        time_window: int = DEFAULT_TIME_WINDOW_SECONDS,
    ):
        """Initializes the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window.
            time_window: The time window in seconds.
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.timestamps = deque()
        self._lock = asyncio.Lock()
        logger.info(f"RateLimiter initialized: {max_requests} requests / {time_window} seconds")

    def _cleanup_timestamps(self) -> None:
        """Removes timestamps older than the time window."""
        now = time.monotonic()
        while self.timestamps and now - self.timestamps[0] > self.time_window:
            self.timestamps.popleft()

    async def wait_for_permission(self) -> None:
        """Waits until a request is permitted according to the rate limit."""
        while True:
            async with self._lock:
                self._cleanup_timestamps()
                if len(self.timestamps) < self.max_requests:
                    # Permission granted, record timestamp
                    self.timestamps.append(time.monotonic())
                    logger.debug("Rate limit permission granted.")
                    return # Exit loop
                else:
                    # Calculate wait time
                    oldest_timestamp = self.timestamps[0]
                    wait_time = oldest_timestamp + self.time_window - time.monotonic()
                    wait_time = max(0, wait_time) # Ensure non-negative

            if wait_time > 0:
                 logger.debug(f"Rate limit reached. Waiting for {wait_time:.2f} seconds.")
                 await asyncio.sleep(wait_time)
            # Loop again to re-check condition after waiting

    # Optional: Synchronous check method (use with caution in async code)
    # def can_request_sync(self) -> bool:
    #     with self._lock: # Need appropriate sync lock if used outside async context
    #         self._cleanup_timestamps()
    #         return len(self.timestamps) < self.max_requests

    # Optional: Method to get estimated wait time without waiting
    async def get_wait_time(self) -> float:
         """Estimates the time needed before the next request can be made."""
         async with self._lock:
             self._cleanup_timestamps()
             if len(self.timestamps) < self.max_requests:
                 return 0.0
             else:
                 oldest_timestamp = self.timestamps[0]
                 wait_time = oldest_timestamp + self.time_window - time.monotonic()
                 return max(0.0, wait_time) 