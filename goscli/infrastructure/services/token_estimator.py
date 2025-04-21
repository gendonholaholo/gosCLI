import logging
import tiktoken
from typing import List, Dict, Any

# Convert to absolute imports
from goscli.domain.models.common import TokenCount, MessageRole
from goscli.domain.interfaces.ai_model import ChatMessage

logger = logging.getLogger(__name__)

# Centralized Tokenizer Configuration
TOKENIZER_MODEL = "cl100k_base" # Common for GPT-3.5/4/4o

try:
    tokenizer = tiktoken.get_encoding(TOKENIZER_MODEL)
    logger.info(f"Initialized tokenizer: {TOKENIZER_MODEL}")
except Exception as e:
    logger.error(f"Failed to initialize tokenizer '{TOKENIZER_MODEL}'. Token counts will use approximation: {e}")
    tokenizer = None

# Approximation fallback
APPROX_CHARS_PER_TOKEN = 4

class TokenEstimator:
    """Provides methods for estimating token counts using tiktoken with fallback."""

    def estimate_tokens_for_text(self, text: str) -> TokenCount:
        """Estimates token count for a single string."""
        if tokenizer:
            try:
                return TokenCount(len(tokenizer.encode(text)))
            except Exception as e:
                logger.warning(f"Tiktoken text encoding failed: {e}. Falling back to char approx.")
        # Fallback
        return TokenCount(len(text) // APPROX_CHARS_PER_TOKEN)

    def estimate_tokens_for_messages(self, messages: List[ChatMessage]) -> TokenCount:
        """Estimates the total token count for a list of messages.
        
        Approximates OpenAI's billing logic (adds tokens per message + content tokens).
        Ref: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        """
        if not tokenizer:
            logger.warning("Tokenizer unavailable. Using rough character approximation for message list.")
            total_chars = sum(len(msg['content']) for msg in messages)
            # Very rough estimate adding some overhead per message
            return TokenCount((total_chars // APPROX_CHARS_PER_TOKEN) + (len(messages) * 5))

        num_tokens = 0
        # Simplified logic based on cookbook examples for gpt-3.5/4
        # Each message adds ~4 tokens for overhead (role, content markers)
        tokens_per_message = 4 
        tokens_per_name = -1 # Adjust if using 'name' field in messages

        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                try:
                    num_tokens += len(tokenizer.encode(value))
                except Exception as e:
                    logger.warning(f"Tiktoken message part encoding failed: {e}. Using char approx for part.")
                    num_tokens += len(value) // APPROX_CHARS_PER_TOKEN
                # if key == "name": # Account for name field if used
                #     num_tokens += tokens_per_name
        
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return TokenCount(num_tokens)

    # --- Potentially add methods for specific models if needed --- 