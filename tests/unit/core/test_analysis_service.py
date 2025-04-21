import pytest
from unittest.mock import MagicMock, call

from goscli.core.analysis_service import AnalysisService
from goscli.domain.interfaces.ai_model import AIModel, AIResponse
from goscli.domain.interfaces.output_processor import OutputProcessor, ProcessedOutput
from goscli.domain.interfaces.file_system import FileSystem
from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.common import FilePath, PromptText, FileContent

# Reuse fixtures from chat service tests if possible, or redefine
@pytest.fixture
def mock_file_system():
    mock = MagicMock(spec=FileSystem)
    mock.read_file.return_value = FileContent("File content for analysis")
    return mock

@pytest.fixture
def mock_ai_model():
    mock = MagicMock(spec=AIModel)
    mock.send_prompt.return_value = AIResponse("Mocked Analysis Result")
    return mock

@pytest.fixture
def mock_output_processor():
    mock = MagicMock(spec=OutputProcessor)
    mock.process_output.side_effect = lambda x: ProcessedOutput(x)
    return mock

@pytest.fixture
def mock_ui():
    mock = MagicMock(spec=UserInterface)
    return mock

@pytest.fixture
def analysis_service(mock_file_system, mock_ai_model, mock_output_processor, mock_ui):
    """Fixture to create AnalysisService with mocked dependencies."""
    return AnalysisService(
        file_system=mock_file_system,
        ai_model=mock_ai_model,
        output_processor=mock_output_processor,
        ui=mock_ui
    )

def test_analyze_file_success(analysis_service: AnalysisService, mock_file_system: MagicMock, mock_ai_model: MagicMock, mock_output_processor: MagicMock, mock_ui: MagicMock):
    """Test the successful file analysis workflow."""
    file_path = FilePath("/path/to/analyze.txt")
    prompt = PromptText("Analyze this file")

    analysis_service.analyze_file(file_path, prompt)

    # Check File System interaction
    mock_file_system.read_file.assert_called_once_with(file_path)

    # Check AI Model interaction
    mock_ai_model.send_prompt.assert_called_once()
    call_args = mock_ai_model.send_prompt.call_args
    sent_prompt = call_args.kwargs['prompt']
    sent_context = call_args.kwargs['context']
    assert sent_prompt == prompt
    assert "File content for analysis" in sent_context
    assert str(file_path) in sent_context

    # Check Output Processor interaction
    mock_output_processor.process_output.assert_called_once_with(AIResponse("Mocked Analysis Result"))

    # Check UI interaction
    mock_ui.display_info.assert_any_call(f"Reading file: {file_path}...")
    mock_ui.display_info.assert_any_call("File read successfully. Sending to AI for analysis...")
    mock_ui.display_info.assert_any_call("Analysis Result:")
    mock_ui.display_output.assert_called_once_with(ProcessedOutput("Mocked Analysis Result"))
    mock_ui.display_error.assert_not_called()

def test_analyze_file_read_error(analysis_service: AnalysisService, mock_file_system: MagicMock, mock_ai_model: MagicMock, mock_ui: MagicMock):
    """Test handling of file reading errors."""
    file_path = FilePath("/path/to/error.txt")
    prompt = PromptText("Analyze this")
    error_message = "Permission denied"
    mock_file_system.read_file.side_effect = PermissionError(error_message)

    analysis_service.analyze_file(file_path, prompt)

    # Check File System interaction
    mock_file_system.read_file.assert_called_once_with(file_path)

    # Check that AI model was not called
    mock_ai_model.send_prompt.assert_not_called()

    # Check UI interaction (error display)
    mock_ui.display_info.assert_any_call(f"Reading file: {file_path}...")
    mock_ui.display_error.assert_called_once_with(f"Error reading file '{file_path}': {error_message}")
    mock_ui.display_output.assert_not_called()

def test_analyze_file_ai_error(analysis_service: AnalysisService, mock_file_system: MagicMock, mock_ai_model: MagicMock, mock_ui: MagicMock):
    """Test handling of AI interaction errors."""
    file_path = FilePath("/path/to/ai_error.txt")
    prompt = PromptText("Analyze this")
    error_message = "API connection failed"
    mock_ai_model.send_prompt.side_effect = RuntimeError(error_message)

    analysis_service.analyze_file(file_path, prompt)

    # Check File System interaction
    mock_file_system.read_file.assert_called_once_with(file_path)

    # Check AI model call was attempted
    mock_ai_model.send_prompt.assert_called_once()

    # Check UI interaction (error display)
    mock_ui.display_info.assert_any_call(f"Reading file: {file_path}...")
    mock_ui.display_info.assert_any_call("File read successfully. Sending to AI for analysis...")
    mock_ui.display_error.assert_called_once_with(f"AI interaction failed: {error_message}")
    mock_ui.display_output.assert_not_called() 