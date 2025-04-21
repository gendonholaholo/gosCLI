"""Core service for handling file finding requests.

Currently uses the FileSystem interface to perform searches (e.g., glob patterns).
Could be extended to use AI for natural language search queries.
"""

import logging
from typing import List

# Domain Layer Imports
from goscli.domain.interfaces.filesystem import FileSystem
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.common import FilePath, ProcessedOutput, PromptText

# from ...domain.interfaces.ai_model import AIModel # If using AI for NL search

# Infrastructure Layer Imports (interfaces/implementations injected)
# from ...infrastructure.agents.qa_agent import QualityAssuranceAgent

logger = logging.getLogger(__name__)


class FindService:
    """Orchestrates the file finding functionality."""

    def __init__(
        self,
        file_system: FileSystem,
        ui: UserInterface,
        # ai_model: Optional[AIModel] = None, # Inject if NL search is added
        # qa_agent: Optional[QualityAssuranceAgent] = None,
        # TODO: Add other necessary dependencies
    ):
        """Initializes the FindService with its dependencies."""
        self.file_system = file_system
        self.ui = ui
        # self.ai_model = ai_model
        # self.qa_agent = qa_agent

    async def find_files_by_query(self, query: PromptText) -> None:
        """
        Finds files based on a query
        (currently assumes glob pattern) asynchronously.
        """
        self.ui.display_info(f"Searching for files matching: {query}...")
        try:
            # Use the FileSystem interface to perform the search
            found_files: List[FilePath] = await self.file_system.find_files(query)

            if not found_files:
                self.ui.display_info("No files found matching the query.")
            else:
                self.ui.display_info(f"Found {len(found_files)} file(s):")
                # TODO: Improve output formatting (e.g., using Rich table)
                for file_path in found_files:
                    # Using display_output assuming it handles simple strings
                    self.ui.display_output(ProcessedOutput(f"- {file_path}"))

        except Exception as e:
            logger.error(
                f"Error during file search for query '{query}': {e}", exc_info=True
            )
            self.ui.display_error(f"File search failed: {e}")

    # TODO: Implement find_files_via_ai if natural language search is added
    # async def find_files_via_ai(self, natural_language_query: PromptText) -> None:
    #     """Finds files using AI to interpret a natural language query."""
    #     if not self.ai_model or not self.qa_agent:
    #          self.ui.display_error("AI model not configured for natural language search.")  # noqa: E501
    #          return
    #     # 1. Send NL query to AI
    #     # 2. Process response (extract potential patterns or file list)
    #     # 3. Use file_system.find_files or file_system.file_exists
    #     # 4. Display results
    #     pass

