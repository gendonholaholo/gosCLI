import logging
import time
from datetime import datetime
from typing import Optional, Any, Dict, List
try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.box import ROUNDED, HEAVY, SIMPLE
from rich.text import Text
from rich.table import Table
from rich.align import Align

from goscli.domain.interfaces.user_interface import UserInterface
from goscli.domain.models.common import PromptText, ProcessedOutput

logger = logging.getLogger(__name__)

class ConsoleDisplay(UserInterface):
    """Concrete implementation of UserInterface using the rich library for console output."""

    def __init__(self):
        """Initializes the rich Console."""
        self._console = Console()
        self.session_start_time = time.time()
        self.message_count = 0
        self.last_sender = None

    @property
    def console(self):
        """Get the Rich console instance for direct operations."""
        return self._console

    def display_output(self, output: ProcessedOutput, **kwargs: Any) -> None:
        """Displays output text to the user, rendering Markdown with enhanced styling.

        Args:
            output: The processed output string to display.
            **kwargs: Additional arguments including:
                - title: The title/sender of the message (default: "AI")
                - style: Style override for the panel
                - message_type: Type of message ("normal", "code", "thinking")
        """
        title = kwargs.get("title", "AI")
        message_type = kwargs.get("message_type", "normal")
        self.message_count += 1
        
        # DEBUG: Log message details
        logger.debug(f"display_output called: title={title}, message_type={message_type}, content_length={len(str(output))}")
        
        # Determine if this is a continuation of messages from the same sender
        is_continuation = self.last_sender == title
        self.last_sender = title
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create different styling based on the sender and message type
        if title.lower() == "ai":
            # AI message styling
            if message_type == "thinking":
                box_style = SIMPLE
                style = "cyan on dark_blue"
                title_style = "bold cyan"
                timestamp_style = "dim cyan"
                header = f"[{title_style}]{title} thinking...[/{title_style}] [dim]·[/dim] [{timestamp_style}]{timestamp}[/{timestamp_style}]"
                logger.debug("Using 'thinking' message style")
            elif message_type == "code":
                box_style = ROUNDED
                style = "purple on dark_blue"
                title_style = "bold white"
                timestamp_style = "dim white"
                header = f"[{title_style}]{title} [bright_purple]code[/bright_purple][/{title_style}] [dim]·[/dim] [{timestamp_style}]{timestamp}[/{timestamp_style}]"
                logger.debug("Using 'code' message style")
            else:
                box_style = ROUNDED
                style = "blue on dark_blue"
                title_style = "bold white"
                timestamp_style = "dim white"
                header = f"[{title_style}]{title}[/{title_style}] [dim]·[/dim] [{timestamp_style}]{timestamp}[/{timestamp_style}]"
                logger.debug("Using standard AI message style")
        else:
            # User message styling
            box_style = SIMPLE
            style = "green on dark_green"
            title_style = "bold white"
            timestamp_style = "dim white"
            header = f"[{title_style}]{title}[/{title_style}] [dim]·[/dim] [{timestamp_style}]{timestamp}[/{timestamp_style}]"
            logger.debug("Using user message style")
        
        # Add a small spacing above if not a continuation
        if not is_continuation:
            logger.debug("Adding spacing for new message (not continuation)")
            self.console.print("")
        
        # Process content for enhanced code block rendering
        output_str = str(output)
        
        try:
            # Create a panel with the message content
            panel = Panel(
                Markdown(output_str),
                title=header,
                title_align="left",
                border_style=style,
                box=box_style,
                padding=(0, 1)
            )
            
            # Attempt to print the panel
            self.console.print(panel)
            logger.debug("Successfully displayed message panel")
        except Exception as e:
            # Fallback if Rich formatting fails
            logger.error(f"Error displaying formatted message: {e}")
            logger.debug("Falling back to plain text output")
            self.console.print(f"\n{title} ({timestamp}):\n{output_str}\n")

    def get_prompt(self, prompt_message: str = "> ") -> PromptText:
        """Gets input prompt from the user using rich console with enhanced styling.

        Args:
            prompt_message: The message to display before the input cursor.

        Returns:
            The text input by the user.
        """
        # Reset last sender when prompting for input
        self.last_sender = None
        
        # Create a nicely styled input prompt
        prompt_style = "[bold green on dark_green]"
        end_style = "[/bold green on dark_green]"
        
        # Add a small spacing before input
        self.console.print("")
        
        # Get user input with styled prompt
        user_input = self.console.input(f"{prompt_style} {prompt_message} {end_style} ")
        
        # Increment message counter for consistency
        self.message_count += 1
        
        return PromptText(user_input)

    def display_error(self, error_message: str, **kwargs: Any) -> None:
        """Displays an error message in a distinct style.

        Args:
            error_message: The error message to display.
        """
        panel = Panel(
            Text(error_message, style="white"),
            title="[bold red]Error[/bold red]",
            border_style="red",
            box=HEAVY,
            padding=(0, 1)
        )
        self.console.print(panel)

    def display_info(self, info_message: str, **kwargs: Any) -> None:
        """Displays an informational message with enhanced styling.

        Args:
            info_message: The informational message to display.
        """
        panel = Panel(
            Text(info_message, style="white"),
            title="[bold blue]Info[/bold blue]",
            border_style="blue",
            box=SIMPLE,
            padding=(0, 1)
        )
        self.console.print(panel)

    def display_warning(self, warning_message: str, **kwargs: Any) -> None:
        """Displays a warning message with enhanced styling.
        
        Args:
            warning_message: The warning message to display.
        """
        logger.warning(f"Display warning: {warning_message}")
        panel = Panel(
            Text(warning_message, style="white"),
            title="[bold yellow]Warning[/bold yellow]",
            border_style="yellow",
            box=HEAVY,
            padding=(0, 1)
        )
        self.console.print(panel)

    def display_session_header(self, provider_name: str = "AI") -> None:
        """Displays a stylized header for a new chat session.
        
        Args:
            provider_name: Name of the AI provider
        """
        logger.debug(f"Displaying session header for provider: {provider_name}")
        try:
            # Create a header table
            table = Table(show_header=False, box=ROUNDED, border_style="cyan", padding=(0, 1))
            table.add_column("Content", style="cyan")
            
            # Add session info rows
            table.add_row(f"[bold cyan]GosCLI Interactive Chat Session[/bold cyan]")
            table.add_row(f"AI Provider: [bold]{provider_name}[/bold]")
            table.add_row(f"Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            table.add_row("Type 'exit' or 'quit' to end the session")
            
            # Create a centered aligned panel
            aligned_table = Align.center(table)
            self.console.print("")
            self.console.print(aligned_table)
            self.console.print("")
            logger.debug("Session header displayed successfully")
        except Exception as e:
            logger.error(f"Error displaying session header: {e}")
            # Fallback to simple text
            self.console.print(f"\n=== GosCLI Interactive Chat Session ===")
            self.console.print(f"AI Provider: {provider_name}")
            self.console.print(f"Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.console.print("Type 'exit' or 'quit' to end the session\n")
    
    def display_session_footer(self, message_count: int, session_duration_secs: float) -> None:
        """Displays a stylized footer at the end of a chat session.
        
        Args:
            message_count: Number of messages exchanged
            session_duration_secs: Session duration in seconds
        """
        logger.debug(f"Displaying session footer: {message_count} messages, {session_duration_secs:.2f} seconds")
        try:
            # Format duration nicely
            minutes, seconds = divmod(int(session_duration_secs), 60)
            hours, minutes = divmod(minutes, 60)
            duration_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"
            
            # Create a footer table
            table = Table(show_header=False, box=SIMPLE, border_style="cyan", padding=(0, 1))
            table.add_column("Content", style="cyan")
            
            # Add session summary
            table.add_row(f"[bold cyan]Chat Session Summary[/bold cyan]")
            table.add_row(f"Messages exchanged: [bold]{message_count}[/bold]")
            table.add_row(f"Session duration: [bold]{duration_str}[/bold]")
            table.add_row(f"Session ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Create a centered aligned panel
            aligned_table = Align.center(table)
            self.console.print("")
            self.console.print(aligned_table)
            self.console.print("")
            logger.debug("Session footer displayed successfully")
        except Exception as e:
            logger.error(f"Error displaying session footer: {e}")
            # Fallback to simple text
            self.console.print("\n=== Chat Session Summary ===")
            self.console.print(f"Messages exchanged: {message_count}")
            minutes, seconds = divmod(int(session_duration_secs), 60)
            hours, minutes = divmod(minutes, 60)
            duration_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"
            self.console.print(f"Session duration: {duration_str}")
            self.console.print(f"Session ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    def display_chat_history(self, history: List[Any], **kwargs: Any) -> None:
        """Displays the chat history with enhanced styling.
        
        Args:
            history: List of chat message objects
            **kwargs: Additional display options
        """
        logger.debug(f"Displaying chat history with {len(history)} messages")
        
        try:
            # Create a table for the chat history
            table = Table(show_header=True, box=ROUNDED, border_style="cyan", padding=(0, 1))
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Time", style="dim")
            table.add_column("Role", style="bold")
            table.add_column("Message", style="white")
            
            # Add each message to the table
            for i, message in enumerate(history, 1):
                try:
                    # Get message properties
                    role = message.role.capitalize()
                    timestamp = datetime.fromtimestamp(message.timestamp).strftime("%H:%M:%S")
                    
                    # Format the content (truncate if too long)
                    content = str(message.content)
                    if len(content) > 100:
                        content = content[:97] + "..."
                    
                    # Apply styling based on role
                    role_style = "bold green" if role.lower() == "user" else "bold blue"
                    
                    # Add row to table
                    table.add_row(
                        str(i),
                        timestamp,
                        f"[{role_style}]{role}[/{role_style}]",
                        content
                    )
                    logger.debug(f"Added history message {i}: {role} at {timestamp}")
                except AttributeError as e:
                    logger.error(f"Error accessing message attributes for history item {i}: {e}")
                    # Add a row with error information
                    table.add_row(
                        str(i),
                        "???",
                        "[bold red]Error[/bold red]",
                        f"Could not display message: {e}"
                    )
                except Exception as e:
                    logger.error(f"Unexpected error processing history item {i}: {e}")
                    table.add_row(
                        str(i),
                        "???",
                        "[bold red]Error[/bold red]",
                        f"Unexpected error: {e}"
                    )
            
            # Create a header
            self.console.print("")
            self.console.print(Panel(
                Text("Chat History", justify="center"),
                border_style="cyan",
                box=SIMPLE
            ))
            
            # Print the table
            self.console.print(table)
            self.console.print("")
            logger.debug("Chat history displayed successfully")
        except Exception as e:
            logger.error(f"Failed to display chat history: {e}")
            self.display_error(f"Could not display chat history: {e}")

    def display_thinking(self, **kwargs: Any) -> None:
        """Displays a 'thinking' indicator while the AI is processing.
        
        Args:
            **kwargs: Additional display options like message
        """
        logger.debug(f"Displaying thinking indicator with kwargs: {kwargs}")
        message = kwargs.get("message", "Thinking...")
        try:
            self.display_output(message, title="AI", message_type="thinking")
            logger.debug("Thinking indicator displayed successfully")
        except Exception as e:
            logger.error(f"Error displaying thinking indicator: {e}", exc_info=True)
            # Fallback to simple text
            self.console.print(f"\nAI is {message}\n")

    def ask_yes_no_question(self, question: str) -> bool:
        """Asks a yes/no question and returns the answer.
        
        Args:
            question: The question to ask
            
        Returns:
            True if the answer is yes, False otherwise
        """
        logger.debug(f"Asking yes/no question: {question}")
        
        try:
            # Create a styled panel for the question
            panel = Panel(
                Text(f"{question} (y/n)", style="white"),
                title="[bold yellow]Question[/bold yellow]",
                border_style="yellow",
                box=ROUNDED,
                padding=(0, 1)
            )
            
            # Print the question panel
            self.console.print(panel)
            
            # Get user input
            response = self.console.input("[bold yellow]> [/bold yellow]").strip().lower()
            
            # Return True for 'y' or 'yes', False otherwise
            return response in ('y', 'yes')
            
        except Exception as e:
            logger.error(f"Error asking yes/no question: {e}")
            # Fallback to simple question
            print(f"\n{question} (y/n)")
            response = input("> ").strip().lower()
            return response in ('y', 'yes')

    def ask_diagram_size(self) -> int:
        """Asks the user to select a size for the Mermaid diagram.
        
        Returns:
            The selected size (width/height in pixels)
        """
        logger.debug("Asking for diagram size selection")
        
        try:
            # Create a styled panel with size options
            panel = Panel(
                Text("Select diagram size:\n1. Small (1000x1000 pixels)\n2. Medium (2000x2000 pixels)\n3. Large (4000x4000 pixels) [default]", style="white"),
                title="[bold blue]Diagram Size Selection[/bold blue]",
                border_style="blue",
                box=ROUNDED,
                padding=(0, 1)
            )
            
            # Print the options panel
            self.console.print(panel)
            
            # Get user input
            response = self.console.input("[bold blue]> [/bold blue]").strip()
            
            # Return size based on selection
            if response == "1":
                logger.debug("User selected size: 1000x1000")
                return 1000
            elif response == "2":
                logger.debug("User selected size: 2000x2000")
                return 2000
            else:
                # Default to 4000 for any other input including blank
                logger.debug("User selected size: 4000x4000 (default)")
                return 4000
            
        except Exception as e:
            logger.error(f"Error asking for diagram size: {e}")
            # Fallback to default size
            logger.debug("Error occurred, returning default size (4000)")
            return 4000 