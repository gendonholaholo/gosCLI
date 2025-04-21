"""Concrete implementation of the AIModel interface using the Groq API.

Hides the specifics of the Groq client library and translates requests/
responses between the domain model and the Groq API format.
"""

import logging
import os
import asyncio
import time
from typing import List, Optional, Any

# Use official groq library
try:
    from groq import Groq as GroqSDKClient, RateLimitError, APIError, AuthenticationError, APIResponseValidationError
except ImportError:
    GroqSDKClient = None # type: ignore
    RateLimitError = Exception # type: ignore
    APIError = Exception # type: ignore
    AuthenticationError = Exception # type: ignore
    APIResponseValidationError = Exception # type: ignore
    logging.getLogger(__name__).warning("Groq library not installed. GroqClient will not function.")

# Domain Layer Imports
from goscli.domain.interfaces.ai_model import AIModel
from goscli.domain.models.ai import ChatMessage, StructuredAIResponse, GroqModel
from goscli.domain.models.common import TokenUsage, CoTResult

logger = logging.getLogger(__name__)

class GroqClient(AIModel):
    """Groq implementation of the AIModel interface."""

    DEFAULT_MODEL = "llama3-70b-8192" # Or load from config

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initializes the Groq client.

        Args:
            api_key: Groq API key. Reads from GROQ_API_KEY env var if None.
            model: The default Groq model to use.
        """
        if not GroqSDKClient:
             raise ImportError("Groq client library is required but not installed.")

        effective_api_key = api_key or os.getenv("GROQ_API_KEY")
        if not effective_api_key:
            raise ValueError("Groq API key not provided and not found in environment variables.")

        try:
            # TODO: Explore async client if/when available in the SDK
            # Consider adding timeout configuration
            self.client = GroqSDKClient(api_key=effective_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}", exc_info=True)
            raise RuntimeError(f"Groq client initialization failed: {e}") from e

        self.model = model or self.DEFAULT_MODEL
        logger.info(f"GroqClient initialized for model: {self.model}")

    def _parse_groq_response(self, response: Any) -> StructuredAIResponse:
        """Parses the response object from Groq API call."""
        try:
            choice = response.choices[0]
            content = choice.message.content or ""
            # Groq finish reasons might differ, map if necessary
            # finish_reason = choice.finish_reason

            token_usage = None
            if response.usage:
                # Map Groq's usage structure to our domain model
                token_usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
            
            cot_result = None # TODO: Extract CoT if applicable

            return StructuredAIResponse(
                content=content,
                token_usage=token_usage,
                cot_result=cot_result,
                model_name=response.model, # Get actual model used
                # finish_reason=finish_reason
            )
        except (AttributeError, IndexError, KeyError, TypeError) as e:
             logger.error(f"Failed to parse Groq response structure: {e}", exc_info=True)
             logger.debug(f"Raw Groq response object: {response}")
             raise APIResponseValidationError(f"Invalid response structure from Groq: {e}") from e

    async def send_messages(self, messages: List[ChatMessage]) -> StructuredAIResponse:
        """Sends messages to the configured Groq model asynchronously."""
        logger.debug(f"Sending {len(messages)} messages to Groq model: {self.model}")
        start_time = time.perf_counter()
        try:
            # Use asyncio.to_thread as the official Groq SDK is synchronous
            chat_completion = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=messages,
                model=self.model,
                # temperature=0.7, # Example Groq parameter
                # max_tokens=1000  # Example Groq parameter
            )
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            structured_response = self._parse_groq_response(chat_completion)
            structured_response.latency_ms = latency_ms # Add latency
            
            logger.debug(f"Received response from Groq in {latency_ms:.2f}ms. Usage: {structured_response.token_usage}")
            return structured_response
        
        except AuthenticationError as e:
            logger.error(f"Groq Authentication Error: {e}")
            raise # Non-retryable
        except RateLimitError as e:
            logger.warning(f"Groq Rate Limit Error encountered: {e}")
            raise # Retryable
        except APIError as e:
            # Includes server errors (5xx), potentially retryable
            logger.warning(f"Groq API Error encountered (Status: {getattr(e, 'status_code', 'N/A' )}): {e}")
            raise # Retryable
        except APIResponseValidationError as e:
             logger.error(f"Groq response validation error: {e}")
             raise # Non-retryable
        except Exception as e:
            logger.error(f"Unexpected error calling Groq: {type(e).__name__} - {e}", exc_info=True)
            # Treat as potentially retryable APIError
            raise APIError(f"Unexpected error: {e}") from e

    async def list_available_models(self) -> List[GroqModel]:
        """Lists available models from Groq asynchronously."""
        logger.debug("Listing available models from Groq.")
        try:
            # Use asyncio.to_thread for the synchronous SDK call
            models_response = await asyncio.to_thread(self.client.models.list)
            model_list_data = models_response.data if models_response and models_response.data else []

            # Map the response to List[GroqModel]
            groq_models = []
            for model_data in model_list_data:
                 try:
                     # Attempt to extract relevant fields, handle missing ones gracefully
                     model_id = getattr(model_data, 'id', 'unknown')
                     name = getattr(model_data, 'id', 'Unknown Name') # Use ID if name not present
                     # context_window = getattr(model_data, 'context_window', None) # Check SDK attributes
                     groq_models.append(
                         GroqModel(
                            model_id=model_id,
                            name=name,
                            # context_window=context_window,
                            provider="groq"
                        )
                     )
                 except Exception as parse_e:
                      logger.warning(f"Failed to parse individual Groq model data: {model_data}. Error: {parse_e}")
            
            logger.debug(f"Found {len(groq_models)} Groq models.")
            return groq_models
        except AuthenticationError as e:
             logger.error(f"Authentication failed while listing Groq models: {e}")
             raise
        except APIError as e:
             logger.error(f"API error while listing Groq models: {e}")
             return [] # Return empty list on failure
        except Exception as e:
            logger.error(f"Failed to list Groq models: {e}", exc_info=True)
            return [] # Return empty list on failure 