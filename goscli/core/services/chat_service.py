"""Core service for managing interactive chat sessions.

Hides the complexity of the chat loop, including user interaction,
state management (ChatSession), token estimation, prompt optimization,
API calls with resilience, and response processing.
"""

import asyncio
import logging
import time
import os
import sys
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

# Utils imports
from goscli.utils.mermaid_generator import MermaidGenerator

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
        # Add mermaid generator
        self.mermaid_generator = MermaidGenerator()
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
                logger.debug(f"Response received of type: {type(response)}")
                try:
                    # Check if postprocess_response is async or not
                    if asyncio.iscoroutinefunction(self.language_processor.postprocess_response):
                        logger.debug("Calling async postprocess_response")
                        response = await self.language_processor.postprocess_response(response)
                    else:
                        logger.debug("Calling sync postprocess_response")
                        response = self.language_processor.postprocess_response(response)
                    logger.debug("Language postprocessing completed successfully")
                except Exception as e:
                    logger.error(f"Error during language postprocessing: {e}", exc_info=True)
                    logger.warning("Using original response due to postprocessing failure")
                    # Continue with the original response
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

    async def _process_mermaid_diagrams(self, content: str) -> None:
        """Detects and processes Mermaid diagrams in the content.
        
        Args:
            content: The content to check for diagrams
        """
        logger.debug(f"Starting Mermaid diagram detection on content of length: {len(content)}")
        
        # Log whether Indonesian mode is enabled
        is_indonesian = use_indonesian()
        logger.debug(f"Indonesian mode in Mermaid diagram processing: {is_indonesian}")
        
        # Detect Mermaid blocks in the content
        mermaid_blocks = self.mermaid_generator.detect_mermaid_blocks(content)
        
        if not mermaid_blocks:
            logger.debug("No Mermaid diagrams detected in content")
            return
        
        logger.info(f"Found {len(mermaid_blocks)} Mermaid diagram(s) in content")
        logger.debug(f"Operating system: {os.name}, Platform: {sys.platform}")
        
        # Ask the user if they want to generate the diagrams
        try:
            # Prepare the question text - this should be translated if in Indonesian mode
            question_text = "Mermaid diagram(s) detected. Would you like to generate the diagram(s)?"
            if is_indonesian:
                # You could hard-code the translation or use translation service, but for UI messages
                # it's usually better to hard-code for reliability
                question_text = "Diagram Mermaid terdeteksi. Apakah Anda ingin membuat diagram?"
                logger.debug("Using Indonesian text for diagram generation question")
            
            user_choice = self.ui.ask_yes_no_question(question_text)
            logger.debug(f"User chose to generate diagrams: {user_choice}")
            if not user_choice:
                logger.info("User chose not to generate diagrams")
                return
                
            # Ask for diagram size
            diagram_size = self.ui.ask_diagram_size()
            logger.debug(f"User selected diagram size: {diagram_size}x{diagram_size}")
        except Exception as e:
            logger.error(f"Error when asking user about diagram generation: {e}", exc_info=True)
            return
        
        # Check if mmdc is installed
        try:
            mmdc_installed = self.mermaid_generator.is_mmdc_installed()
            logger.debug(f"mmdc installation check result: {mmdc_installed}")
            
            if not mmdc_installed:
                logger.info("mmdc not installed, offering to install it")
                
                # Prepare info message text based on language mode
                info_text = "Mermaid CLI (mmdc) is not installed but required for diagram generation."
                if is_indonesian:
                    info_text = "Mermaid CLI (mmdc) tidak terinstal tapi dibutuhkan untuk membuat diagram."
                    logger.debug("Using Indonesian text for mmdc installation info")
                
                self.ui.display_info(info_text)
                
                try:
                    # Prepare question text based on language mode
                    install_question = "Would you like to install Mermaid CLI (requires npm)?"
                    if is_indonesian:
                        install_question = "Apakah Anda ingin menginstal Mermaid CLI (memerlukan npm)?"
                        logger.debug("Using Indonesian text for mmdc installation question")
                    
                    install_choice = self.ui.ask_yes_no_question(install_question)
                    logger.debug(f"User chose to install mmdc: {install_choice}")
                    
                    if install_choice:
                        logger.debug("Attempting to display thinking indicator")
                        try:
                            # Prepare message text based on language mode
                            thinking_message = "Installing Mermaid CLI..."
                            if is_indonesian:
                                thinking_message = "Menginstal Mermaid CLI..."
                                logger.debug("Using Indonesian text for mmdc installation thinking indicator")
                            
                            # Use kwargs to handle potential method signature issues
                            self.ui.display_thinking(**{"message": thinking_message})
                        except TypeError as te:
                            logger.warning(f"TypeError when calling display_thinking with message parameter: {te}")
                            # Fallback to parameterless call
                            self.ui.display_thinking()
                            logger.debug("Fallback to parameterless display_thinking call succeeded")
                        
                        install_result = self.mermaid_generator.install_mmdc()
                        logger.debug(f"mmdc installation attempt result: {install_result}")
                        
                        if install_result:
                            # Prepare success message based on language mode
                            success_text = "Mermaid CLI installed successfully."
                            if is_indonesian:
                                success_text = "Mermaid CLI berhasil diinstal."
                                logger.debug("Using Indonesian text for mmdc installation success")
                            
                            self.ui.display_info(success_text)
                        else:
                            # Prepare error message based on language mode
                            error_text = "Failed to install Mermaid CLI. Please install it manually using 'npm install -g @mermaid-js/mermaid-cli'."
                            if is_indonesian:
                                error_text = "Gagal menginstal Mermaid CLI. Silakan instal secara manual menggunakan 'npm install -g @mermaid-js/mermaid-cli'."
                                logger.debug("Using Indonesian text for mmdc installation error")
                            
                            self.ui.display_error(error_text)
                            return
                    else:
                        # Prepare skip message based on language mode
                        skip_text = "Skipping diagram generation."
                        if is_indonesian:
                            skip_text = "Melewati pembuatan diagram."
                            logger.debug("Using Indonesian text for diagram generation skip")
                        
                        self.ui.display_info(skip_text)
                        return
                except Exception as e:
                    logger.error(f"Error during mmdc installation dialog: {e}", exc_info=True)
                    return
        except Exception as e:
            logger.error(f"Error checking if mmdc is installed: {e}", exc_info=True)
            
            # Prepare error message based on language mode
            error_text = f"Error checking Mermaid CLI installation: {e}"
            if is_indonesian:
                error_text = f"Kesalahan memeriksa instalasi Mermaid CLI: {e}"
                logger.debug("Using Indonesian text for mmdc check error")
            
            self.ui.display_error(error_text)
            return
        
        # Generate diagrams
        for i, mermaid_code in enumerate(mermaid_blocks):
            logger.debug(f"Processing diagram {i+1}/{len(mermaid_blocks)}")
            logger.debug(f"Mermaid code snippet (first 100 chars): {mermaid_code[:100]}...")
            
            try:
                logger.debug("Attempting to display thinking indicator for diagram generation")
                try:
                    # Prepare thinking message based on language mode
                    thinking_text = f"Generating diagram {i+1}/{len(mermaid_blocks)}..."
                    if is_indonesian:
                        thinking_text = f"Membuat diagram {i+1}/{len(mermaid_blocks)}..."
                        logger.debug("Using Indonesian text for diagram generation thinking indicator")
                    
                    # Use kwargs to handle potential method signature issues
                    self.ui.display_thinking(**{"message": thinking_text})
                except TypeError as te:
                    logger.warning(f"TypeError when calling display_thinking with message parameter: {te}")
                    # Fallback to parameterless call
                    self.ui.display_thinking()
                    logger.debug("Fallback to parameterless display_thinking call succeeded")
                
                logger.debug("Calling generate_diagram method")
                file_path = self.mermaid_generator.generate_diagram(mermaid_code, size=diagram_size)
                success = file_path is not None
                logger.debug(f"Diagram generation result: success={success}, file_path={file_path}")
                
                if success and file_path:
                    # Prepare success message based on language mode
                    success_text = f"Diagram generated: {file_path}"
                    if is_indonesian:
                        success_text = f"Diagram berhasil dibuat: {file_path}"
                        logger.debug("Using Indonesian text for diagram generation success")
                    
                    self.ui.display_info(success_text)
                    logger.info(f"Successfully generated diagram in {'Indonesian' if is_indonesian else 'English'} mode: {file_path}")
                    
                    # Try to open the diagram if on a desktop system
                    try:
                        if os.name == 'nt':  # Windows
                            logger.debug(f"Attempting to open diagram with os.startfile on Windows: {file_path}")
                            os.startfile(file_path)
                        elif os.name == 'posix':  # macOS or Linux
                            logger.debug(f"Attempting to open diagram with xdg-open on POSIX: {file_path}")
                            import subprocess
                            subprocess.run(['xdg-open', file_path], check=False)
                        logger.debug("Successfully initiated diagram opening")
                    except Exception as e:
                        logger.error(f"Error opening diagram: {e}", exc_info=True)
                else:
                    # Prepare error message based on language mode
                    error_text = "Failed to generate diagram."
                    if is_indonesian:
                        error_text = "Gagal membuat diagram."
                        logger.debug("Using Indonesian text for diagram generation failure")
                    
                    self.ui.display_error(error_text)
            except Exception as e:
                logger.error(f"Unexpected error generating diagram {i+1}: {e}", exc_info=True)
                
                # Prepare error message based on language mode
                error_text = f"Error generating diagram: {e}"
                if is_indonesian:
                    error_text = f"Kesalahan dalam membuat diagram: {e}"
                    logger.debug("Using Indonesian text for diagram generation error")
                
                self.ui.display_error(error_text)

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
                response = await self._call_ai_with_retry(messages_for_api)
                ai_messages += 1

                # 9. Handle potential API failure
                if response is None:
                    # Error already displayed by _call_ai_with_retry
                    continue  # Skip to next user prompt

                # 10. Process Response with QA Agent
                ai_processed_response: ProcessedOutput = self.qa_agent.process_response(
                    response
                )

                # 11. Add AI message to history
                # Estimate AI response tokens (if usage data available)
                ai_token_count = None
                if response.token_usage:
                    ai_token_count = TokenCount(
                        response.token_usage.get("completion_tokens", 0)
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
                content_str = None
                
                # Safely extract content as string
                if hasattr(response, 'content'):
                    # Get content from StructuredAIResponse
                    if isinstance(response.content, str):
                        content_str = response.content
                    else:
                        logger.warning(f"Response content is not a string but: {type(response.content)}")
                        # Try to convert to string
                        try:
                            content_str = str(response.content) 
                            logger.debug("Successfully converted response content to string")
                        except Exception as e:
                            logger.error(f"Failed to convert response content to string: {e}")
                            content_str = ""
                elif isinstance(response, str):
                    # Direct string response
                    content_str = response
                else:
                    logger.warning(f"Response has no content attribute and is not a string: {type(response)}")
                    content_str = str(ai_processed_response)
                    
                # Check if it's primarily code
                if content_str and self._is_primarily_code(content_str):
                    message_type = "code"
                    logger.debug("Response identified as primarily code")

                # 13. Display AI response with appropriate styling
                self.ui.display_output(
                    ai_processed_response, title="AI", message_type=message_type
                )

                # After receiving a response from the AI, check for optimized use case
                if content_str:
                    logger.debug(f"Checking for Mermaid diagrams in content (length: {len(content_str)})")
                    try:
                        await self._process_mermaid_diagrams(content_str)
                    except Exception as e:
                        logger.error(f"Error processing Mermaid diagrams: {e}", exc_info=True)
                        self.ui.display_error(f"Error processing diagrams: {e}")
                else:
                    logger.warning("No content string available to check for Mermaid diagrams")

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
        
    def _is_primarily_code(self, content) -> bool:
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
            
        # Handle non-string content
        if not isinstance(content, str):
            logger.warning(f"Non-string content provided to code detection: {type(content)}")
            try:
                content = str(content)
                logger.debug("Successfully converted content to string for code detection")
            except Exception as e:
                logger.error(f"Failed to convert content to string for code detection: {e}")
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
