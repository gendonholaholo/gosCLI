import time
import logging
import collections
from threading import Lock
from typing import Deque

logger = logging.getLogger(__name__)

# Configuration Constants (from PRD_3.md, adjust as needed)
DEFAULT_MAX_REQUESTS = 60  # Per hour initially, logic uses per minute
DEFAULT_TIMEFRAME_SECONDS = 60 * 60 # 1 hour
# Let's refine this to be per minute for easier calculation within the class
DEFAULT_MAX_REQUESTS_PER_MINUTE = 5 # Aligns with burst allowance mention
DEFAULT_MINUTE_TIMEFRAME = 60

class RateLimiter:
    """Manages API request rate limiting using a sliding window approach."""

    def __init__(self,
                 max_requests: int = DEFAULT_MAX_REQUESTS_PER_MINUTE,
                 timeframe_seconds: int = DEFAULT_MINUTE_TIMEFRAME):
        """Initializes the RateLimiter.

        Args:
            max_requests: Maximum number of requests allowed within the timeframe.
            timeframe_seconds: The duration of the sliding window in seconds.
        """
        if max_requests <= 0 or timeframe_seconds <= 0:
            raise ValueError("Max requests and timeframe must be positive.")
            
        self.max_requests = max_requests
        self.timeframe = timeframe_seconds
        # Use a deque to efficiently store timestamps and remove old ones
        self.timestamps: Deque[float] = collections.deque()
        self._lock = Lock() # Thread safety for timestamp access
        logger.info(f"RateLimiter initialized: Max {self.max_requests} requests / {self.timeframe} seconds.")

    def _prune_timestamps(self, current_time: float) -> None:
        """Removes timestamps older than the defined timeframe."""
        # Remove timestamps older than current_time - timeframe
        while self.timestamps and self.timestamps[0] <= current_time - self.timeframe:
            self.timestamps.popleft()

    def can_request(self) -> bool:
        """Checks if a request can be made without exceeding the limit."""
        with self._lock:
            now = time.monotonic() # Use monotonic clock for duration
            self._prune_timestamps(now)
            can_make_request = len(self.timestamps) < self.max_requests
            # logger.debug(f"Rate limit check: Current count={len(self.timestamps)}, Max={self.max_requests}. Allowed: {can_make_request}")
            return can_make_request

    def record_request(self) -> None:
        """Records the timestamp of a successful request."""
        with self._lock:
            now = time.monotonic()
            self._prune_timestamps(now)
            if len(self.timestamps) < self.max_requests:
                self.timestamps.append(now)
                # logger.debug(f"Request recorded at {now}. Current count: {len(self.timestamps)}")
            else:
                # This shouldn't happen if can_request() is checked first, but log if it does
                logger.warning("Attempted to record request while already at limit.")

    def wait_time(self) -> float:
        """Calculates the time (in seconds) to wait until the next request can be made.
        
        Returns 0 if a request can be made immediately.
        """
        with self._lock:
            now = time.monotonic()
            self._prune_timestamps(now)
            
            if len(self.timestamps) < self.max_requests:
                return 0.0 # Can request immediately
            
            # If limit is reached, calculate wait time based on the oldest timestamp 
            # within the current window that needs to expire.
            oldest_relevant_timestamp = self.timestamps[0] # The one that needs to slide out
            time_passed_since_oldest = now - oldest_relevant_timestamp
            wait_needed = self.timeframe - time_passed_since_oldest
            
            # Add a small buffer to avoid race conditions
            wait_needed += 0.01 
            
            logger.debug(f"Rate limit reached. Wait time calculated: {wait_needed:.2f} seconds.")
            return max(0.0, wait_needed) # Ensure non-negative wait time 