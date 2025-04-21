import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, call
import os
from pathlib import Path

# Import the app instance from main
from goscli.main import app

# These fixtures are defined in tests/conftest.py:
# runner: CliRunner
# mock_openai_client: MagicMock (patches GptClient)
# mock_console_display: MagicMock (patches ConsoleDisplay)
# test_fs: Path (root of temporary file structure)
# ensure_api_key_for_tests: Sets dummy API key

def test_analyze_command_flow(
    runner: CliRunner,
    test_fs: Path,
    mock_openai_client: MagicMock,
    mock_console_display: MagicMock
):
    """Test the full flow for the 'analyze' command.
    Uses real LocalFileSystem, mocked GptClient and ConsoleDisplay.
    """
    file_to_analyze = test_fs / "analyze_files" / "report.txt"
    prompt = "Summarize this report"

    # Use CliRunner to invoke the command
    result = runner.invoke(app, [
        "analyze",
        "--file", str(file_to_analyze),
        prompt
    ])

    # Assert command executed successfully
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"

    # Assert AI client was called correctly
    mock_openai_client.send_prompt.assert_called_once()
    call_args = mock_openai_client.send_prompt.call_args
    sent_prompt = call_args.kwargs['prompt']
    sent_context = call_args.kwargs['context']
    assert sent_prompt == prompt
    assert "This is a test report." in sent_context # Check file content is in context
    assert file_to_analyze.name in sent_context

    # Assert UI methods were called (via mocked ConsoleDisplay)
    mock_console_display.display_info.assert_any_call(f"Reading file: {file_to_analyze}...")
    mock_console_display.display_info.assert_any_call("File read successfully. Sending to AI for analysis...")
    mock_console_display.display_info.assert_any_call("Analysis Result:")
    # Output processor is pass-through, so AI response is displayed directly
    mock_console_display.display_output.assert_called_once_with("Mocked AI integration response")
    mock_console_display.display_error.assert_not_called()

def test_find_command_flow(
    runner: CliRunner,
    test_fs: Path,
    mock_console_display: MagicMock
):
    """Test the full flow for the 'find' command.
    Uses real LocalFileSystem, mocked ConsoleDisplay. No AI involved currently.
    """
    search_pattern = "*.json"
    expected_file = test_fs / "find_files" / "config.json"

    # Change CWD for glob pattern matching relative paths easily
    original_cwd = os.getcwd()
    os.chdir(test_fs / "find_files")
    try:
        result = runner.invoke(app, [
            "find",
            search_pattern
        ])

        # Assert command executed successfully
        assert result.exit_code == 0, f"CLI command failed: {result.stdout}"

        # Assert UI methods were called (via mocked ConsoleDisplay)
        mock_console_display.display_info.assert_any_call(f"Searching for files matching pattern: '{search_pattern}'...")
        mock_console_display.display_info.assert_any_call("Found 1 file(s):")
        # Check that the specific file path was displayed (relative to the CWD we set)
        mock_console_display.display_output.assert_called_once_with(f"- {expected_file.name}")
        mock_console_display.display_error.assert_not_called()
    finally:
        os.chdir(original_cwd) # Change back CWD

def test_find_command_no_results(
    runner: CliRunner,
    test_fs: Path,
    mock_console_display: MagicMock
):
    """Test the 'find' command flow when no files match."""
    search_pattern = "*.nonexistent"

    original_cwd = os.getcwd()
    os.chdir(test_fs / "find_files")
    try:
        result = runner.invoke(app, [
            "find",
            search_pattern
        ])
        assert result.exit_code == 0, f"CLI command failed: {result.stdout}"

        mock_console_display.display_info.assert_any_call(f"Searching for files matching pattern: '{search_pattern}'...")
        mock_console_display.display_info.assert_any_call("No files found matching the pattern.")
        mock_console_display.display_output.assert_not_called()
        mock_console_display.display_error.assert_not_called()
    finally:
        os.chdir(original_cwd)

def test_chat_mode_flow(
    runner: CliRunner,
    mock_openai_client: MagicMock,
    mock_console_display: MagicMock
):
    """Test the basic chat mode flow (start, one interaction, exit)."""
    # Simulate user typing "Hello" then "exit"
    mock_console_display.get_prompt.side_effect = ["Hello there", "exit"]

    # Invoke the app without commands, providing simulated input
    # Note: CliRunner handles stdin via the `input` argument
    result = runner.invoke(app, input="Hello there\nexit\n") # Simulating pressing Enter after each

    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"

    # Check UI calls
    mock_console_display.display_info.assert_any_call("Starting interactive chat session. Type 'exit' or 'quit' to end.")
    assert mock_console_display.get_prompt.call_count == 2
    mock_console_display.get_prompt.assert_has_calls([
        call("You: "),
        call("You: ")
    ])
    # Check AI output display (pass-through processor)
    mock_console_display.display_output.assert_called_once_with("AI: Mocked AI integration response")
    mock_console_display.display_info.assert_any_call("Ending chat session.")
    mock_console_display.display_error.assert_not_called()

    # Check AI call
    mock_openai_client.send_prompt.assert_called_once()
    call_args = mock_openai_client.send_prompt.call_args
    sent_prompt = call_args.kwargs['prompt']
    sent_context = call_args.kwargs['context']
    assert sent_prompt == "Hello there"
    assert "User: Hello there" in sent_context # Basic check of context history 