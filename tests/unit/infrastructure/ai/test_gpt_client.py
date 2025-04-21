import pytest
from unittest.mock import MagicMock, patch
import os
from typing import List, Dict, Any

from goscli.infrastructure.ai.gpt_client import GptClient
from goscli.domain.models.common import PromptText, TokenUsage, MessageRole
from goscli.domain.interfaces.ai_model import ChatMessage, StructuredAIResponse
from openai import OpenAI, AuthenticationError, RateLimitError, APIError

# Fixture to provide a mock OpenAI client instance
@pytest.fixture
def mock_openai_client():
    mock_client = MagicMock(spec=OpenAI)
    # Mock the response structure including usage
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 20
    mock_usage.total_tokens = 30
    
    mock_choice = MagicMock()
    mock_choice.message.content = "Mocked AI response"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage = mock_usage
    
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client

# Use patch to replace the OpenAI() constructor during tests
@patch('goscli.infrastructure.ai.gpt_client.OpenAI')
def test_gpt_client_init_success(mock_openai_constructor, mock_openai_client):
    """Test successful initialization with API key."""
    mock_openai_constructor.return_value = mock_openai_client
    api_key = "test_key"
    client = GptClient(api_key=api_key)
    mock_openai_constructor.assert_called_once_with(api_key=api_key)
    assert client.model == GptClient.DEFAULT_MODEL

@patch('goscli.infrastructure.ai.gpt_client.OpenAI')
def test_gpt_client_init_no_key(mock_openai_constructor):
    """Test initialization failure when no API key is found."""
    # Ensure environment variable is not set for this test
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="OpenAI API key not provided"):
            GptClient(api_key=None)
        mock_openai_constructor.assert_not_called()

@patch('goscli.infrastructure.ai.gpt_client.OpenAI')
def test_send_messages_success(mock_openai_constructor, mock_openai_client):
    """Test sending messages successfully using send_messages."""
    mock_openai_constructor.return_value = mock_openai_client
    client = GptClient(api_key="test_key")
    
    # Prepare messages in the expected format
    test_messages: List[ChatMessage] = [
        {'role': MessageRole('system'), 'content': 'Be helpful.'},
        {'role': MessageRole('user'), 'content': 'Explain Python'}
    ]

    # Call the new method
    response: StructuredAIResponse = client.send_messages(test_messages)

    # Assert response content
    assert response.content == "Mocked AI response"
    
    # Assert token usage parsing
    assert response.token_usage is not None
    assert response.token_usage['prompt_tokens'] == 10
    assert response.token_usage['completion_tokens'] == 20
    assert response.token_usage['total_tokens'] == 30
    
    # Assert API call details
    mock_openai_client.chat.completions.create.assert_called_once()
    call_args = mock_openai_client.chat.completions.create.call_args
    assert call_args.kwargs['model'] == client.model
    assert call_args.kwargs['messages'] == test_messages

# Test different API error scenarios
@pytest.mark.parametrize(
    "error_type, error_message_match",
    [
        (AuthenticationError("Invalid API key", response=MagicMock(), body=None), "authentication error"),
        (RateLimitError("Rate limit exceeded", response=MagicMock(), body=None), "rate limit exceeded"),
        (APIError("Server error", request=MagicMock(), body=None), "API error"),
        (Exception("Unexpected failure"), "Unexpected error"),
    ]
)
@patch('goscli.infrastructure.ai.gpt_client.OpenAI')
@patch('goscli.infrastructure.ai.gpt_client.logger')
def test_send_messages_api_errors(mock_logger, mock_openai_constructor, mock_openai_client, error_type, error_message_match):
    """Test handling of various OpenAI API errors with send_messages."""
    mock_openai_constructor.return_value = mock_openai_client
    mock_openai_client.chat.completions.create.side_effect = error_type

    client = GptClient(api_key="test_key")
    test_messages: List[ChatMessage] = [
        {'role': MessageRole('user'), 'content': 'Test prompt'}
    ]

    with pytest.raises(RuntimeError, match=error_message_match):
        # Call the new method
        client.send_messages(test_messages)

    # Optional: Assert retry attempts if RateLimitError or APIError was raised
    if isinstance(error_type, (RateLimitError, APIError)):
         # tenacity uses call_count on the decorated function itself if called directly
         # or on __wrapped__ if accessed through the instance?
         # Let's assume direct access works for retry object stats
         # Accessing retry state might be tricky/fragile in tests.
         # A simpler check might be to assert logger calls if retrying.
         # For now, just checking the call count on the mock might suffice
         # to ensure it was called multiple times for retryable errors.
         assert mock_openai_client.chat.completions.create.call_count > 1
         # assert client.send_messages.retry.statistics['attempt_number'] > 1 # This might not work directly
    elif isinstance(error_type, AuthenticationError):
        mock_openai_client.chat.completions.create.assert_called_once() # Should fail on first attempt 