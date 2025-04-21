import logging

# Convert to absolute imports
from goscli.domain.interfaces.output_processor import OutputProcessor, RawOutput, ProcessedOutput

logger = logging.getLogger(__name__)

class BasicProcessor(OutputProcessor):
    """Processes and potentially reformats the raw AI output.
    
    Provides a clean fallback implementation.
    """
    
    def __init__(self):
        """Initializes the basic processor."""
        logger.info("BasicProcessor initialized.")

    def process_output(self, raw_output: RawOutput) -> ProcessedOutput:
        """Processes the AI output to prepare for display.
        
        In this basic implementation, it passes through the raw text unchanged.
        
        Args:
            raw_output: The raw output from the AI model.
            
        Returns:
            The processed output, which is identical to the input in this case.
        """
        return ProcessedOutput(str(raw_output)) 