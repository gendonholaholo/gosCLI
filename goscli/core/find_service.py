import logging

from goscli.domain.interfaces.file_system import FileSystem
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.common import FilePath, PromptText
# from goscli.core.exceptions import FileOperationError # Use built-in if custom failed

logger = logging.getLogger(__name__)

class FindService:
    """Handles the logic for finding files based on user queries."""

    def __init__(
        self,
        file_system: FileSystem,
        ui: UserInterface,
        # ai_model: AIModel # Potentially needed later for NL query -> criteria translation
    ):
        """Initializes the FindService.

        Args:
            file_system: An instance implementing the FileSystem interface.
            ui: An instance implementing the UserInterface interface.
        """
        self.file_system = file_system
        self.ui = ui
        # self.ai_model = ai_model # If using AI for query processing

    def find_files_by_query(self, query: PromptText) -> None:
        """Finds files based on the user's query and displays the results.

        Note: Current implementation treats the query directly as a glob pattern.
        Natural Language Processing (NLP) to convert a query like
        "find python files modified last week" into a concrete search criteria
        (glob pattern, date checks, etc.) is NOT implemented yet.

        Args:
            query: The user's search query (currently treated as a glob pattern).

        Raises:
            # FileOperationError: If the file search operation fails.
            OSError: If the file search operation fails.
        """
        try:
            # TODO: Implement NLP/AI step here to convert natural language `query`
            #       into a specific search `criteria` (e.g., glob pattern, filters).
            #       For now, we assume the query IS the criteria (glob pattern).
            search_criteria: str = query
            self.ui.display_info(f"Searching for files matching pattern: '{search_criteria}'...")

            found_files: List[FilePath] = self.file_system.find_files(search_criteria)

            if not found_files:
                self.ui.display_info("No files found matching the pattern.")
            else:
                self.ui.display_info(f"Found {len(found_files)} file(s):")
                # Use display_output for potentially better formatting if needed
                for file_path in found_files:
                    self.ui.display_output(f"- {file_path}")

        except OSError as e:
            # Wrap file system errors
            # raise FileOperationError(f"Failed to search for files with query '{query}': {e}", e)
            self.ui.display_error(f"Error during file search: {e}")
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred during file search: {e}", exc_info=True)
            self.ui.display_error(f"An unexpected error occurred during file search: {e}")
            # raise CommandExecutionError(f"Unexpected find error: {e}", e) from e # If custom exceptions exist 