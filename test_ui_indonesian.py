#!/usr/bin/env python3
"""
Test script to verify the UI components work correctly with Indonesian text.
"""

import sys
import logging
from datetime import datetime

# Configure logging to see debug messages
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

logger = logging.getLogger(__name__)
logger.info("Starting Indonesian UI test")

try:
    # Import the ConsoleDisplay class
    from goscli.infrastructure.cli.display import ConsoleDisplay
    from goscli.domain.models.common import PromptText
    
    # Create an instance of ConsoleDisplay
    ui = ConsoleDisplay()
    
    # Test the session header
    ui.display_session_header("TestProvider")
    
    # Test different message types with Indonesian text
    ui.display_output("Ini adalah pesan biasa", title="AI")
    ui.display_output("```python\nprint('Halo Dunia')\n```", title="AI", message_type="code")
    ui.display_output("Contoh pesan pengguna dalam bahasa Indonesia", title="You")
    
    # Test thinking indicator with Indonesian message
    ui.display_thinking()
    
    # Test info, warning, and error messages with Indonesian text
    ui.display_info("Ini adalah pesan informasi dalam bahasa Indonesia")
    ui.display_warning("Ini adalah pesan peringatan dalam bahasa Indonesia")
    ui.display_error("Ini adalah pesan kesalahan dalam bahasa Indonesia")
    
    # Create mock history with Indonesian content for testing
    from goscli.domain.models.chat import Message, MessageRole
    history = [
        Message(role=MessageRole("user"), content=PromptText("Halo AI"), timestamp=datetime.now().timestamp()),
        Message(role=MessageRole("assistant"), content=PromptText("Halo manusia"), timestamp=datetime.now().timestamp()),
        Message(role=MessageRole("user"), content=PromptText("Apa kabar?"), timestamp=datetime.now().timestamp()),
        Message(role=MessageRole("assistant"), content=PromptText("Saya baik-baik saja, terima kasih!"), timestamp=datetime.now().timestamp())
    ]
    
    # Test chat history display with Indonesian content
    ui.display_chat_history(history)
    
    # Test session footer
    ui.display_session_footer(4, 120)
    
    logger.info("Indonesian UI test completed successfully")
except Exception as e:
    logger.error(f"Indonesian UI test failed: {e}", exc_info=True)
    sys.exit(1) 