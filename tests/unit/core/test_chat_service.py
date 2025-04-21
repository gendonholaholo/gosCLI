import pytest
from unittest.mock import MagicMock, call

from goscli.core.chat_service import ChatService
from goscli.domain.interfaces.ai_model import AIModel, AIResponse, AIContext
from goscli.domain.interfaces.output_processor import OutputProcessor, ProcessedOutput
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.common import PromptText

@pytest.fixture
def mock_ai_model():
    mock = MagicMock(spec=AIModel)
    mock.send_prompt.return_value = AIResponse("Mocked AI Response")
    return mock

@pytest.fixture
def mock_output_processor():
    mock = MagicMock(spec=OutputProcessor)
    # Simple pass-through mock for testing
    mock.process_output.side_effect = lambda x: ProcessedOutput(x)
    return mock

@pytest.fixture
def mock_ui():
    mock = MagicMock(spec=UserInterface)
    # Simulate user input sequence: first prompt, then 'exit'
    mock.get_prompt.side_effect = ["Hello AI", "exit"]
    return mock

@pytest.fixture
def chat_service(mock_ai_model, mock_output_processor, mock_ui):
    """Fixture to create ChatService with mocked dependencies."""
    return ChatService(
        ai_model=mock_ai_model,
        output_processor=mock_output_processor,
        ui=mock_ui
    )

def test_start_session_loop(chat_service: ChatService, mock_ai_model: MagicMock, mock_output_processor: MagicMock, mock_ui: MagicMock):
    """Test the main chat loop interaction."""
    chat_service.start_session()

    # Check UI calls
    mock_ui.display_info.assert_any_call("Starting interactive chat session. Type 'exit' or 'quit' to end.")
    assert mock_ui.get_prompt.call_count == 2 # Called for "Hello AI" and "exit"
    mock_ui.get_prompt.assert_any_call("You: ")
    mock_ui.display_output.assert_called_once_with("AI: Mocked AI Response")
    mock_ui.display_info.assert_any_call("Ending chat session.")

    # Check AI model call
    mock_ai_model.send_prompt.assert_called_once()
    call_args = mock_ai_model.send_prompt.call_args
    # Verify prompt and basic context (based on ChatSession implementation)
    sent_prompt = call_args.kwargs['prompt']
    sent_context = call_args.kwargs['context']
    assert sent_prompt == PromptText("Hello AI")
    assert "User: Hello AI" in sent_context # Check if user message is in context

    # Check output processor call
    mock_output_processor.process_output.assert_called_once_with(AIResponse("Mocked AI Response"))

    # Check session state reset
    assert chat_service.current_session is None

def test_start_session_exit_immediately(chat_service: ChatService, mock_ai_model: MagicMock, mock_ui: MagicMock):
    """Test exiting the loop immediately."""
    mock_ui.get_prompt.side_effect = ["quit"]
    chat_service.start_session()

    mock_ui.display_info.assert_any_call("Starting interactive chat session. Type 'exit' or 'quit' to end.")
    mock_ui.get_prompt.assert_called_once_with("You: ")
    mock_ai_model.send_prompt.assert_not_called()
    mock_ui.display_output.assert_not_called()
    mock_ui.display_info.assert_any_call("Ending chat session.")
    assert chat_service.current_session is None

def test_start_session_handles_ai_error(chat_service: ChatService, mock_ai_model: MagicMock, mock_ui: MagicMock):
    """Test that errors from the AI model are caught and displayed."""
    ai_error_message = "AI Service Unavailable"
    # Simulate user prompt then exit
    mock_ui.get_prompt.side_effect = ["Ask something", "exit"]
    # Simulate AI error
    mock_ai_model.send_prompt.side_effect = RuntimeError(ai_error_message)

    chat_service.start_session()

    mock_ai_model.send_prompt.assert_called_once()
    mock_ui.display_error.assert_called_once_with(f"An error occurred: {ai_error_message}")
    # Ensure loop continued to ask for 'exit'
    assert mock_ui.get_prompt.call_count == 2
    mock_ui.display_info.assert_any_call("Ending chat session.")
    assert chat_service.current_session is None 