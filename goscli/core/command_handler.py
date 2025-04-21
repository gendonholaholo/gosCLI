"""Command Handler: Orchestrates CLI command execution.

Receives commands from the main entry point (main.py) and delegates
the work to the appropriate application services (ChatService, AnalysisService,
FindService). Uses the AgentExecutionDecider to potentially route execution
locally or to API-based services.
"""

import logging
import asyncio
from typing import Optional, Dict, Any

# Core Services Imports
from goscli.core.services.chat_service import ChatService
from goscli.core.services.analysis_service import AnalysisService
from goscli.core.services.find_service import FindService

# Domain Layer Imports
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.common import FilePath, PromptText

# Infrastructure Layer Imports (specific agents/services)
from goscli.infrastructure.agents.execution_decider import AgentExecutionDecider
# Import CacheService interface for type hint, implementation injected
from goscli.domain.interfaces.cache import CacheService
# TODO: Potentially import a ModelRegistry interface/service for list-models

logger = logging.getLogger(__name__)

class CommandHandler:
    """Handles incoming commands and delegates to appropriate services."""

    def __init__(
        self,
        chat_service: ChatService,
        analysis_service: AnalysisService,
        find_service: FindService,
        execution_decider: AgentExecutionDecider,
        cache_service: CacheService, # Added for clear-cache
        ui: UserInterface,
        # TODO: Add other necessary dependencies (e.g., config, model_registry)
    ):
        """Initializes the CommandHandler with required services and agents."""
        self.chat_service = chat_service
        self.analysis_service = analysis_service
        self.find_service = find_service
        self.execution_decider = execution_decider
        self.cache_service = cache_service
        self.ui = ui

    def start_chat(self) -> None:
        """Handles the initiation of the interactive chat mode."""
        # Chat implicitly requires API interaction eventually, no decider needed here.
        # The decider might be used *within* chat for specific commands later.
        logger.info("Starting interactive chat session.")
        try:
            # start_session manages its own async loop internally
            self.chat_service.start_session()
        except Exception as e:
            logger.error(f"Failed to start chat mode: {e}", exc_info=True)
            self.ui.display_error(f"Failed to run chat mode: {e}")

    async def handle_analyze(self, file_path_str: str, prompt_str: str, provider: Optional[str] = None) -> None:
        """Handles the 'analyze' command, deciding execution path and provider."""
        intent = "AnalyzeFile"
        parameters = {'file_path': file_path_str, 'prompt': prompt_str, 'provider': provider}
        logger.info(f"Handling 'analyze' command for file: {file_path_str} with provider: {provider or 'default'}")

        # TODO: Check if provider is valid/configured if specified

        should_call_api = self.execution_decider.should_call_api(intent, parameters)

        if should_call_api:
            logger.info(f"Routing '{intent}' to API-based AnalysisService.")
            try:
                file_path = FilePath(file_path_str)
                prompt = PromptText(prompt_str)
                # TODO: Pass the provider to the analysis_service if it needs to select the AIModel
                await self.analysis_service.analyze_file(file_path, prompt)
            except Exception as e:
                logger.error(f"Analysis command failed: {e}", exc_info=True)
                self.ui.display_error(f"Analysis failed: {e}")
        else:
            # TODO: Implement local analysis if applicable, or display message
            logger.info(f"Routing '{intent}' to local execution (Not Implemented).")
            self.ui.display_error("Local analysis is not yet implemented.")

    async def handle_find(self, query_str: str) -> None:
        """Handles the 'find' command, deciding execution path."""
        intent = "FindFiles"
        parameters = {'query': query_str}
        logger.info(f"Handling 'find' command with query: {query_str}")

        should_call_api = self.execution_decider.should_call_api(intent, parameters)

        if should_call_api:
            # TODO: Implement AI-based find if applicable, or display message
            # await self.find_service.find_files_via_ai(PromptText(query_str))
            logger.info(f"Routing '{intent}' to API-based FindService (Not Implemented).")
            self.ui.display_error("Natural language file search is not yet implemented.")
        else:
            logger.info(f"Routing '{intent}' to local FindService (using glob).")
            try:
                query = PromptText(query_str)
                # Assuming find_files_by_query is now async based on FindService placeholder
                await self.find_service.find_files_by_query(query)
            except Exception as e:
                logger.error(f"Find command failed: {e}", exc_info=True)
                self.ui.display_error(f"Find failed: {e}")

    async def handle_clear_cache(self, level: str) -> None:
        """Handles the 'clear-cache' command."""
        intent = "ClearCache"
        parameters = {'level': level}
        logger.info(f"Handling 'clear-cache' command for level: {level}")

        # Cache clearing is always local
        # TODO: Validate level using constants if defined elsewhere
        if level not in ['l1', 'l2', 'l3', 'all']:
             self.ui.display_error("Invalid cache level. Choose 'l1', 'l2', 'l3', or 'all'.")
             return
        try:
            await self.cache_service.clear(level)
            self.ui.display_info(f"Cache level '{level}' cleared successfully.")
        except Exception as e:
            logger.error(f"Failed to clear cache level '{level}': {e}", exc_info=True)
            self.ui.display_error(f"Failed to clear cache: {e}")

    async def handle_list_models(self, provider: Optional[str]) -> None:
        """Handles listing available AI models from a specified provider."""
        intent = "ListModels"
        parameters = {'provider': provider}
        selected_provider = provider or 'default' # Or get default from config
        logger.info(f"Handling 'list-models' command for provider: {selected_provider}")

        # TODO: Implement model listing logic.
        # This likely requires a way to access the specific AIModel implementation
        # based on the provider name. This could involve:
        # 1. A dedicated ModelRegistryService injected here.
        # 2. Modifying the DI in main.py to provide access to multiple AIModel instances.
        # 3. Querying a configuration service.
        try:
            # Placeholder logic - assumes a way to get the right model client
            # model_client = self._get_model_client(selected_provider)
            # available_models = await model_client.list_available_models()
            # self.ui.display_info(f"Available models for '{selected_provider}':")
            # for model in available_models:
            #    self.ui.display_output(f"- {model.model_id} ({getattr(model, 'name', 'N/A')})") # Example
            self.ui.display_error(f"Listing models for provider '{selected_provider}' is not yet implemented.")
        except Exception as e:
            logger.error(f"Failed to list models for provider '{selected_provider}': {e}", exc_info=True)
            self.ui.display_error(f"Failed to list models: {e}")

    # Placeholder internal method - needs proper implementation based on DI strategy
    # def _get_model_client(self, provider: str) -> AIModel:
    #    # Logic to select the correct AIModel instance based on provider name
    #    raise NotImplementedError
