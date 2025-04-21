"""Concrete implementation of the AIModel interface using the OpenAI API.

Hides the specifics of the OpenAI client library and translates requests/
responses between the domain model and the OpenAI API format.
"""

import logging
import os
import asyncio
import time
from typing import List, Optional, Any, Dict

# Use official openai library
try:
    # Use v1.x library structure
    from openai import OpenAI, RateLimitError, APIError, AuthenticationError, APIResponseValidationError
except ImportError:
    # Handle case where library is not installed, maybe raise config error
    OpenAI = None # type: ignore
    RateLimitError = Exception # type: ignore
    APIError = Exception # type: ignore
    AuthenticationError = Exception # type: ignore
    APIResponseValidationError = Exception # type: ignore
    logging.getLogger(__name__).warning("OpenAI library (v1.x+) not installed. GPTClient will not function.")

# Domain Layer Imports
from goscli.domain.interfaces.ai_model import AIModel
from goscli.domain.models.ai import ChatMessage, StructuredAIResponse, GroqModel # GroqModel for list compatibility?
from goscli.domain.models.common import TokenUsage, CoTResult

logger = logging.getLogger(__name__)

# Map OpenAI finish reasons (can be extended)
FINISH_REASON_MAP = {
    "stop": "stop",
    "length": "length",
    "function_call": "function_call", # If using functions
    "content_filter": "content_filter",
    "tool_calls": "tool_calls",
}

class GptClient(AIModel):
    """OpenAI implementation of the AIModel interface."""

    DEFAULT_MODEL = "gpt-4o-mini" # Or load from config

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initializes the OpenAI client.

        Args:
            api_key: OpenAI API key. Reads from OPENAI_API_KEY env var if None.
            model: The default OpenAI model to use.
        """
        if not OpenAI:
            raise ImportError("OpenAI client library (v1.x+) is required but not installed.")

        effective_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not effective_api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables.")

        try:
            # Consider adding timeout configuration
            self.client = OpenAI(api_key=effective_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI client initialization failed: {e}") from e

        self.model = model or self.DEFAULT_MODEL
        logger.info(f"GptClient initialized for model: {self.model}")

    def _parse_openai_response(self, response: Any) -> StructuredAIResponse:
        """Parses the response object from OpenAI API call."""
        try:
            choice = response.choices[0]
            content = choice.message.content or "" 
            finish_reason = FINISH_REASON_MAP.get(choice.finish_reason, choice.finish_reason) # Map reason

            token_usage = None
            if response.usage:
                token_usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
            
            # TODO: Extract CoT data if implemented via structured output or function calls
            cot_result = None 

            return StructuredAIResponse(
                content=content,
                token_usage=token_usage,
                cot_result=cot_result,
                model_name=response.model, # Get actual model used from response
                # finish_reason=finish_reason # Can add if needed
            )
        except (AttributeError, IndexError, KeyError, TypeError) as e:
             logger.error(f"Failed to parse OpenAI response structure: {e}", exc_info=True)
             logger.debug(f"Raw OpenAI response object: {response}")
             # Raise a specific validation error or return a default/error response
             raise APIResponseValidationError(f"Invalid response structure from OpenAI: {e}") from e

    async def send_messages(self, messages: List[ChatMessage]) -> StructuredAIResponse:
        """Sends messages to the configured OpenAI model asynchronously."""
        logger.debug(f"Sending {len(messages)} messages to OpenAI model: {self.model}")
        start_time = time.perf_counter()
        try:
            # Use asyncio.to_thread for the synchronous SDK call
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                # temperature=0.7, # Example parameter
                # max_tokens=1000 # Example parameter
            )
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            
            structured_response = self._parse_openai_response(response)
            structured_response.latency_ms = latency_ms # Add latency

            logger.debug(f"Received response from OpenAI in {latency_ms:.2f}ms. Usage: {structured_response.token_usage}")
            return structured_response
        
        except AuthenticationError as e:
            logger.error(f"OpenAI Authentication Error: {e}")
            raise # Non-retryable, let ApiRetryService handle propagation
        except RateLimitError as e:
            logger.warning(f"OpenAI Rate Limit Error encountered: {e}")
            raise # Retryable, let ApiRetryService handle retry
        except APIError as e:
            # Includes server errors (5xx), potentially retryable
            logger.warning(f"OpenAI API Error encountered (Status: {e.status_code}): {e}")
            raise # Retryable, let ApiRetryService handle retry
        except APIResponseValidationError as e:
             # If parsing fails, treat as non-retryable for now
             logger.error(f"OpenAI response validation error: {e}")
             raise # Non-retryable
        except Exception as e:
            # Catch-all for other unexpected errors (network, client issues)
            logger.error(f"Unexpected error calling OpenAI: {type(e).__name__} - {e}", exc_info=True)
            # Treat as potentially retryable APIError
            raise APIError(f"Unexpected error: {e}") from e 

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """Lists available models from OpenAI asynchronously."""
        logger.debug("Listing available models from OpenAI.")
        try:
            # Use asyncio.to_thread for the synchronous SDK call
            models_response = await asyncio.to_thread(self.client.models.list)
            
            # Extract relevant data (e.g., id and owner)
            model_list = [
                {"id": model.id, "owned_by": model.owned_by, "provider": "openai"}
                for model in models_response.data 
                if "gpt" in model.id # Simple filter example
            ]
            logger.debug(f"Found {len(model_list)} OpenAI models.")
            return model_list
        except AuthenticationError as e:
             logger.error(f"Authentication failed while listing OpenAI models: {e}")
             raise
        except APIError as e:
             logger.error(f"API error while listing OpenAI models: {e}")
             # Treat as potentially transient? Or just fail?
             return [] # Return empty list on failure for now
        except Exception as e:
            logger.error(f"Failed to list OpenAI models: {e}", exc_info=True)
            return [] # Return empty list on failure 