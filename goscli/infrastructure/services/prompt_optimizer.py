import logging
from typing import List, Optional

# Convert to absolute imports
from goscli.domain.interfaces.ai_model import ChatMessage
from goscli.domain.models.common import TokenCount
from goscli.infrastructure.services.token_estimator import TokenEstimator

logger = logging.getLogger(__name__)

class PromptOptimizer:
    """Optimizes prompts (message lists) to fit within token limits."""

    def __init__(self, token_estimator: TokenEstimator):
        """Initializes the PromptOptimizer.
        
        Args:
            token_estimator: The service used to estimate token counts.
        """
        self.token_estimator = token_estimator

    def optimize_messages(self, 
                          messages: List[ChatMessage], 
                          max_tokens: TokenCount
                          ) -> List[ChatMessage]:
        """Reduces the message list to fit within the max_tokens limit.
        
        Current strategy: Remove oldest messages (excluding system prompt if present).
        TODO: Implement more sophisticated strategies like summarization.

        Args:
            messages: The original list of messages.
            max_tokens: The maximum allowed token count for the list.

        Returns:
            An optimized list of messages that fits the token limit.
        """
        estimated_tokens = self.token_estimator.estimate_tokens_for_messages(messages)
        
        if estimated_tokens <= max_tokens:
            logger.debug(f"Message list token count ({estimated_tokens}) is within limit ({max_tokens}). No optimization needed.")
            return messages # No optimization needed

        logger.warning(f"Message list ({estimated_tokens} tokens) exceeds limit ({max_tokens}). Optimizing...")
        
        optimized_messages: List[ChatMessage] = []
        current_tokens = TokenCount(0)
        system_prompt: Optional[ChatMessage] = None

        # Preserve system prompt if it exists at the beginning
        if messages and messages[0]['role'] == 'system':
            system_prompt = messages[0]
            current_tokens = self.token_estimator.estimate_tokens_for_messages([system_prompt])
            # Remove it from the main list for processing
            messages = messages[1:] 

        # Iterate backwards from the most recent message
        for message in reversed(messages):
            message_tokens = self.token_estimator.estimate_tokens_for_messages([message]) # Estimate single msg cost
            
            # Check if adding this message (plus system prompt if applicable) exceeds the limit
            potential_total = current_tokens + message_tokens
            if system_prompt:
                 # Re-add system prompt tokens if it wasn't accounted for yet
                 # Note: estimate_tokens_for_messages adds overhead, so this is approximate
                 if not optimized_messages: # Only add system prompt cost once
                      potential_total += self.token_estimator.estimate_tokens_for_messages([system_prompt])
            
            if potential_total <= max_tokens:
                optimized_messages.append(message)
                current_tokens += message_tokens
            else:
                # Stop adding messages once the limit is reached
                logger.debug(f"Stopping message inclusion at limit ({current_tokens} tokens).")
                break 
        
        # Add system prompt back to the beginning if it exists
        if system_prompt:
             optimized_messages.append(system_prompt)
        
        # Reverse to restore chronological order
        optimized_messages.reverse()
        final_token_count = self.token_estimator.estimate_tokens_for_messages(optimized_messages)
        logger.info(f"Optimized message list contains {len(optimized_messages)} messages, {final_token_count} tokens (Limit: {max_tokens}).")
        
        if not optimized_messages or (len(optimized_messages) == 1 and optimized_messages[0]['role'] == 'system'):
             logger.warning("Optimization resulted in no user/assistant messages being included.")
             # Decide on behavior: return empty list? return just system prompt? Raise error?
             # For now, return potentially just the system prompt or empty list.

        return optimized_messages

    # TODO: Implement summarization method
    # def summarize_messages(self, messages: List[ChatMessage], target_token_count: TokenCount) -> List[ChatMessage]:
    #     pass 