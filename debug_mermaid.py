#!/usr/bin/env python3
"""
Debug script to test Mermaid diagram detection and generation directly.
"""

import logging
import sys
import os
from goscli.utils.mermaid_generator import MermaidGenerator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("debug_mermaid")

def test_mermaid_detection():
    """Test the Mermaid diagram detection function."""
    logger.info("Testing Mermaid diagram detection")
    
    generator = MermaidGenerator()
    
    # Test sample Mermaid diagram
    mermaid_sample = """
Here's a simple diagram:

```mermaid
graph TD
    A[Start] --> B{Is it working?}
    B -->|Yes| C[Great!]
    B -->|No| D[Debug]
    D --> B
    C --> E[End]
```

End of diagram.
"""
    
    logger.info(f"Sample text length: {len(mermaid_sample)}")
    
    # Detect Mermaid blocks
    blocks = generator.detect_mermaid_blocks(mermaid_sample)
    
    logger.info(f"Detected {len(blocks)} Mermaid blocks")
    
    # Log the detected blocks
    for i, block in enumerate(blocks):
        logger.info(f"Block {i+1}:\n{block}")
    
    # Check if mmdc is installed
    is_installed = generator.is_mmdc_installed()
    logger.info(f"mmdc installation check: {is_installed}")
    
    # If installed, try generating a diagram
    if is_installed:
        if blocks:
            logger.info("Attempting to generate diagram")
            success, file_path = generator.generate_diagram(blocks[0], size=1000)
            logger.info(f"Diagram generation: success={success}, file_path={file_path}")
            
            if success and file_path:
                logger.info(f"Generated diagram at: {file_path}")
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(file_path)
                except Exception as e:
                    logger.error(f"Error opening diagram: {e}")
        else:
            logger.warning("No blocks detected, skipping diagram generation")
    else:
        logger.warning("mmdc is not installed, skipping diagram generation")

if __name__ == "__main__":
    logger.info(f"Starting Mermaid debug test on Python {sys.version}")
    logger.info(f"Current directory: {os.getcwd()}")
    test_mermaid_detection()
    logger.info("Debug test completed") 