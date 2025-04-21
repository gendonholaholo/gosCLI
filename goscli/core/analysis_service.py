import logging
from typing import List, Iterator, Optional

import tiktoken  # Added for token counting

from goscli.domain.interfaces.ai_model import (
    AIModel,
    ChatMessage,
    StructuredAIResponse,
)  # Added ChatMessage, StructuredAIResponse

from goscli.domain.interfaces.file_system import FileSystem

from goscli.domain.interfaces.user_interface import (
    UserInterface,
)  # For displaying results

from goscli.domain.models.common import (
    FilePath,
    PromptText,
    FileContent,
    FileChunk,
    FileFingerprint,
    # AIContext,
    # AIResponse,
    ProcessedOutput,
)

# Import CachingService and fingerprint generator
from goscli.infrastructure.services.caching_service import (
    CachingService,
    generate_file_fingerprint,
)

# Import ApiRetryService
from goscli.infrastructure.services.api_retry import (
    ApiRetryService,
    MaxRetryError,
    AuthenticationError,
)

# Use built-in if custom failed
# from goscli.core.exceptions import FileOperationError, AIInteractionError

# Import QA Agent
from goscli.infrastructure.agents.qa_agent import QualityAssuranceAgent

from openai import RateLimitError

logger = logging.getLogger(__name__)

# --- Constants ---
# Target chunk size in tokens (from PRD_2.md)
TARGET_CHUNK_TOKENS = 4000
# Overlap size in tokens (from PRD_2.md)
CHUNK_OVERLAP_TOKENS = 100
# Model used for tokenization (should match the AI model if possible)
# Using cl100k_base as it's common for gpt-4, gpt-3.5 etc.
TOKENIZER_MODEL = "cl100k_base"

# Initialize tokenizer globally once (or within __init__ if model might change)
try:
    tokenizer = tiktoken.get_encoding(TOKENIZER_MODEL)
except Exception as e:
    logger.error(
        f"Failed to initialize tokenizer '{TOKENIZER_MODEL}'. Chunking might be inaccurate: {e}"
    )
    tokenizer = None  # Fallback or raise error


class AnalysisService:
    """Handles the logic for analyzing a file based on a user prompt.

    Incorporates caching and file chunking for large files.
    """

    def __init__(
        self,
        file_system: FileSystem,
        ai_model: AIModel,
        qa_agent: QualityAssuranceAgent,  # Use QA Agent
        ui: UserInterface,
        cache_service: CachingService,  # Inject CachingService
        api_retry_service: ApiRetryService,  # Inject ApiRetryService
    ):
        """Initializes the AnalysisService.

        Args:
            file_system: An instance implementing the FileSystem interface.
            ai_model: An instance implementing the AIModel interface.
            qa_agent: An instance of QualityAssuranceAgent.
            ui: An instance implementing the UserInterface interface.
            cache_service: An instance of CachingService.
            api_retry_service: An instance of ApiRetryService.
        """
        self.file_system = file_system
        self.ai_model = ai_model
        self.qa_agent = qa_agent  # Store QA Agent
        self.ui = ui
        self.cache_service = cache_service  # Store cache service instance
        self.api_retry_service = api_retry_service  # Store retry service

    def _get_token_count(self, text: str) -> int:
        """Estimates the token count for a given text using tiktoken."""
        if tokenizer:
            try:
                return len(tokenizer.encode(text))
            except Exception as e:
                logger.warning(
                    f"Tiktoken encoding failed: {e}. Falling back to character approximation."
                )
        # Fallback to character approximation if tokenizer failed
        return len(text) // 4  # Simple fallback

    def _chunk_content(self, content: FileContent) -> Iterator[FileChunk]:
        """Splits file content into manageable chunks with overlap using tiktoken.

        Yields chunks one by one.
        """
        # Tokenize the entire content once
        if not tokenizer:
            logger.warning("Tokenizer not available. Using character-based chunking.")
            # Fallback to previous character based logic (simplified here)
            content_len = len(content)
            if content_len <= TARGET_CHUNK_TOKENS * 4:
                yield FileChunk(content)
                return
            # Simplified char based chunking for fallback
            # Production code might replicate the previous char logic more closely
            for i in range(
                0, content_len, TARGET_CHUNK_TOKENS * 4 - CHUNK_OVERLAP_TOKENS * 4
            ):
                yield FileChunk(content[i : i + TARGET_CHUNK_TOKENS * 4])
            return

        try:
            tokens = tokenizer.encode(content)
        except Exception as e:
            logger.error(
                f"Failed to tokenize content with tiktoken: {e}. Cannot perform token-based chunking."
            )
            # Potentially fallback to character chunking or raise an error
            # For now, let's return the whole content as one chunk to avoid complex fallbacks
            yield FileChunk(content)
            return

        total_tokens = len(tokens)
        logger.info(f"Total tokens in content: {total_tokens}")

        if total_tokens <= TARGET_CHUNK_TOKENS:
            logger.debug("Content token count is within target chunk size.")
            yield FileChunk(content)  # No chunking needed
            return

        logger.info(
            f"Content token count ({total_tokens}) exceeds target size. Chunking..."
        )
        start_token_index = 0
        chunk_num = 1
        while start_token_index < total_tokens:
            end_token_index = min(start_token_index + TARGET_CHUNK_TOKENS, total_tokens)

            # Decode the token slice back to text
            try:
                chunk_tokens = tokens[start_token_index:end_token_index]
                chunk_text = tokenizer.decode(chunk_tokens)
            except Exception as e:
                logger.error(
                    f"Failed to decode tokens for chunk {chunk_num}: {e}. Skipping chunk."
                )
                # Move to next potential chunk start to avoid getting stuck
                start_token_index += TARGET_CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS
                continue  # Skip this problematic chunk

            logger.debug(
                f"Yielding chunk {chunk_num} (tokens {start_token_index}-{end_token_index}) size: {len(chunk_tokens)} tokens"
            )
            yield FileChunk(chunk_text)

            # Move start index for the next chunk, considering overlap in tokens
            next_start_index = (
                start_token_index + TARGET_CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS
            )

            # Prevent infinite loops if overlap calculation doesn't advance
            if next_start_index <= start_token_index:
                if end_token_index < total_tokens:
                    # Forcefully advance past the current chunk if stuck and not at the end
                    next_start_index = end_token_index
                else:
                    break  # Reached the end

            start_token_index = next_start_index
            chunk_num += 1

        logger.info("Finished token-based chunking content.")

    async def _call_ai_with_retry(
        self, messages: List[ChatMessage], cache_prefix: str, cache_key_args: tuple
    ) -> Optional[StructuredAIResponse]:  # Return Optional
        """Helper to call the AI model via the retry service, providing cache info."""
        try:
            # Pass cache info for fallback
            response = await self.api_retry_service.execute_with_retry(
                self.ai_model.send_messages,
                messages=messages,
                cache_prefix=cache_prefix,
                cache_key_args=cache_key_args,
                # No cache_key_kwargs needed for analysis cache structure
            )
            return response  # Could be None if cache fallback occurred but returned None (unlikely for put)
        # Or could be the cached value itself (needs type check potentially)
        except MaxRetryError as e:
            logger.error(
                f"API call failed permanently after retries and cache fallback attempt: {e.original_exception}"
            )
            # Decide how to handle permanent failure - re-raise, return None, specific error?
            # Returning None from here signals failure to _get_analysis_from_ai
            return None
        except (AuthenticationError, RateLimitError) as e:
            # Handle non-retryable or already-handled rate limit errors
            logger.error(f"API call failed due to non-retryable error: {e}")
            raise e  # Re-raise for higher level handling

    async def _get_analysis_from_ai(
        self,
        file_path: FilePath,
        prompt: PromptText,
        file_content: FileContent,
        file_fingerprint: Optional[FileFingerprint],
    ) -> Optional[ProcessedOutput]:  # Return Optional
        """Performs AI analysis, handling chunking, caching, and potential fallback."""
        chunks = list(self._chunk_content(file_content))
        num_chunks = len(chunks)

        if num_chunks == 1:
            chunk = chunks[0]
            cache_prefix = "analysis_single_chunk_v2"
            cache_key_args = (file_fingerprint, prompt) if file_fingerprint else None

            # Check cache first (standard check)
            if file_fingerprint:
                cached_result: Optional[ProcessedOutput] = self.cache_service.get(
                    cache_prefix, *cache_key_args
                )
                if cached_result is not None:
                    self.ui.display_info(
                        "Retrieved full analysis from cache (single chunk)."
                    )
                    return cached_result

            self.ui.display_info(
                "Analyzing single chunk (cache miss or no fingerprint)..."
            )
            messages: List[ChatMessage] = [
                {
                    "role": "system",
                    "content": f"Analyze file '{file_path}'. Content:\n{chunk}",
                },
                {"role": "user", "content": prompt},
            ]

            # Call AI via retry service (providing cache info for fallback)
            structured_response = await self._call_ai_with_retry(
                messages, cache_prefix, cache_key_args or ()
            )

            if (
                structured_response is None
            ):  # Indicates permanent failure after retries & fallback
                self.ui.display_error(
                    "Failed to get analysis from AI after retries and cache check."
                )
                return None

            # Process successful response (could be from API or cache fallback)
            # If it came from cache fallback, it might already be ProcessedOutput
            # Let QA Agent handle StructuredAIResponse or potentially pre-processed string? Adapt QA agent.
            # Assuming QA agent handles StructuredAIResponse for now.
            if isinstance(structured_response, StructuredAIResponse):
                processed_response = self.qa_agent.process_response(structured_response)
                # Store processed response in cache if it came from API
                if file_fingerprint:
                    # Only store if it wasn't a cache hit initially or from fallback
                    # The retry service doesn't explicitly tell us if it used fallback,
                    # so we might overwrite cache unnecessarily. A better signal is needed.
                    # For now, let's assume we always cache the final processed result.
                    self.cache_service.put(
                        processed_response, cache_prefix, *cache_key_args
                    )
                return processed_response
            else:
                # Handle case where fallback returned something unexpected (or already processed string?)
                logger.warning(
                    "Received unexpected type from _call_ai_with_retry, potentially pre-processed cache value."
                )
                # Assuming the fallback returns ProcessedOutput string directly
                return ProcessedOutput(str(structured_response))

        else:  # Multiple chunks
            self.ui.display_info(f"Analyzing content in {num_chunks} chunks...")
            all_chunk_outputs: List[ProcessedOutput] = []
            cache_prefix = "analysis_chunk_v2"

            for i, chunk in enumerate(chunks):
                chunk_num = i + 1
                self.ui.display_info(f"Processing chunk {chunk_num}/{num_chunks}...")
                chunk_processed_output: Optional[ProcessedOutput] = None
                chunk_cache_key_args = (
                    (file_fingerprint, prompt, chunk_num) if file_fingerprint else None
                )

                # Check cache first
                if chunk_cache_key_args:
                    cached_chunk_result = self.cache_service.get(
                        cache_prefix, *chunk_cache_key_args
                    )
                    if cached_chunk_result is not None:
                        self.ui.display_info(
                            f"Retrieved chunk {chunk_num} analysis from cache."
                        )
                        chunk_processed_output = ProcessedOutput(cached_chunk_result)

                if chunk_processed_output is None:
                    self.ui.display_info(
                        f"Cache miss for chunk {chunk_num}. Sending to AI..."
                    )
                    messages: List[ChatMessage] = [
                        {
                            "role": "system",
                            "content": f"Analyze chunk {chunk_num}/{num_chunks} of '{file_path}'. Content:\n{chunk}",
                        },
                        {"role": "user", "content": f"Regarding this chunk, {prompt}"},
                    ]

                    # Call AI via retry service (providing cache info)
                    structured_response = await self._call_ai_with_retry(
                        messages, cache_prefix, chunk_cache_key_args or ()
                    )

                    if structured_response is None:  # Permanent failure for this chunk
                        self.ui.display_error(
                            f"Failed to get analysis for chunk {chunk_num} after retries."
                        )
                        # Decide how to proceed: skip chunk, use placeholder, stop entirely?
                        # Let's use a placeholder for now.
                        chunk_processed_output = ProcessedOutput(
                            f"(Analysis failed for chunk {chunk_num})"
                        )
                    elif isinstance(structured_response, StructuredAIResponse):
                        chunk_processed_output = self.qa_agent.process_response(
                            structured_response
                        )
                        if chunk_cache_key_args:
                            self.cache_service.put(
                                chunk_processed_output,
                                cache_prefix,
                                *chunk_cache_key_args,
                            )
                            self.ui.display_info(
                                f"Stored chunk {chunk_num} analysis in cache."
                            )
                    else:
                        # Fallback likely returned ProcessedOutput string
                        chunk_processed_output = ProcessedOutput(
                            str(structured_response)
                        )

                all_chunk_outputs.append(chunk_processed_output)

            self.ui.display_info("Aggregating results from all chunks...")
            aggregated_result = "\n\n---\n\n".join(
                f"[Chunk {i + 1}/{num_chunks} Analysis]:\n{res}"
                for i, res in enumerate(all_chunk_outputs)
            )
            return ProcessedOutput(aggregated_result)

    async def analyze_file(self, file_path: FilePath, prompt: PromptText) -> None:
        """Analyzes file content, handling errors including permanent API failure."""
        try:
            self.ui.display_info(f"Analyzing file: {file_path}...")
            file_fingerprint = generate_file_fingerprint(str(file_path))
            # ... (read file) ...
            file_content: FileContent = self.file_system.read_file(file_path)

            analysis_result = await self._get_analysis_from_ai(
                file_path, prompt, file_content, file_fingerprint
            )

            if analysis_result is not None:
                self.ui.display_info("Analysis Result:")
                self.ui.display_output(analysis_result)
            else:
                # Error message was already displayed by _get_analysis_from_ai
                logger.error("Analysis could not be completed.")

        # ... (Specific error handling: File errors, Auth, RateLimit, Runtime, general Exception) ...
        except (FileNotFoundError, PermissionError, IsADirectoryError, OSError) as e:
            self.ui.display_error(f"Error reading file '{file_path}': {e}")
        except AuthenticationError as e:
            logger.error(f"Authentication failed during analysis: {e}")
            self.ui.display_error(f"Authentication failed: {e}")
        except RateLimitError as e:
            logger.error(f"Rate limit error during analysis (initial check): {e}")
            self.ui.display_error(f"API rate limit error: {e}")
        except RuntimeError as e:
            logger.error(f"Runtime error during analysis: {e}", exc_info=True)
            self.ui.display_error(f"Analysis failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
            self.ui.display_error(f"An unexpected error occurred during analysis: {e}")
