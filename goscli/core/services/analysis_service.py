"""
Core service for handling file analysis requests.

Coordinates reading files, interacting with the AI model for analysis,
handling caching, and processing the results.
"""

# import asyncio  # If file reading or AI calls are async
import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Tuple  # , Any

# Domain Layer Imports
from goscli.domain.interfaces.ai_model import AIModel
from goscli.domain.interfaces.cache import CacheService
from goscli.domain.interfaces.filesystem import FileSystem
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.ai import ChatMessage, StructuredAIResponse  # , MessageRole
from goscli.domain.models.common import (
    CacheKey,
    FilePath,
    ProcessedOutput,
    PromptText,
    TokenCount,
)
from goscli.infrastructure.agents.qa_agent import QualityAssuranceAgent

# Infrastructure Layer Imports (Specific Implementations Injected)
from goscli.infrastructure.resilience.api_retry import ApiRetryService, MaxRetryError
from goscli.infrastructure.optimization.prompt_optimizer import PromptOptimizer

# Potentially TokenEstimator/PromptOptimizer if analysis prompts need optimization
from goscli.infrastructure.optimization.token_estimator import TokenEstimator

# Localization support
from goscli.infrastructure.localization.language_processor import LanguageProcessor
from goscli.infrastructure.config.settings import use_indonesian

logger = logging.getLogger(__name__)

# --- Configuration ---
# TODO: Load from config
MAX_ANALYSIS_FILE_SIZE = 1024 * 1024 * 1  # 1MB Example limit
ANALYSIS_CACHE_TTL = 60 * 60 * 24  # 1 day example
MODEL_CONTEXT_WINDOW = 128000
RESPONSE_BUFFER_TOKENS = 1500  # Reserve space for the AI's response
MAX_PROMPT_TOKENS = TokenCount(MODEL_CONTEXT_WINDOW - RESPONSE_BUFFER_TOKENS)


class AnalysisService:
    """Orchestrates the file analysis functionality."""

    def __init__(
        self,
        ai_model: AIModel,
        qa_agent: QualityAssuranceAgent,
        file_system: FileSystem,
        cache_service: CacheService,
        api_retry_service: ApiRetryService,
        ui: UserInterface,
        token_estimator: Optional[TokenEstimator] = None,
        prompt_optimizer: Optional[PromptOptimizer] = None,
        language_processor: Optional[LanguageProcessor] = None,
        # TODO: Inject config service
    ):
        """Initializes the AnalysisService with its dependencies."""
        self.ai_model = ai_model
        self.qa_agent = qa_agent
        self.file_system = file_system
        self.cache_service = cache_service
        self.api_retry_service = api_retry_service
        self.ui = ui
        self.token_estimator = token_estimator
        self.prompt_optimizer = prompt_optimizer
        self.language_processor = language_processor or LanguageProcessor()
        self.max_file_size = MAX_ANALYSIS_FILE_SIZE  # Use loaded config value
        self.cache_ttl = ANALYSIS_CACHE_TTL  # Use loaded config value
        logger.info(
            f"AnalysisService initialized with AI model: {ai_model.__class__.__name__}"
        )

    def _create_cache_key(
        self, file_path: FilePath, prompt: PromptText, file_hash: str
    ) -> CacheKey:
        """
        Creates a unique cache key for an analysis request based
        on file hash and prompt.
        """
        prompt_hash = hashlib.sha256(str(prompt).encode()).hexdigest()[:16]
        # Key includes provider, file hash, and prompt hash for uniqueness
        provider_name = self.ai_model.__class__.__name__
        return CacheKey(f"analysis:{provider_name}:{file_hash}:{prompt_hash}")

    async def _get_file_content_and_hash(
        self, file_path: FilePath
    ) -> Tuple[Optional[str], Optional[str]]:
        """Reads file content and calculates its SHA256 hash."""
        try:
            # Check file size first (synchronous check is usually fast enough)
            try:
                file_size = Path(file_path).stat().st_size
                if file_size > self.max_file_size:
                    logger.error(
                        f"File {file_path} ({file_size} bytes) exceeds"
                        f"maximum size limit ({self.max_file_size} bytes)."
                    )
                    self.ui.display_error(
                        f"File exceeds size limit"
                        f"({self.max_file_size / (1024 * 1024):.1f} MB)."
                    )
                    return None, None
            except FileNotFoundError:
                raise  # Re-raise to be caught below
            except Exception as stat_e:
                logger.warning(
                    f"Could not determine file size for {file_path}: {stat_e}"
                )
                # Proceed cautiously if size unknown

            # Read file content
            file_content = await self.file_system.read_file(file_path)
            # Calculate hash
            file_hash = hashlib.sha256(file_content.encode()).hexdigest()
            return file_content, file_hash
        except FileNotFoundError:
            logger.error(f"File not found for analysis: {file_path}")
            self.ui.display_error(f"Error: File not found at {file_path}")
            return None, None
        except Exception as e:
            logger.error(
                f"Error reading or hashing file {file_path}: {e}", exc_info=True
            )
            self.ui.display_error(f"Error reading file: {e}")
            return None, None

    async def _get_analysis_from_ai(
        self, file_content: str, prompt: PromptText
    ) -> Optional[StructuredAIResponse]:
        """Constructs messages and sends the analysis request to the AI model."""
        # TODO: Refine system prompt, make configurable?
        system_prompt = (
            "You are a helpful assistant."
            "Analyze the provided file content based on the user's specific prompt."
            "Provide a clear and concise analysis."
        )
        user_message = (
            f"User Prompt: {prompt}\n\nFile Content to Analyze:"
            "\n```\n{file_content}\n```"
        )

        messages: List[ChatMessage] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # --- Optional Prompt Optimization ---
        if self.token_estimator and self.prompt_optimizer:
            # TODO: Get max tokens for the *specific model* being used?
            max_prompt_tokens = MAX_PROMPT_TOKENS  # Use general limit for now
            estimated_tokens = self.token_estimator.estimate_tokens_for_messages(
                messages
            )
            if estimated_tokens > max_prompt_tokens:
                logger.warning(
                    f"Analysis prompt ({estimated_tokens} tokens)"
                    f" exceeds limit ({max_prompt_tokens}). Optimizing..."
                )
                # Optimize (this might truncate file content within the user message)
                messages = self.prompt_optimizer.optimize_messages(
                    messages, max_prompt_tokens
                )
                if not messages:
                    logger.error("Prompt optimization failed for analysis request.")
                    self.ui.display_error(
                        "Error: Could not optimize the analysis"
                        " request to fit token limits."
                    )
                    return None
        # --- End Optional Optimization ---

        # Preprocess messages to add language instructions if needed
        logger.debug(f"Before preprocessing: {len(messages)} messages")
        processed_messages = self.language_processor.preprocess_messages(messages)
        logger.debug(f"After preprocessing: {len(processed_messages)} messages")

        provider_name = self.ai_model.__class__.__name__
        try:
            response = await self.api_retry_service.execute_with_retry(
                self.ai_model.send_messages,
                messages=processed_messages,
                provider_name=provider_name,
                endpoint_name="send_messages_analysis",
                # Allow cache fallback for analysis?
                # Maybe not useful unless prompt identical
                use_cache_fallback=False,
                use_provider_fallback=True,
            )
            
            # Postprocess response for language if needed
            if response:
                logger.debug("Response received, applying language postprocessing")
                response = await self.language_processor.postprocess_response(response)
            else:
                logger.warning("No response received from AI model")
                
            return response
        except MaxRetryError as e:
            logger.error(
                f"Analysis API call failed permanently: {e.original_exception}"
            )
            self.ui.display_error(
                f"AI analysis failed after multiple attempts: {e.original_exception}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error during analysis API call: {e}", exc_info=True
            )
            self.ui.display_error(f"AI analysis failed unexpectedly: {e}")
            return None

    async def analyze_file(self, file_path: FilePath, prompt: PromptText) -> None:
        """Performs analysis on a given file with a specific prompt."""
        self.ui.display_info(
            f"Analyzing file: {file_path} using {self.ai_model.__class__.__name__}..."
        )

        # 1. Read file and get hash
        file_content, file_hash = await self._get_file_content_and_hash(file_path)
        if file_content is None or file_hash is None:
            # Error handled and displayed within the helper method
            return

        # 2. Create cache key and check cache
        cache_key = self._create_cache_key(file_path, prompt, file_hash)
        try:
            cached_result: Optional[ProcessedOutput] = await self.cache_service.get(
                cache_key
            )
            if cached_result:
                logger.info(f"Analysis cache hit for key: {cache_key}")
                self.ui.display_info("(Result from cache)")
                self.ui.display_output(cached_result, title="Analysis Result")
                return
            logger.info(f"Analysis cache miss for key: {cache_key}")
        except Exception as e:
            logger.warning(
                f"Cache lookup failed for key {cache_key}: {e}."
                f" Proceeding without cache."
            )

        # 3. Call AI for analysis
        structured_response = await self._get_analysis_from_ai(file_content, prompt)

        if not structured_response:
            # Error displayed by _get_analysis_from_ai
            return

        # 4. Process AI response
        processed_output = self.qa_agent.process_response(structured_response)

        # 5. Store result in cache
        try:
            await self.cache_service.set(
                cache_key, processed_output, ttl=self.cache_ttl
            )
            logger.info(
                f"Analysis result cached for key: {cache_key} "
                f"with TTL: {self.cache_ttl}s"
            )
        except Exception as e:
            logger.error(
                f"Failed to cache analysis result for key {cache_key}: {e}",
                exc_info=True,
            )

        # 6. Display result
        self.ui.display_output(processed_output, title="Analysis Result")

    # TODO: Add methods for handling chunked analysis for large files if needed.
    # Requires breaking file_content, multiple AI calls, and result aggregation.

