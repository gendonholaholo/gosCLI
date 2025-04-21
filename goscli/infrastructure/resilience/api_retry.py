"""Service for executing API calls with automatic retries.

Implements exponential backoff for handling transient errors like
rate limits (429) or temporary server issues (5xx). Includes fallback
mechanisms (e.g., using cache or switching providers).
"""

import logging
import asyncio
import time
from typing import Any, Callable, Coroutine, Optional, Type, Tuple

# Infrastructure Layer Imports
# from .rate_limiter import RateLimiter
from goscli.infrastructure.resilience.rate_limiter import RateLimiter
# Import CacheService interface for type hint
# from ...domain.interfaces.cache import CacheService
# from ...domain.interfaces.ai_model import AIModel # For provider fallback type hint
from goscli.domain.interfaces.cache import CacheService
from goscli.domain.interfaces.ai_model import AIModel # For provider fallback type hint

# Domain Layer Imports
# from ...domain.models.common import CacheKey
from goscli.domain.models.common import CacheKey
# Import domain events for potential dispatching
# from ...domain.events.api_events import (
#     ApiCallInitiated, ApiCallSucceeded, ApiCallFailed, 
#     ApiCallDeferred, RetryScheduled, GroqApiFallbackTriggered
# )
from goscli.domain.events.api_events import (
    ApiCallInitiated, ApiCallSucceeded, ApiCallFailed, 
    ApiCallDeferred, RetryScheduled, GroqApiFallbackTriggered
)
# TODO: Add generic provider fallback event?
# TODO: Add cache fallback event?

# Define specific exceptions to catch for retries
# Attempt to import from both libraries, falling back to base Exception
try:
    from openai import RateLimitError as OpenAIRateLimitError, APIError as OpenAIAPIError, AuthenticationError as OpenAIAuthenticationError
except ImportError:
    OpenAIRateLimitError = Exception
    OpenAIAPIError = Exception
    OpenAIAuthenticationError = Exception

try:
    from groq import RateLimitError as GroqRateLimitError, APIError as GroqAPIError, AuthenticationError as GroqAuthenticationError
except ImportError:
    GroqRateLimitError = Exception
    GroqAPIError = Exception
    GroqAuthenticationError = Exception

# Combine known retryable/non-retryable errors from providers
# Ensure base Exception is not included if specific types are found
RETRYABLE_EXCEPTIONS = tuple(set(
    e for e in [OpenAIRateLimitError, OpenAIAPIError, GroqRateLimitError, GroqAPIError]
    if e is not Exception
) or (Exception,)) # Fallback to generic Exception if none are imported

NON_RETRYABLE_EXCEPTIONS = tuple(set(
    e for e in [OpenAIAuthenticationError, GroqAuthenticationError, ValueError, TypeError, ImportError]
    if e is not Exception
) or (Exception,)) # Fallback if none are imported

logger = logging.getLogger(__name__)

# --- Custom Exceptions --- 
class MaxRetryError(Exception):
    """Exception raised when max retries are exceeded."""
    def __init__(self, original_exception: Exception, attempts: int):
        self.original_exception = original_exception
        self.attempts = attempts
        super().__init__(f"Max retries ({attempts}) exceeded. Last error: {original_exception}")

# --- Retry Service --- 

class ApiRetryService:
    """Handles API call execution with rate limiting, retries, and fallback."""

    def __init__(
        self,
        rate_limiter: RateLimiter,
        cache_service: Optional[CacheService] = None, # Optional: For cache fallback
        primary_provider_name: str = "openai", # Name of the primary provider being called
        fallback_provider: Optional[AIModel] = None, # Optional: For provider fallback
        fallback_provider_name: Optional[str] = None,
        max_retries: int = 5,
        initial_backoff_s: float = 1.0,
        backoff_factor: float = 2.0,
        # TODO: Load retryable/non-retryable exceptions from config?
    ):
        """Initializes the ApiRetryService.

        Args:
            rate_limiter: The rate limiter instance to use.
            cache_service: Optional cache service for fallback.
            primary_provider_name: Name of the primary provider (for logging/events).
            fallback_provider: Optional alternative AIModel for fallback.
            fallback_provider_name: Name of the fallback provider (for logging/events).
            max_retries: Maximum number of retry attempts.
            initial_backoff_s: Initial delay in seconds for the first retry.
            backoff_factor: Multiplier for the backoff delay (e.g., 2 for exponential).
        """
        self.rate_limiter = rate_limiter
        self.cache_service = cache_service
        self.primary_provider_name = primary_provider_name
        self.fallback_provider = fallback_provider
        self.fallback_provider_name = fallback_provider_name or (fallback_provider.__class__.__name__ if fallback_provider else None)
        self.max_retries = max_retries
        self.initial_backoff_s = initial_backoff_s
        self.backoff_factor = backoff_factor
        self.retryable_exceptions = RETRYABLE_EXCEPTIONS
        self.non_retryable_exceptions = NON_RETRYABLE_EXCEPTIONS

        logger.info(
            f"ApiRetryService initialized: max_retries={max_retries}, "
            f"initial_backoff={initial_backoff_s}s, factor={backoff_factor}, "
            f"Primary='{self.primary_provider_name}', Fallback='{self.fallback_provider_name or 'None'}'"
        )
        logger.debug(f"Retryable Exceptions: {self.retryable_exceptions}")
        logger.debug(f"Non-retryable Exceptions: {self.non_retryable_exceptions}")

    async def execute_with_retry(
        self, 
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        # Add provider_name explicitly for clarity in events/logging
        provider_name: Optional[str] = None,
        endpoint_name: Optional[str] = None, # e.g., 'send_messages', 'list_models'
        cache_key: Optional[CacheKey] = None,
        cache_level: str = 'all',
        use_cache_fallback: bool = True,
        use_provider_fallback: bool = True, # Flag to enable provider fallback
        **kwargs: Any
    ) -> Any:
        """Executes an async function with rate limiting, retries, and fallbacks.

        Args:
            func: The async function (API call) to execute.
            *args: Positional arguments for the function.
            provider_name: Name of the provider being called (defaults to primary).
            endpoint_name: Name of the specific API endpoint/method called.
            cache_key: Optional key to check cache for fallback.
            cache_level: Level(s) to check in cache for fallback.
            use_cache_fallback: Whether to attempt fallback to cache.
            use_provider_fallback: Whether to attempt fallback to another provider.
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of the function call or a fallback result.

        Raises:
            MaxRetryError: If max retries and all fallbacks fail.
            Exception: If a non-retryable exception occurs.
        """
        last_exception: Optional[Exception] = None
        current_backoff = self.initial_backoff_s
        effective_provider_name = provider_name or self.primary_provider_name
        effective_endpoint = endpoint_name or func.__name__

        # TODO: Implement event dispatching (e.g., using a simple dispatcher or library)
        def dispatch_event(event: Any):
            logger.debug(f"EVENT: {event}")
            # In a real system, this would publish the event
            pass

        for attempt in range(self.max_retries + 1):
            try:
                # 1. Wait for rate limit permission
                wait_duration = await self.rate_limiter.get_wait_time()
                if wait_duration > 0:
                     dispatch_event(ApiCallDeferred(provider=effective_provider_name, endpoint=effective_endpoint, wait_time_seconds=wait_duration))
                     await self.rate_limiter.wait_for_permission() # This call now includes the wait
                else:
                    # Still need to acquire the lock/timestamp if no wait needed
                     await self.rate_limiter.wait_for_permission()

                # 2. Execute the function
                dispatch_event(ApiCallInitiated(provider=effective_provider_name, endpoint=effective_endpoint))
                start_time = time.perf_counter()
                result = await func(*args, **kwargs)
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                # Attempt to add latency to the result if it's a StructuredAIResponse
                if hasattr(result, 'latency_ms') and result.latency_ms is None:
                    result.latency_ms = latency_ms
                
                # Extract summary for event (e.g., token usage)
                response_summary = getattr(result, 'token_usage', None) 

                dispatch_event(ApiCallSucceeded(provider=effective_provider_name, endpoint=effective_endpoint, latency_ms=latency_ms, response_summary=response_summary))
                return result

            except self.non_retryable_exceptions as e:
                logger.error(f"Non-retryable error calling {effective_provider_name}.{effective_endpoint} on attempt {attempt + 1}: {e}", exc_info=True)
                dispatch_event(ApiCallFailed(provider=effective_provider_name, endpoint=effective_endpoint, error_type=type(e).__name__, error_message=str(e)))
                raise e # Propagate non-retryable errors immediately

            except self.retryable_exceptions as e:
                last_exception = e
                logger.warning(
                    f"Retryable error calling {effective_provider_name}.{effective_endpoint} on attempt {attempt + 1}/{self.max_retries + 1}: {type(e).__name__}. "
                    f"Waiting {current_backoff:.2f}s..."
                )
                dispatch_event(RetryScheduled(provider=effective_provider_name, endpoint=effective_endpoint, attempt_number=attempt+1, delay_seconds=current_backoff))
                if attempt < self.max_retries:
                    await asyncio.sleep(current_backoff)
                    current_backoff *= self.backoff_factor
                else:
                    logger.error(f"Max retries ({self.max_retries}) reached for {effective_provider_name}.{effective_endpoint}. Last error: {e}")
                    break # Proceed to fallback logic
            except Exception as e:
                # Catch any other unexpected exceptions
                last_exception = e
                logger.error(f"Unexpected error calling {effective_provider_name}.{effective_endpoint} on attempt {attempt + 1}: {e}", exc_info=True)
                # Decide whether to retry unexpected errors or fail fast
                if attempt < self.max_retries:
                     logger.warning(f"Retrying after unexpected error. Waiting {current_backoff:.2f}s...")
                     dispatch_event(RetryScheduled(provider=effective_provider_name, endpoint=effective_endpoint, attempt_number=attempt+1, delay_seconds=current_backoff))
                     await asyncio.sleep(current_backoff)
                     current_backoff *= self.backoff_factor
                else:
                    logger.error(f"Max retries ({self.max_retries}) reached after unexpected error. Last error: {e}")
                    break

        # --- If loop finishes without returning (i.e., max retries exceeded) --- 
        logger.warning(f"Primary API call failed definitively for {effective_provider_name}.{effective_endpoint}. Attempting fallbacks...")

        # 1. Try Cache Fallback
        if use_cache_fallback and self.cache_service and cache_key:
            logger.info(f"Attempting fallback from cache for key: {cache_key}")
            try:
                cached_value = await self.cache_service.get(cache_key, level=cache_level)
                if cached_value is not None:
                    logger.info(f"Cache fallback successful for key: {cache_key}")
                    # dispatch_event(CacheUsedFallback(...))
                    return cached_value
                else:
                    logger.info(f"Cache fallback failed for key: {cache_key} (not found or expired)")
            except Exception as cache_e:
                logger.error(f"Error during cache fallback lookup: {cache_e}", exc_info=True)
                # Continue to provider fallback even if cache lookup fails

        # 2. Try Provider Fallback
        if use_provider_fallback and self.fallback_provider and self.fallback_provider_name:
            logger.warning(f"Attempting fallback from {effective_provider_name} to provider: {self.fallback_provider_name}")
            # Assuming the function/method exists on the fallback provider
            fallback_func = getattr(self.fallback_provider, func.__name__, None)
            if fallback_func and callable(fallback_func):
                 dispatch_event(GroqApiFallbackTriggered( # TODO: Make event generic
                      reason=f"Primary failed: {type(last_exception).__name__}", 
                      fallback_provider=self.fallback_provider_name
                 ))
                 try:
                     # Re-execute the call using the fallback provider, but WITHOUT further retries/fallbacks within this call
                     # Wait for rate limit on fallback provider (assumes same limiter for now)
                     await self.rate_limiter.wait_for_permission()
                     dispatch_event(ApiCallInitiated(provider=self.fallback_provider_name, endpoint=effective_endpoint))
                     start_time = time.perf_counter()
                     fallback_result = await fallback_func(*args, **kwargs)
                     end_time = time.perf_counter()
                     latency_ms = (end_time - start_time) * 1000
                     
                     # Add metadata
                     if hasattr(fallback_result, 'latency_ms') and fallback_result.latency_ms is None:
                          fallback_result.latency_ms = latency_ms
                     if hasattr(fallback_result, 'provider') and fallback_result.provider is None: # If provider is part of response
                          fallback_result.provider = self.fallback_provider_name
                     
                     logger.info(f"Provider fallback to {self.fallback_provider_name} successful.")
                     dispatch_event(ApiCallSucceeded(provider=self.fallback_provider_name, endpoint=effective_endpoint, latency_ms=latency_ms))
                     return fallback_result
                 except Exception as fallback_e:
                     logger.error(f"Provider fallback to {self.fallback_provider_name} failed: {fallback_e}", exc_info=True)
                     dispatch_event(ApiCallFailed(provider=self.fallback_provider_name, endpoint=effective_endpoint, error_type=type(fallback_e).__name__, error_message=str(fallback_e)))
                     # Update last_exception to the fallback error
                     last_exception = fallback_e
            else:
                logger.error(f"Fallback provider {self.fallback_provider_name} does not have method {func.__name__}")

        # If all retries and fallbacks failed
        final_error = last_exception or Exception("Unknown error after retries and fallbacks")
        logger.error(f"All retries and fallbacks failed for {effective_provider_name}.{effective_endpoint}. Raising MaxRetryError.")
        dispatch_event(ApiCallFailed(provider=effective_provider_name, endpoint=effective_endpoint, error_type=type(final_error).__name__, error_message=str(final_error)))
        raise MaxRetryError(final_error, self.max_retries)

# TODO: Add RequestQueueService and BatchingService placeholders/implementations if needed 