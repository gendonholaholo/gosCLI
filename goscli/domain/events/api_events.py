"""Domain Events related to API calls and resilience.

Examples include events for when calls are deferred, retried, fail, or succeed.
"""

from dataclasses import dataclass, field # Added field
import time
from typing import Any, Optional

# Base Event Class (Optional)
@dataclass
class DomainEvent:
    """Base class for domain events."""
    # timestamp: float = field(default_factory=time.time) # Moved to subclasses
    pass # Keep as a marker or remove if no other common logic

# --- Specific API Events ---

@dataclass
class ApiCallInitiated(DomainEvent):
    """Event triggered when an API call is about to be made."""
    provider: str # e.g., 'openai', 'groq'
    endpoint: str
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time) # Moved here

@dataclass
class ApiCallSucceeded(DomainEvent):
    """Event triggered when an API call succeeds."""
    provider: str
    endpoint: str
    latency_ms: float
    request_id: Optional[str] = None
    response_summary: Optional[Any] = None # e.g., token usage
    timestamp: float = field(default_factory=time.time) # Moved here

@dataclass
class ApiCallFailed(DomainEvent):
    """Event triggered when an API call fails definitively (after retries)."""
    provider: str
    endpoint: str
    error_type: str
    error_message: str
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time) # Moved here

@dataclass
class ApiCallDeferred(DomainEvent):
    """Event triggered when an API call is deferred due to rate limiting."""
    provider: str
    endpoint: str
    wait_time_seconds: float
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time) # Moved here

@dataclass
class RetryScheduled(DomainEvent):
    """Event triggered when a retry is scheduled for a failed API call."""
    provider: str
    endpoint: str
    attempt_number: int
    delay_seconds: float
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time) # Moved here

@dataclass
class GroqApiFallbackTriggered(DomainEvent):
    """Event triggered when Groq API fails and fallback to another provider occurs."""
    reason: str # e.g., 'timeout', 'max_retries_exceeded'
    fallback_provider: str # e.g., 'openai'
    original_request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time) # Moved here

# TODO: Add events for BatchExecuted, PromptOptimized, TokenEstimateExceeded etc. 