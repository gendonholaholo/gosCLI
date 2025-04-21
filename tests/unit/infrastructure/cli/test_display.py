import pytest
from unittest.mock import MagicMock, call

from goscli.infrastructure.cli.display import ConsoleDisplay
from goscli.domain.interfaces.user_interface import OutputText, PromptInput

@pytest.fixture
def mock_console():
    """Fixture to create a mock rich Console object."""
    return MagicMock()

@pytest.fixture
def console_display(mock_console: MagicMock):
    """Fixture to create a ConsoleDisplay instance with a mocked console."""
    display = ConsoleDisplay()
    display.console = mock_console # Inject the mock
    return display

def test_display_output(console_display: ConsoleDisplay, mock_console: MagicMock):
    """Test that display_output calls console.print with Markdown."""
    test_text = OutputText("Hello **World**")
    console_display.display_output(test_text)
    # Check that print was called once
    mock_console.print.assert_called_once()
    # Check that the argument passed to print was a Markdown object
    args, kwargs = mock_console.print.call_args
    assert len(args) == 1
    assert hasattr(args[0], 'markup') # Check if it behaves like a Markdown object
    assert args[0].markup == "Hello **World**"

def test_get_prompt(console_display: ConsoleDisplay, mock_console: MagicMock):
    """Test that get_prompt calls console.input and returns the result."""
    expected_input = "user input"
    mock_console.input.return_value = expected_input
    prompt_msg = "> "

    actual_input = console_display.get_prompt(prompt_msg)

    mock_console.input.assert_called_once_with(f"[bold green]{prompt_msg}[/bold green]")
    assert actual_input == PromptInput(expected_input)

def test_display_error(console_display: ConsoleDisplay, mock_console: MagicMock):
    """Test that display_error calls console.print with error formatting."""
    error_msg = "Something went wrong"
    console_display.display_error(error_msg)
    mock_console.print.assert_called_once_with(f"[bold red]Error:[/bold red] {error_msg}")

def test_display_info(console_display: ConsoleDisplay, mock_console: MagicMock):
    """Test that display_info calls console.print with info formatting."""
    info_msg = "Process completed"
    console_display.display_info(info_msg)
    mock_console.print.assert_called_once_with(f"[blue]Info:[/blue] {info_msg}") 