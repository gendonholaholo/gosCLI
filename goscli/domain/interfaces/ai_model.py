"""Interface for AI Language Models (LLMs).

Defines the contract for sending messages or prompts to different
AI providers (e.g., OpenAI GPT, Groq Llama).
"""

import abc
from typing import List, Optional, Any

# Import relevant domain models
from ..models.ai import ChatMessage, StructuredAIResponse, GroqModel
# from ..models.common import PromptText # If send_prompt were kept


class AIModel(abc.ABC):
    """Abstract Base Class for AI language model interactions."""

    @abc.abstractmethod
    async def send_messages(self, messages: List[ChatMessage]) -> StructuredAIResponse:
        """Sends a list of messages (conversation history) to the AI model asynchronously.

        Args:
            messages: A list of ChatMessage objects representing the conversation.

        Returns:
            A StructuredAIResponse containing the AI's reply and metadata.

        Raises:
            # TODO: Define specific exceptions (e.g., AuthenticationError, APIError)
            Exception: If the API call fails.
        """
        pass

    @abc.abstractmethod
    async def list_available_models(
        self,
    ) -> List[Any]:  # Return type depends on provider (e.g., List[GroqModel])
        """Lists the models available from this provider asynchronously.

        Returns:
            A list of available models (structure may vary by provider).

        Raises:
            Exception: If listing models fails.
        """
        pass

    # Optional: Add methods for streaming responses if needed
    # @abc.abstractmethod
    # async def stream_messages(self, messages: List[ChatMessage]) -> AsyncIterator[StructuredAIResponse]:
    #     """Streams the AI response chunk by chunk."""
    #     pass

    # Deprecated: Keep commented out or remove fully
    # @abc.abstractmethod
    # def send_prompt(self, prompt: PromptText, context: Optional[str] = None) -> str:
    #     """(Deprecated) Sends a single prompt."""
    #     pass

