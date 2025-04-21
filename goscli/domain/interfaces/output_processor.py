from abc import ABC, abstractmethod

RawOutput = str # Placeholder for raw AI output
ProcessedOutput = str # Placeholder for processed output

class OutputProcessor(ABC):
    """Interface for processing (enhancing) raw AI output."""

    @abstractmethod
    def process_output(self, raw_output: RawOutput) -> ProcessedOutput:
        """Processes the raw output from the AI model.

        Args:
            raw_output: The raw text received from the AI model.

        Returns:
            The processed/enhanced output text.
        """
        pass 