#!/usr/bin/env python3
"""
Simple test script for the enhanced UI components.
"""

import sys
import logging
from datetime import datetime

# Configure logging to see debug messages
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

logger = logging.getLogger(__name__)
logger.info("Starting UI test")

try:
    # Import the ConsoleDisplay class
    from goscli.infrastructure.cli.display import ConsoleDisplay
    from goscli.domain.models.common import PromptText
    
    # Create an instance of ConsoleDisplay
    ui = ConsoleDisplay()
    
    # Test the session header
    ui.display_session_header("TestProvider")
    
    # Test different message types
    ui.display_output("This is a regular message", title="AI")
    ui.display_output("```python\nprint('Hello World')\n```", title="AI", message_type="code")
    ui.display_output("User message example", title="You")
    
    # Test thinking indicator
    ui.display_thinking()
    
    # Test info, warning, and error messages
    ui.display_info("This is an information message")
    ui.display_warning("This is a warning message")
    ui.display_error("This is an error message")
    
    # Create mock history for testing
    from goscli.domain.models.chat import Message, MessageRole
    history = [
        Message(role=MessageRole("user"), content=PromptText("Hello AI"), timestamp=datetime.now().timestamp()),
        Message(role=MessageRole("assistant"), content=PromptText("Hello human"), timestamp=datetime.now().timestamp()),
        Message(role=MessageRole("user"), content=PromptText("How are you?"), timestamp=datetime.now().timestamp()),
        Message(role=MessageRole("assistant"), content=PromptText("I'm doing well, thank you!"), timestamp=datetime.now().timestamp())
    ]
    
    # Test chat history display
    ui.display_chat_history(history)
    
    # Test session footer
    ui.display_session_footer(4, 120)
    
    logger.info("UI test completed successfully")
except Exception as e:
    logger.error(f"UI test failed: {e}", exc_info=True)
    sys.exit(1) 