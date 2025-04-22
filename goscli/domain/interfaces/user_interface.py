"""Interface for interacting with the user (input/output).

Defines the contract for displaying information, errors, warnings,
and getting input from the user, allowing different UI implementations
(e.g., console, GUI).
"""

import abc
from typing import Any, Optional

# Import relevant domain models
from goscli.domain.models.common import PromptText, ProcessedOutput

class UserInterface(abc.ABC):
    """Abstract Base Class for user interaction."""

    @abc.abstractmethod
    def display_output(self, output: ProcessedOutput, **kwargs: Any) -> None:
        """Displays standard output to the user.

        Args:
            output: The processed output string to display.
            **kwargs: Additional arguments for formatting (e.g., color, style).
        """
        pass

    @abc.abstractmethod
    def display_error(self, error_message: str, **kwargs: Any) -> None:
        """Displays an error message to the user.

        Args:
            error_message: The error message string.
            **kwargs: Additional arguments for formatting.
        """
        pass

    @abc.abstractmethod
    def display_warning(self, warning_message: str, **kwargs: Any) -> None:
        """Displays a warning message to the user.

        Args:
            warning_message: The warning message string.
            **kwargs: Additional arguments for formatting.
        """
        pass

    @abc.abstractmethod
    def display_info(self, info_message: str, **kwargs: Any) -> None:
        """Displays an informational message to the user.

        Args:
            info_message: The informational message string.
            **kwargs: Additional arguments for formatting.
        """
        pass

    @abc.abstractmethod
    def get_prompt(self, prompt_message: str = "Input: ") -> PromptText:
        """Gets input from the user synchronously.

        Note: For async contexts, the caller should wrap this in asyncio.to_thread.

        Args:
            prompt_message: The message to display before the input prompt.

        Returns:
            The user's input as PromptText.
        """
        pass
        
    def display_session_header(self, provider_name: str = "AI") -> None:
        """Displays a header for a new chat session.
        
        Args:
            provider_name: Name of the AI provider
        """
        pass
        
    def display_session_footer(self, message_count: int, session_duration_secs: float) -> None:
        """Displays a footer at the end of a chat session.
        
        Args:
            message_count: Number of messages exchanged
            session_duration_secs: Session duration in seconds
        """
        pass
        
    def display_chat_history(self, history: list, **kwargs: Any) -> None:
        """Displays the chat history.
        
        Args:
            history: List of chat message objects
            **kwargs: Additional display options
        """
        pass
        
    def display_thinking(self, **kwargs: Any) -> None:
        """Displays a 'thinking' indicator while the AI is processing.
        
        Args:
            **kwargs: Additional display options
        """
        pass
        
    def ask_yes_no_question(self, question: str) -> bool:
        """Asks a yes/no question and returns the answer.
        
        Args:
            question: The question to ask
            
        Returns:
            True if the answer is yes, False otherwise
        """
        pass

    # Optional: Add methods for progress bars, tables, etc.
    # @abc.abstractmethod
    # def display_progress(self, current: int, total: int, description: str = "") -> None:
    #     pass 