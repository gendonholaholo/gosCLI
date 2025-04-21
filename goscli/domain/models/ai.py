"""Domain models related to AI interactions.

Includes structures for AI responses and potentially model representations.
"""

from typing import Dict, List, Optional, TypedDict, Any
from dataclasses import dataclass

from .common import TokenUsage, MessageRole, CoTResult

# --- AI Interaction Structures ---

class ChatMessage(TypedDict):
    """Represents a message structure expected by AI model APIs (like OpenAI)."""
    role: MessageRole
    content: str
    # name: Optional[str] # Optional field for specific APIs

@dataclass
class StructuredAIResponse:
    """Structured response from an AI model, including metadata."""
    content: str
    token_usage: Optional[TokenUsage] = None
    cot_result: Optional[CoTResult] = None
    model_name: Optional[str] = None # Which model generated the response
    latency_ms: Optional[float] = None # Time taken for the API call
    # Add other relevant metadata (e.g., finish reason, error info if partial)

# --- Model Representation (Example) ---

@dataclass
class GroqModel:
    """Entity representing a model available via the Groq API."""
    model_id: str # e.g., "llama3-8b-8192"
    name: str     # User-friendly name
    provider: str = "groq"
    context_window: Optional[int] = None
    # Add other properties like activation status, description, etc.
    # TODO: Define properties based on Groq API response

# TODO: Add models for OpenAI models if needed for registry/selection
# TODO: Define structures for prompt optimization aggregates if complex
# TODO: Define structures for resilient API request aggregates if complex 