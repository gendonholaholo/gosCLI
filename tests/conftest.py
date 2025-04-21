import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from pathlib import Path
import os

# Import the application entry point and key components to mock/replace
from goscli.main import app, create_command_handler # Need app for CliRunner
from goscli.infrastructure.ai.gpt_client import GptClient # To mock this specifically
from goscli.infrastructure.cli.display import ConsoleDisplay # To potentially mock parts of this

@pytest.fixture(scope="session")
def runner():
    """Provides a Typer CliRunner instance."""
    return CliRunner()

@pytest.fixture
def mock_openai_client(mocker):
    """Fixture to provide a reusable mock GptClient instance.
    Patches the GptClient class within the test scope.
    """
    mock = mocker.MagicMock(spec=GptClient)
    # Mock the response structure needed by the services
    mock.send_prompt.return_value = "Mocked AI integration response"

    # Patch the GptClient where it's imported in main.py's create_command_handler context
    # Adjust the patch target if DI structure changes
    # For simplicity now, we might patch it globally for the test session or module
    # Or better: patch it within create_command_handler if possible, or patch the instance after creation.
    # Patching the class globally for these tests:
    mocker.patch('goscli.main.GptClient', return_value=mock)
    return mock

@pytest.fixture
def mock_console_display(mocker):
    """ Mocks the ConsoleDisplay to capture output easily.
        Patches the ConsoleDisplay where it's imported/used.
    """
    mock = mocker.MagicMock(spec=ConsoleDisplay)
    # Configure mocks for methods used in the flows
    mock.display_output = mocker.MagicMock()
    mock.display_info = mocker.MagicMock()
    mock.display_error = mocker.MagicMock()
    mock.get_prompt = mocker.MagicMock()

    mocker.patch('goscli.main.ConsoleDisplay', return_value=mock)
    # Patch it also where services might import it if not passed via DI correctly
    # (Ideally DI makes this unnecessary)
    # mocker.patch('goscli.core.analysis_service.ConsoleDisplay', return_value=mock)
    # mocker.patch('goscli.core.chat_service.ConsoleDisplay', return_value=mock)
    # mocker.patch('goscli.core.find_service.ConsoleDisplay', return_value=mock)
    return mock

@pytest.fixture
def test_fs(tmp_path: Path):
    """Creates a temporary file structure for integration tests."""
    base = tmp_path / "integration_fs"
    base.mkdir()

    # Files for analysis
    analyze_dir = base / "analyze_files"
    analyze_dir.mkdir()
    (analyze_dir / "report.txt").write_text("This is a test report.")
    (analyze_dir / "code.py").write_text("print('hello')")

    # Files for finding
    find_dir = base / "find_files"
    find_dir.mkdir()
    (find_dir / "config.json").write_text('{ "key": "value" }')
    sub_find = find_dir / "subdir"
    sub_find.mkdir()
    (sub_find / "notes.txt").write_text('Important notes')
    (sub_find / "image.jpg").write_text('dummy image data') # Treat as file

    return base

@pytest.fixture(autouse=True)
def ensure_api_key_for_tests(monkeypatch):
    """Ensure a dummy API key is set for tests to prevent init errors,
       even though the client itself is mocked.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "DUMMY_TEST_KEY_FOR_INIT") 