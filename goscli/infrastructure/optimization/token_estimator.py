"""Service for estimating token counts for text or message lists.

Uses tokenizer libraries (like `tiktoken`) to provide accurate estimations
before sending requests to AI models, helping to prevent exceeding context limits.
Bounded Context: Token Management
"""

import logging
from typing import List, Optional

try:
    import tiktoken
except ImportError:
    tiktoken = None
    logging.getLogger(__name__).warning("tiktoken library not installed. Token estimation will use approximation.")

# Domain Layer Imports
from goscli.domain.models.common import TokenCount, PromptText
from goscli.domain.models.ai import ChatMessage

logger = logging.getLogger(__name__)

# Default tokenizer if tiktoken is available
# TODO: Make this configurable based on the target AI model
DEFAULT_TOKENIZER_MODEL = "cl100k_base" # Common for GPT-3.5/4
APPROX_CHARS_PER_TOKEN = 4 # Fallback approximation

class TokenEstimator:
    """Estimates token counts using tiktoken or approximation."""

    def __init__(self, tokenizer_model_name: Optional[str] = None):
        """Initializes the TokenEstimator."""
        self.tokenizer_name = tokenizer_model_name or DEFAULT_TOKENIZER_MODEL
        self.tokenizer = None
        if tiktoken:
            try:
                self.tokenizer = tiktoken.get_encoding(self.tokenizer_name)
                logger.info(f"TokenEstimator initialized with tiktoken model: {self.tokenizer_name}")
            except Exception as e:
                logger.error(f"Failed to load tiktoken model '{self.tokenizer_name}': {e}. Falling back to approximation.")
        else:
            logger.warning("TokenEstimator using character approximation.")

    def estimate_tokens(self, text: PromptText | str) -> TokenCount:
        """Estimates the token count for a single string of text.

        Args:
            text: The text to estimate tokens for.

        Returns:
            The estimated token count.
        """
        if self.tokenizer:
            try:
                # Ensure text is string
                str_text = str(text)
                if not str_text:
                    return TokenCount(0)
                tokens = self.tokenizer.encode(str_text)
                count = len(tokens)
                logger.debug(f"Estimated tokens for text (len {len(str_text)}): {count} (using {self.tokenizer_name})")
                return TokenCount(count)
            except Exception as e:
                 logger.warning(f"tiktoken encoding failed for text: '{str(text)[:50]}...': {e}. Falling back to approx.")
                 # Fall through to approximation
        
        # Fallback approximation
        str_text = str(text)
        approx_count = len(str_text) // APPROX_CHARS_PER_TOKEN
        logger.debug(f"Estimated tokens for text (len {len(str_text)}): {approx_count} (using approximation)")
        return TokenCount(approx_count)

    def estimate_tokens_for_messages(self, messages: List[ChatMessage]) -> TokenCount:
        """Estimates the token count for a list of ChatMessages.

        Accounts for message structure overhead based on OpenAI's guidelines.
        See: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb

        Args:
            messages: The list of messages.

        Returns:
            The total estimated token count for the message list.
        """
        if not self.tokenizer:
            # Basic approximation for fallback
            total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
            approx_count = total_chars // APPROX_CHARS_PER_TOKEN + (len(messages) * 5) # Rough overhead
            logger.debug(f"Estimated tokens for {len(messages)} messages: {approx_count} (using approximation)")
            return TokenCount(approx_count)

        # Use tiktoken with overhead calculation (example for OpenAI models)
        # TODO: Verify if this overhead applies to Groq models or adjust
        num_tokens = 0
        try:
            for message in messages:
                # Add tokens for message structure overhead
                num_tokens += 4  # Every message follows <im_start>{role/name}\n{content}<im_end>\n
                # Add tokens for message content and role
                for key, value in message.items():
                    content_str = str(value) if value is not None else ""
                    if content_str:
                         num_tokens += len(self.tokenizer.encode(content_str))
                    if key == "name":  # If there's a name, the role is omitted
                        num_tokens -= 1 # Role is always required and always 1 token (remove role estimate)
            
            # Add final tokens for assistant priming
            num_tokens += 2  # Every reply is primed with <im_start>assistant
            
            logger.debug(f"Estimated tokens for {len(messages)} messages: {num_tokens} (using {self.tokenizer_name} + overhead)")
            return TokenCount(num_tokens)
        except Exception as e:
             logger.error(f"Error during detailed token estimation for messages: {e}. Falling back to simple sum.", exc_info=True)
             # Fallback to summing individual message content tokens (less accurate)
             simple_sum = sum(self.estimate_tokens(msg.get('content', '')) for msg in messages)
             return TokenCount(simple_sum)

# TODO: Add methods to estimate based on specific model if tokenization differs significantly 