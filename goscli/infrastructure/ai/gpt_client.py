import os
import logging
import json # Import json for parsing
from typing import Optional, List, Any # Added Any for cot_result

# Using the official OpenAI client library
from openai import OpenAI, APIError, RateLimitError, AuthenticationError
# Removed tenacity imports as retry is handled externally
# from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Convert to absolute imports
from goscli.domain.interfaces.ai_model import AIModel, StructuredAIResponse, ChatMessage
from goscli.domain.models.common import PromptText, TokenUsage
# from goscli.core.exceptions import AIInteractionError, ConfigurationError # Use built-in if custom failed

# Configure logging for retries
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GptClient(AIModel):
    """Concrete implementation of AIModel using the OpenAI API.
    
    Note: Retry logic is handled externally by ApiRetryService.
    """

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        """Initializes the OpenAI client."""
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            # raise ConfigurationError("OpenAI API key not provided or found in environment variables.")
            raise ValueError("OpenAI API key not provided or found in environment variables.")

        try:
            self.client = OpenAI(api_key=resolved_api_key)
            self.model = model
            logger.info(f"GptClient initialized with model: {self.model}")
        except Exception as e:
            # Catch potential errors during client initialization
            # raise ConfigurationError(f"Failed to initialize OpenAI client: {e}")
             logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
             raise ValueError(f"Failed to initialize OpenAI client: {e}")

    def send_messages(
        self, messages: List[ChatMessage]
    ) -> StructuredAIResponse:
        """Sends a structured list of messages to the configured OpenAI model.
        
        This method performs a single API call attempt.
        Retries and rate limiting should be handled by the caller (e.g., ApiRetryService).
        It also attempts to parse the response for a structured JSON format (e.g., CoT).

        Args:
            messages: The list of messages to send.

        Returns:
            A StructuredAIResponse containing the final content, token usage, and potentially parsed CoT result.

        Raises:
            AuthenticationError: If API key is invalid.
            RateLimitError: If rate limit is hit on this attempt.
            APIError: For other OpenAI API errors.
            RuntimeError: For unexpected errors during the call.
            Exception: Any other exception from the underlying client.
        """
        # Let exceptions propagate up to the ApiRetryService.
        logger.info(f"Attempting to send {len(messages)} messages to OpenAI model: {self.model}")
        
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages
            # Consider adding response_format={"type": "json_object"} if using specific prompts
            # and models that guarantee JSON output.
        )
        logger.info("Received response from OpenAI successfully.")

        raw_response_content = completion.choices[0].message.content
        if raw_response_content is None:
             logger.error("AI model returned an empty response content.")
             # Use a default string instead of raising error here, let QA agent handle it
             raw_response_content = "(AI failed to generate a response)"
             # raise RuntimeError("AI model returned an empty response content.")

        token_usage: Optional[TokenUsage] = None
        if completion.usage:
            try:
                token_usage = TokenUsage({
                    'prompt_tokens': completion.usage.prompt_tokens,
                    'completion_tokens': completion.usage.completion_tokens,
                    'total_tokens': completion.usage.total_tokens
                })
                logger.info(f"Token usage: {token_usage}")
            except Exception as usage_error:
                logger.warning(f"Could not parse token usage from response: {usage_error}")

        # --- Attempt to parse structured response (e.g., JSON with CoT) --- 
        cot_result: Optional[Any] = None
        final_content: str = raw_response_content # Default to raw content

        try:
            # Try to load the raw content as JSON
            parsed_data = json.loads(raw_response_content)
            
            # Check if it's a dictionary and has the expected CoT structure
            if isinstance(parsed_data, dict) and "thought" in parsed_data and "final_answer" in parsed_data:
                cot_result = parsed_data # Store the entire parsed JSON structure
                final_content = str(parsed_data["final_answer"]) # Extract the final answer for direct use
                logger.info("Parsed structured JSON response with 'thought' and 'final_answer'.")
            # else: # Potentially handle other JSON structures if needed
            #    logger.debug("JSON response detected, but not the expected CoT structure.")

        except json.JSONDecodeError:
            # Not JSON, treat as plain text. This is expected for normal responses.
            logger.debug("Response content is not valid JSON, treating as plain text.")
        except Exception as e:
            # Catch other potential errors during parsing (e.g., accessing dict keys)
            logger.warning(f"Error processing potential structured JSON response: {e}")
        # --- End parsing attempt ---

        return StructuredAIResponse(
            content=final_content, # Use the extracted final_answer or the original raw content
            token_usage=token_usage, 
            cot_result=cot_result # Pass the parsed structure (or None)
        )

    # --- Deprecated send_prompt method (commented out or removed) ---
    # def send_prompt(self, prompt: PromptText, context: Optional[AIContext] = None) -> AIResponse:
    #     ... 