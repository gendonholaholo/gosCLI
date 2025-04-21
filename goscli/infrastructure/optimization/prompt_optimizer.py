"""Service for optimizing prompt length.

Provides strategies (like truncation, summarization) to reduce the number
of tokens in a list of messages to fit within a specified limit, typically
the context window of an AI model minus a buffer for the response.
Bounded Context: Prompt Optimization
"""

import logging
from typing import List, Optional

# Domain Layer Imports
from goscli.domain.models.ai import ChatMessage
from goscli.domain.models.common import TokenCount

# Infrastructure Layer Imports
from goscli.infrastructure.optimization.token_estimator import TokenEstimator
# from ...domain.interfaces.ai_model import AIModel # Needed for summarization

logger = logging.getLogger(__name__)

class PromptOptimizer:
    """Optimizes message lists to fit within token limits."""

    def __init__(
        self,
        token_estimator: TokenEstimator,
        # ai_model_for_summarization: Optional[AIModel] = None # Inject if using AI for summarization
    ):
        """Initializes the PromptOptimizer.

        Args:
            token_estimator: The estimator used to check token counts during optimization.
            # ai_model_for_summarization: Optional AI model for summarization tasks.
        """
        self.token_estimator = token_estimator
        # self.ai_model_for_summarization = ai_model_for_summarization
        logger.info("PromptOptimizer initialized.")

    def optimize_messages(
        self, messages: List[ChatMessage], max_tokens: TokenCount
    ) -> List[ChatMessage]:
        """Optimizes a list of messages to be at or below max_tokens.

        Current strategy: Simple truncation of oldest messages (excluding system prompt).

        Args:
            messages: The list of ChatMessage dictionaries to optimize.
            max_tokens: The target maximum token count.

        Returns:
            An optimized list of ChatMessage dictionaries.
            Returns an empty list if optimization fails (e.g., target too small).
        """
        # Create a copy to avoid modifying the original list directly
        current_messages = messages[:]
        current_tokens = self.token_estimator.estimate_tokens_for_messages(current_messages)
        logger.debug(f"Optimizing messages: Start tokens={current_tokens}, Target max={max_tokens}")

        if current_tokens <= max_tokens:
            logger.debug("No optimization needed, current tokens within limit.")
            return current_messages # Return the copy

        # --- Simple Truncation Strategy --- 
        system_prompt: Optional[ChatMessage] = None

        # Preserve system prompt if it exists at the beginning
        if current_messages and current_messages[0].get('role') == 'system':
            system_prompt = current_messages.pop(0)
            logger.debug("Preserving system prompt during optimization.")

        # Repeatedly remove the oldest message (index 0 of remaining list) until limit is met
        while current_messages:
            # List to check includes system prompt if it exists
            list_to_check = ([system_prompt] + current_messages) if system_prompt else current_messages
            current_tokens = self.token_estimator.estimate_tokens_for_messages(list_to_check)

            if current_tokens <= max_tokens:
                logger.info(f"Optimization complete via truncation. Final tokens: {current_tokens}")
                return list_to_check
            else:
                # Remove the oldest message (at index 0 of the *mutable* list)
                removed_message = current_messages.pop(0)
                logger.debug(f"Removed message ({removed_message.get('role')}) to reduce tokens. New count (estimated): {current_tokens}")

        # If the loop finishes, only the system prompt might remain
        if system_prompt:
             final_list = [system_prompt]
             final_tokens = self.token_estimator.estimate_tokens_for_messages(final_list)
             if final_tokens <= max_tokens:
                 logger.warning("Optimization removed all non-system messages. Returning only system prompt.")
                 return final_list
        
        # If even the system prompt alone is too long, or no messages remain at all
        logger.error(f"Cannot optimize messages to meet max_tokens={max_tokens}. Minimum possible tokens ({final_tokens if system_prompt else 0}) still exceed limit.")
        # Return empty list to signal failure to optimize sufficiently
        return []

    # --- Potential Future Implementations ---

    # TODO: Implement advanced summarization strategy
    # async def _summarize_messages(self, messages_to_summarize: List[ChatMessage]) -> ChatMessage:
    #     """Uses an AI model to summarize a list of messages."""
    #     if not self.ai_model_for_summarization:
    #         raise RuntimeError("AI model for summarization not configured.")
    #     # Construct prompt for summarization
    #     # Call AI model using retry service
    #     # Return a new ChatMessage with role 'system' or 'assistant' containing the summary
    #     pass

    # TODO: Implement optimization using summarization
    # async def optimize_messages_with_summary(self, messages: List[ChatMessage], max_tokens: TokenCount) -> List[ChatMessage]:
    #     """Optimizes messages using summarization for older parts if truncation isn't enough."""
    #     # 1. Try truncation first
    #     truncated_messages = self.optimize_messages(messages, max_tokens)
    #     current_tokens = self.token_estimator.estimate_tokens_for_messages(truncated_messages)
    #     if current_tokens <= max_tokens:
    #         return truncated_messages
    #
    #     # 2. If still over limit, attempt summarization (more complex)
    #     logger.info("Truncation insufficient, attempting summarization...")
    #     # Identify chunk to summarize (e.g., messages after system prompt, before last N)
    #     # Call self._summarize_messages
    #     # Reconstruct message list with summary
    #     # Re-estimate and potentially truncate further
    #     pass 