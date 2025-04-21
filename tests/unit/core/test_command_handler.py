import pytest
from unittest.mock import MagicMock

from goscli.core.command_handler import CommandHandler
from goscli.core.chat_service import ChatService
from goscli.core.analysis_service import AnalysisService
from goscli.core.find_service import FindService
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.common import FilePath, PromptText

@pytest.fixture
def mock_chat_service():
    return MagicMock(spec=ChatService)

@pytest.fixture
def mock_analysis_service():
    return MagicMock(spec=AnalysisService)

@pytest.fixture
def mock_find_service():
    return MagicMock(spec=FindService)

@pytest.fixture
def mock_ui():
    return MagicMock(spec=UserInterface)

@pytest.fixture
def command_handler(
    mock_chat_service,
    mock_analysis_service,
    mock_find_service,
    mock_ui
):
    """Fixture to create CommandHandler with mocked services."""
    return CommandHandler(
        chat_service=mock_chat_service,
        analysis_service=mock_analysis_service,
        find_service=mock_find_service,
        ui=mock_ui
    )

def test_start_chat(command_handler: CommandHandler, mock_chat_service: MagicMock):
    """Test that start_chat calls the chat service."""
    command_handler.start_chat()
    mock_chat_service.start_session.assert_called_once()

def test_start_chat_error(command_handler: CommandHandler, mock_chat_service: MagicMock, mock_ui: MagicMock):
    """Test that errors during chat start are displayed."""
    error_message = "Chat init failed"
    mock_chat_service.start_session.side_effect = Exception(error_message)
    command_handler.start_chat()
    mock_chat_service.start_session.assert_called_once()
    mock_ui.display_error.assert_called_once_with(f"Failed to run chat mode: {error_message}")

def test_handle_analyze(command_handler: CommandHandler, mock_analysis_service: MagicMock):
    """Test that handle_analyze calls the analysis service with correct args."""
    file_path_str = "/path/to/file.py"
    prompt_str = "Explain this python code"

    command_handler.handle_analyze(file_path_str, prompt_str)

    # Check that service was called with domain types
    mock_analysis_service.analyze_file.assert_called_once_with(
        FilePath(file_path_str),
        PromptText(prompt_str)
    )

def test_handle_analyze_error(command_handler: CommandHandler, mock_analysis_service: MagicMock, mock_ui: MagicMock):
    """Test that errors during analysis handling are displayed."""
    file_path_str = "/path/to/file.py"
    prompt_str = "Explain this python code"
    error_message = "Analysis internal error"
    mock_analysis_service.analyze_file.side_effect = Exception(error_message)

    command_handler.handle_analyze(file_path_str, prompt_str)

    mock_analysis_service.analyze_file.assert_called_once()
    mock_ui.display_error.assert_called_once_with(f"Analysis command failed: {error_message}")

def test_handle_find(command_handler: CommandHandler, mock_find_service: MagicMock):
    """Test that handle_find calls the find service with correct args."""
    query_str = "*.txt"
    command_handler.handle_find(query_str)
    mock_find_service.find_files_by_query.assert_called_once_with(PromptText(query_str))

def test_handle_find_error(command_handler: CommandHandler, mock_find_service: MagicMock, mock_ui: MagicMock):
    """Test that errors during find handling are displayed."""
    query_str = "*.txt"
    error_message = "Find internal error"
    mock_find_service.find_files_by_query.side_effect = Exception(error_message)

    command_handler.handle_find(query_str)

    mock_find_service.find_files_by_query.assert_called_once()
    mock_ui.display_error.assert_called_once_with(f"Find command failed: {error_message}") 