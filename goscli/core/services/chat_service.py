"""Core service for managing interactive chat sessions.

Hides the complexity of the chat loop, including user interaction,
state management (ChatSession), token estimation, prompt optimization,
API calls with resilience, and response processing.
"""

import asyncio
import logging
import time
from typing import List, Optional

# Domain Layer Imports
from goscli.domain.interfaces.ai_model import AIModel
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.ai import ChatMessage, StructuredAIResponse
from goscli.domain.models.chat import ChatSession
from goscli.domain.models.common import (
    MessageRole,
    ProcessedOutput,
    PromptText,
    TokenCount,
)
from goscli.infrastructure.agents.qa_agent import QualityAssuranceAgent

# Infrastructure Layer Imports (Specific Implementations Injected)
from goscli.infrastructure.resilience.api_retry import ApiRetryService, MaxRetryError
from goscli.infrastructure.optimization.prompt_optimizer import PromptOptimizer
from goscli.infrastructure.optimization.token_estimator import TokenEstimator

# Localization support
from goscli.infrastructure.localization.language_processor import LanguageProcessor
from goscli.infrastructure.config.settings import use_indonesian

# Import specific Authentication errors directly from where they are defined (usually the client libs)
# Add try-except blocks to handle cases where libraries might not be installed
try:
    from openai import AuthenticationError as OpenAIAuthenticationError
except ImportError:
    OpenAIAuthenticationError = None  # Set to None if openai isn't installed

try:
    from groq import AuthenticationError as GroqAuthenticationError
except ImportError:
    GroqAuthenticationError = None  # Set to None if groq isn't installed

# Create a tuple of available authentication errors, filtering out None values
# This allows catching the relevant exceptions without error if a library is missing
AvailableAuthErrors = tuple(
    filter(None, [OpenAIAuthenticationError, GroqAuthenticationError])
)

# These might still be useful for catching other errors
RateLimitError = getattr(
    __import__("openai", fromlist=["RateLimitError"]), "RateLimitError", Exception
)  # Example
APIError = getattr(
    __import__("openai", fromlist=["APIError"]), "APIError", Exception
)  # Example

logger = logging.getLogger(__name__)

# --- Configuration ---
# TODO: Load these from config settings
MODEL_CONTEXT_WINDOW = 128000
RESPONSE_BUFFER_TOKENS = 1500  # Reserve space for the AI's response
MAX_PROMPT_TOKENS = TokenCount(MODEL_CONTEXT_WINDOW - RESPONSE_BUFFER_TOKENS)
DEFAULT_PROVIDER = "openai"  # Example default


class ChatService:
    """Orchestrates the interactive chat functionality."""

    def __init__(
        self,
        ai_model: AIModel,  # The default AI model instance
        qa_agent: QualityAssuranceAgent,
        ui: UserInterface,
        api_retry_service: ApiRetryService,
        token_estimator: TokenEstimator,
        prompt_optimizer: PromptOptimizer,
        language_processor: Optional[LanguageProcessor] = None,
        # TODO: Add config service if needed for MAX_PROMPT_TOKENS etc.
    ):
        """Initializes the ChatService with its dependencies."""
        self.ai_model = ai_model  # This will be the default provider
        self.qa_agent = qa_agent
        self.ui = ui
        self.api_retry_service = api_retry_service
        self.token_estimator = token_estimator
        self.prompt_optimizer = prompt_optimizer
        self.language_processor = language_processor or LanguageProcessor()
        self.current_session: Optional[ChatSession] = None
        self.chat_task: Optional[asyncio.Task] = None
        self.max_prompt_tokens = MAX_PROMPT_TOKENS  # Use loaded config value
        logger.info(
            f"ChatService initialized with default AI model:"
            f" {ai_model.__class__.__name__}"
        )

    async def _call_ai_with_retry(
        self, messages: List[ChatMessage]
    ) -> Optional[StructuredAIResponse]:
        """Internal helper to call the AI model via the retry service."""
        provider_name = self.ai_model.__class__.__name__  # Or get from model instance
        
        # Preprocess messages to add language instructions if needed
        logger.debug(f"Before preprocessing: {len(messages)} messages")
        processed_messages = self.language_processor.preprocess_messages(messages)
        logger.debug(f"After preprocessing: {len(processed_messages)} messages")
        
        try:
            # Execute using the injected default AI model
            response = await self.api_retry_service.execute_with_retry(
                self.ai_model.send_messages,
                messages=processed_messages,  # Use processed messages
                provider_name=provider_name,
                endpoint_name="send_messages",
                # Chat loop usually doesn't benefit from cache fallback
                # for *next* response
                use_cache_fallback=False,
                # Enable provider fallback if configured in retry service
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
                f"Chat API call failed permanently after retries:"
                f" {e.original_exception}"
            )
            self.ui.display_error("AI communication failed after multiple attempts.")
            return None
        except AvailableAuthErrors as e:  # Catch specific available auth errors
            logger.critical(
                f"Authentication error during chat API call: {e}", exc_info=True
            )
            self.ui.display_error(
                f"Authentication failed: {e}. Please check your API key."
            )
            # Re-raise to potentially stop the loop or app
            raise
        except Exception as e:
            # Catch other unexpected errors from retry service
            logger.error(
                f"Unexpected error during API call via retry service: {e}",
                exc_info=True,
            )
            self.ui.display_error(
                f"An unexpected error occurred during AI communication: {e}"
            )
            return None  # Treat as failure for this turn

    async def start_chat_loop(self) -> None:
        """Runs the main asynchronous loop for a chat session."""
        if not self.current_session:
            logger.error("Cannot start chat loop: session not initialized.")
            return

        # Display styled session header with provider name
        provider_name = self.ai_model.__class__.__name__.replace("Client", "")
        self.ui.display_session_header(provider_name)
        
        logger.info(f"Chat session {self.current_session.session_id} loop started.")
        
        # Track message counts for session summary
        user_messages = 0
        ai_messages = 0

        while True:
            try:
                # 1. Get user input (run sync input in thread)
                user_input_text = await asyncio.to_thread(self.ui.get_prompt, "You: ")
                user_prompt = PromptText(user_input_text)

                # 2. Handle special commands
                if user_prompt.lower() in ["exit", "quit"]:
                    logger.debug(f"Handling exit command: {user_prompt}")
                    self.ui.display_info("Ending chat session.")
                    break
                elif user_prompt.lower() in ["/history", "/h"]:
                    # Display the chat history
                    logger.debug(f"Handling history command: {user_prompt}")
                    self.ui.display_chat_history(self.current_session.get_history())
                    continue  # Skip to next prompt
                elif user_prompt.lower() in ["/help", "/?"]:
                    logger.debug(f"Handling help command: {user_prompt}")
                    self._display_help_commands()
                    continue  # Skip to next prompt
                elif user_prompt.lower() in ["/clear", "/cls"]:
                    # Clear the console (platform-independent, using Rich)
                    logger.debug(f"Handling clear screen command: {user_prompt}")
                    try:
                        # Check if console attribute exists and is accessible
                        if hasattr(self.ui, 'console') and self.ui.console is not None:
                            self.ui.console.clear()
                            logger.debug("Console cleared successfully")
                        else:
                            logger.warning("UI does not have a console attribute or it is None")
                            self.ui.display_warning("Clear screen not supported by current UI")
                    except Exception as e:
                        logger.error(f"Error clearing console: {e}")
                        self.ui.display_error(f"Could not clear console: {e}")
                    # Redisplay the header
                    self.ui.display_session_header(provider_name)
                    continue  # Skip to next prompt
                elif user_prompt.lower() in ["/stats", "/info"]:
                    # Show session stats
                    logger.debug(f"Handling stats command: {user_prompt}")
                    self._display_session_stats()
                    continue  # Skip to next prompt
                
                # Count the actual user message (not special commands)
                user_messages += 1

                # 3. Prepare potential message list for estimation
                potential_next_message = ChatMessage(
                    role=MessageRole("user"), content=user_prompt
                )
                current_history_for_api = self.current_session.get_history_for_api()
                potential_message_list = current_history_for_api + [
                    potential_next_message
                ]

                # 4. Estimate tokens
                estimated_tokens = self.token_estimator.estimate_tokens_for_messages(
                    potential_message_list
                )
                logger.debug(
                    f"Estimated tokens for next turn prompt: {estimated_tokens}"
                )

                messages_for_api = (
                    potential_message_list  # Start with the full potential list
                )

                # 5. Optimize if needed
                if estimated_tokens > self.max_prompt_tokens:
                    logger.warning(
                        f"Potential prompt ({estimated_tokens} tokens) exceeds limit ({self.max_prompt_tokens}). Optimizing..."
                    )
                    # Optimize the *full* potential list to fit the budget
                    optimized_list = self.prompt_optimizer.optimize_messages(
                        potential_message_list, self.max_prompt_tokens
                    )

                    if not optimized_list or (
                        len(optimized_list) == 1
                        and optimized_list[0]["role"] == "system"
                    ):
                        # Check if optimization failed or only system prompt remains
                        logger.error(
                            "History optimization failed or removed all user/assistant messages. Cannot proceed."
                        )
                        self.ui.display_error(
                            "Error: Conversation history is too long to add new message after optimization."
                        )
                        continue  # Skip this turn, wait for next user input

                    # Use the optimized list for the API call
                    messages_for_api = optimized_list
                    # Update the *actual* session history based on the optimized list *excluding* the latest user message
                    # This is tricky. The optimizer might remove messages needed for context.
                    # Simpler: Just use the optimized list for the API call for now.
                    # A more robust approach would update the session history strategically.
                    logger.info(
                        f"Using optimized message list ({len(messages_for_api)} messages) for API call."
                    )

                # --- Add message and proceed with API call ---
                # Add the user message to the *actual* session history *after* potential optimization check
                # Note: This means the session history might grow beyond the limit between turns if optimization wasn't triggered
                # or if the user message is added *before* optimization is applied to the history itself.
                # Let's add it *before* the call but use `messages_for_api` for the call itself.
                self.current_session.add_message(
                    MessageRole("user"),
                    user_prompt,
                    self.token_estimator.estimate_tokens(user_prompt),
                )
                
                # Display user's message in UI for consistency (rendering user's own messages)
                self.ui.display_output(user_prompt, title="You")
                
                # Show a "thinking" indicator
                self.ui.display_thinking()

                # 8. Call AI
                structured_response = await self._call_ai_with_retry(messages_for_api)
                ai_messages += 1

                # 9. Handle potential API failure
                if structured_response is None:
                    # Error already displayed by _call_ai_with_retry
                    continue  # Skip to next user prompt

                # 10. Process Response with QA Agent
                ai_processed_response: ProcessedOutput = self.qa_agent.process_response(
                    structured_response
                )

                # 11. Add AI message to history
                # Estimate AI response tokens (if usage data available)
                ai_token_count = None
                if structured_response.token_usage:
                    ai_token_count = TokenCount(
                        structured_response.token_usage.get("completion_tokens", 0)
                    )
                else:
                    # Estimate if usage not provided
                    ai_token_count = self.token_estimator.estimate_tokens(
                        str(ai_processed_response)
                    )

                self.current_session.add_message(
                    MessageRole("assistant"), ai_processed_response, ai_token_count
                )
                logger.info(
                    f"Session {self.current_session.session_id} total tokens: {self.current_session.total_token_count}"
                )
                
                # 12. Detect if response is primarily code and set message type
                message_type = "normal"
                content_str = str(ai_processed_response)
                if self._is_primarily_code(content_str):
                    message_type = "code"

                # 13. Display AI response with appropriate styling
                self.ui.display_output(
                    ai_processed_response, title="AI", message_type=message_type
                )

            # 14. Error Handling
            except (RateLimitError, APIError) as api_err:
                # These might still be raised if retry service fails or for non-retryable ones
                logger.error(f"Chat loop caught API Error: {api_err}", exc_info=True)
                self.ui.display_error(
                    f"An API error occurred: {api_err}. Please try again later or check logs."
                )
                # Decide whether to break or continue
                # continue
            except (
                AvailableAuthErrors
            ) as auth_err:  # Catch specific available auth errors
                # Break the loop on auth errors
                logger.critical(
                    f"Chat loop terminating due to Authentication Error: {auth_err}"
                )
                break
            except KeyboardInterrupt:
                logger.info("Chat session interrupted by user (KeyboardInterrupt).")
                self.ui.display_info("\nEnding chat session.")
                break
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred in chat loop: {e}", exc_info=True
                )
                self.ui.display_error(f"An unexpected error occurred: {e}")
                break  # Exit loop on unexpected errors

        # Calculate session duration and display footer
        session_duration = time.time() - self.ui.session_start_time
        total_messages = user_messages + ai_messages
        self.ui.display_session_footer(total_messages, session_duration)
        
        # Cleanup after loop exits
        logger.info(f"Chat session {self.current_session.session_id} loop finished.")
        self.current_session = None
        self.chat_task = None
        
    def _display_help_commands(self) -> None:
        """Displays a list of available commands in the chat session."""
        help_text = """
Available commands:
- /history or /h - Display the chat history
- /clear or /cls - Clear the console screen
- /stats or /info - Show session statistics
- /help or /? - Show this help message
- exit or quit - End the chat session
        """
        self.ui.display_info(help_text)
        
    def _display_session_stats(self) -> None:
        """Displays statistics about the current chat session."""
        if not self.current_session:
            self.ui.display_error("No active chat session.")
            return
            
        # Calculate duration
        session_duration = time.time() - self.ui.session_start_time
        minutes, seconds = divmod(int(session_duration), 60)
        hours, minutes = divmod(minutes, 60)
        duration_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"
        
        # Count messages by role
        user_count = 0
        ai_count = 0
        for message in self.current_session.get_history():
            if message.role.lower() == "user":
                user_count += 1
            elif message.role.lower() == "assistant":
                ai_count += 1
                
        # Get token usage data
        total_tokens = self.current_session.total_token_count
        
        # Build stats message
        stats_text = f"""
Session Statistics:
- Session ID: {self.current_session.session_id}
- Duration: {duration_str}
- Messages: {user_count + ai_count} total ({user_count} from you, {ai_count} from AI)
- Tokens Used: {total_tokens}
- Provider: {self.ai_model.__class__.__name__.replace("Client", "")}
        """
        
        self.ui.display_info(stats_text)
        
    def _is_primarily_code(self, content: str) -> bool:
        """Determines if a response is primarily code.
        
        Args:
            content: The content to check
            
        Returns:
            True if the content appears to be primarily code
        """
        # Safe guard against empty content
        if not content:
            logger.debug("Empty content provided to code detection")
            return False
            
        # Count code blocks (``` delimited)
        code_block_count = content.count("```")
        total_length = len(content)
        
        logger.debug(f"Checking if content is primarily code: {code_block_count} code blocks, {total_length} total length")
        
        # If we have at least one code block and it's more than 50% of the content
        if code_block_count >= 2:  # At least one complete block (opening and closing ```)
            # Find all code blocks and measure their total length
            code_content = 0
            lines = content.split("\n")
            in_code_block = False
            
            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                    
                if in_code_block:
                    code_content += len(line) + 1  # +1 for the newline
            
            # If code makes up more than 60% of the content
            code_ratio = code_content / total_length if total_length > 0 else 0
            logger.debug(f"Code content: {code_content} chars ({code_ratio:.2%} of total)")
            
            if code_content > 0 and code_ratio > 0.6:
                logger.debug("Content identified as primarily code")
                return True
        
        logger.debug("Content identified as normal text")
        return False

    def start_session(self) -> None:
        """Starts a new chat session and manages the async event loop."""
        if self.chat_task and not self.chat_task.done():
            logger.warning(
                "Attempted to start a new chat session while one is already running."
            )
            self.ui.display_warning("Chat session is already active.")
            return

        self.current_session = ChatSession()
        logger.info(f"Starting new chat session: {self.current_session.session_id}")

        try:
            # Get or create event loop and run the coroutine
            # Using asyncio.run is generally safer for top-level entry points
            # if no other async code is running concurrently in the same thread.
            asyncio.run(self.start_chat_loop())
        except RuntimeError as e:
            # Handle specific case where asyncio.run detects a running loop
            if "cannot run loop" in str(e).lower():
                logger.error(
                    "Cannot start new asyncio loop via asyncio.run(). Is one already running?"
                )
                self.ui.display_error(
                    "Failed to start chat loop due to event loop conflict."
                )
                # Attempt to run differently if needed, though this suggests an architectural issue
                # try:
                #     loop = asyncio.get_event_loop()
                #     loop.run_until_complete(self.start_chat_loop())
                # except Exception as inner_e:
                #      logger.error(f"Fallback loop execution failed: {inner_e}")
            else:
                logger.error(f"Runtime error starting chat session: {e}", exc_info=True)
                self.ui.display_error(f"Failed to start chat: {e}")
        except Exception as e:
            logger.error(f"Failed to start chat session: {e}", exc_info=True)
            self.ui.display_error(f"Failed to start chat: {e}")
        finally:
            # Ensure cleanup happens even if loop start fails
            self.current_session = None
            self.chat_task = None

    # TODO: Add other methods if needed (e.g., loading/saving sessions)

