"""Defines common Value Objects used across different domain contexts.

These objects represent simple values or concepts like file paths, prompts,
token counts, etc., ensuring consistency and type safety.
"""

from typing import NewType, List, Tuple, Any, Dict, TypedDict, Optional

# === Core Value Objects ===

# Using NewType for semantic clarity, although they are strings at runtime.
FilePath = NewType("FilePath", str)           # Path to a file
FileContent = NewType("FileContent", str)       # Full content of a file
PromptText = NewType("PromptText", str)        # User's text prompt
AIResponse = NewType("AIResponse", str)        # Raw response from AI model
ProcessedOutput = NewType("ProcessedOutput", str) # Output after agent processing

# === File System Context ===
SearchCriteria = NewType("SearchCriteria", str)  # Simple glob pattern for now
FileChunk = NewType("FileChunk", str)            # A chunk of a large file
FileFingerprint = NewType("FileFingerprint", str) # Hash (e.g., SHA1) of file content

# === AI Interaction & CoT Context ===
AIContext = NewType("AIContext", str)            # Context string for AI (e.g., history, file chunk)
CoTStep = NewType("CoTStep", Dict[str, Any])    # Represents one step in Chain of Thought reasoning
                                               # Example: {'step': 1, 'action': 'Analyze Header', 'result': '...'}
CoTResult = NewType("CoTResult", List[CoTStep]) # The full chain of thought steps

# === Caching Context ===
CacheKey = NewType("CacheKey", str)              # Unique key for a cache entry
CachePrefix = NewType("CachePrefix", str)      # Prefix for categorizing cache keys (e.g., 'analysis')

# === Thread Management Context ===
MessageRole = NewType("MessageRole", str)      # 'user', 'ai', 'system'
ThreadID = NewType("ThreadID", str)            # Unique ID for a chat thread
ThreadSummary = NewType("ThreadSummary", str)    # Summarized version of chat history

# === Token Management ===
TokenCount = NewType("TokenCount", int)        # Number of tokens
TokenUsage = NewType("TokenUsage", Dict[str, TokenCount]) # Record of token usage 
                                                         # Example: {'prompt_tokens': 100, 'completion_tokens': 250, 'total_tokens': 350}

# === Function Execution Context === 
FunctionName = NewType("FunctionName", str)
FunctionParameters = NewType("FunctionParameters", Dict[str, Any])
FunctionResult = NewType("FunctionResult", Any)

# --- Structured Data ---
class TokenUsage(TypedDict):
    """Represents token usage information from an AI call."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class CoTResult(TypedDict):
    """Represents Chain-of-Thought results (optional)."""
    thought: Optional[str]
    steps: Optional[list[str]]
    # Add other relevant CoT fields as needed

class GroqApiKey(TypedDict):
    """Value Object for securely handling Groq API Key (placeholder)."""
    # TODO: Implement secure handling, maybe not a plain TypedDict
    key: str

class BackoffPolicy(TypedDict):
    """Value Object representing retry backoff configuration."""
    max_retries: int
    initial_delay: float
    factor: float

# --- Aggregates/Complex Structures (Example) ---
class QueueItem(TypedDict):
    """Represents an item in the request queue."""
    request_id: str
    priority: int
    payload: Any # The actual request data
    timestamp: float

# TODO: Add other common models as needed (e.g., Error types) 