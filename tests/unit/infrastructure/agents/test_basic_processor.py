import pytest

from goscli.infrastructure.agents.basic_processor import BasicProcessor
from goscli.domain.interfaces.output_processor import RawOutput, ProcessedOutput

def test_basic_processor_passthrough():
    """Test that the basic processor currently passes the input through unchanged."""
    processor = BasicProcessor()
    raw_input = RawOutput("This is the raw input. \n With newlines.  ")
    expected_output = ProcessedOutput("This is the raw input. \n With newlines.  ")

    actual_output = processor.process_output(raw_input)

    assert actual_output == expected_output
    # Ensure the type is also correct
    assert isinstance(actual_output, ProcessedOutput) 