"""Tests for utility functions."""

import os
import pytest
from botocore.exceptions import ClientError


def test_call_llm_basic(mocker):
    """Test basic LLM call with mocked bedrock client."""
    from hackathon_science.utils import DEFAULT_MAX_TOKENS, call_llm

    # Mock the boto3 client
    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client

    # Mock the converse response
    mock_response = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Hello! How can I help?"}]
            }
        },
        "stopReason": "end_turn",
        "usage": {
            "inputTokens": 10,
            "outputTokens": 5
        }
    }
    mock_client.converse.return_value = mock_response

    # Call the function
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    result = call_llm(messages, model_id="anthropic.claude-3-sonnet-20240229-v1:0")

    # Verify boto3 client was created correctly
    mock_boto3.client.assert_called_once_with("bedrock-runtime", region_name="us-east-1")

    # Verify converse was called with correct parameters
    mock_client.converse.assert_called_once_with(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        messages=messages,
        inferenceConfig={"maxTokens": DEFAULT_MAX_TOKENS}
    )

    # Verify the result
    assert result == mock_response


def test_call_llm_with_tools(mocker):
    """Test LLM call with tools parameter."""
    from hackathon_science.utils import DEFAULT_MAX_TOKENS, call_llm

    # Mock the boto3 client
    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client

    # Mock the converse response
    mock_response = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"toolUse": {"toolUseId": "123", "name": "search", "input": {}}}]
            }
        },
        "stopReason": "tool_use"
    }
    mock_client.converse.return_value = mock_response

    # Call with tools
    messages = [{"role": "user", "content": [{"text": "Search for papers"}]}]
    tools = [{"toolSpec": {"name": "search", "description": "Search papers"}}]
    result = call_llm(messages, model_id="anthropic.claude-3-sonnet-20240229-v1:0", tools=tools)

    # Verify converse was called with toolConfig
    mock_client.converse.assert_called_once_with(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        messages=messages,
        inferenceConfig={"maxTokens": DEFAULT_MAX_TOKENS},
        toolConfig={"tools": tools}
    )

    assert result == mock_response


def test_call_llm_with_region(mocker):
    """Test LLM call with custom region."""
    from hackathon_science.utils import call_llm

    # Mock the boto3 client
    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client

    mock_response = {"output": {"message": {"role": "assistant", "content": [{"text": "Hi"}]}}}
    mock_client.converse.return_value = mock_response

    # Call with custom region
    messages = [{"role": "user", "content": [{"text": "Hi"}]}]
    call_llm(messages, model_id="anthropic.claude-3-sonnet-20240229-v1:0", region="us-west-2")

    # Verify region was passed to boto3 client
    mock_boto3.client.assert_called_once_with("bedrock-runtime", region_name="us-west-2")


def test_call_llm_uses_custom_inference_config(mocker):
    """Test LLM call preserves caller inference config overrides."""
    from hackathon_science.utils import call_llm

    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client
    mock_client.converse.return_value = {"output": {"message": {"content": []}}}

    messages = [{"role": "user", "content": [{"text": "Hi"}]}]
    inference_config = {"maxTokens": 1234, "temperature": 0.1}

    call_llm(
        messages,
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        inferenceConfig=inference_config,
    )

    mock_client.converse.assert_called_once_with(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        messages=messages,
        inferenceConfig={"maxTokens": 1234, "temperature": 0.1}
    )
    assert inference_config == {"maxTokens": 1234, "temperature": 0.1}


def test_call_llm_retry_on_throttling(mocker):
    """Test retry logic when throttling exception occurs."""
    from hackathon_science.utils import call_llm

    # Mock the boto3 client
    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client

    # Mock sleep to avoid actual delays in tests
    mock_sleep = mocker.patch("hackathon_science.utils.time.sleep")

    # First call raises ThrottlingException, second succeeds
    throttling_error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "converse"
    )
    mock_response = {"output": {"message": {"role": "assistant", "content": [{"text": "Success"}]}}}

    mock_client.converse.side_effect = [throttling_error, mock_response]

    # Call the function
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    result = call_llm(messages, model_id="anthropic.claude-3-sonnet-20240229-v1:0")

    # Verify converse was called twice (first failed, second succeeded)
    assert mock_client.converse.call_count == 2

    # Verify sleep was called with exponential backoff (2^0 = 1 second for first retry)
    mock_sleep.assert_called_once_with(1)

    # Verify the result is from the successful call
    assert result == mock_response


def test_call_llm_retry_exponential_backoff(mocker):
    """Test exponential backoff timing in retry logic."""
    from hackathon_science.utils import call_llm

    # Mock the boto3 client
    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client

    # Mock sleep
    mock_sleep = mocker.patch("hackathon_science.utils.time.sleep")

    # First two calls fail with throttling, third succeeds
    throttling_error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "converse"
    )
    mock_response = {"output": {"message": {"role": "assistant", "content": [{"text": "Success"}]}}}

    mock_client.converse.side_effect = [throttling_error, throttling_error, mock_response]

    # Call the function
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    result = call_llm(messages, model_id="anthropic.claude-3-sonnet-20240229-v1:0")

    # Verify converse was called three times
    assert mock_client.converse.call_count == 3

    # Verify sleep was called with exponential backoff: 2^0=1, 2^1=2
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list[0][0][0] == 1  # First retry: 2^0 = 1
    assert mock_sleep.call_args_list[1][0][0] == 2  # Second retry: 2^1 = 2

    assert result == mock_response


def test_call_llm_max_retries_exhausted(mocker):
    """Test that exception is raised after max retries are exhausted."""
    from hackathon_science.utils import call_llm

    # Mock the boto3 client
    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client

    # Mock sleep
    mock_sleep = mocker.patch("hackathon_science.utils.time.sleep")

    # All calls fail with throttling
    throttling_error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "converse"
    )
    mock_client.converse.side_effect = throttling_error

    # Call the function with max_retries=3
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]

    with pytest.raises(ClientError) as exc_info:
        call_llm(messages, model_id="anthropic.claude-3-sonnet-20240229-v1:0", max_retries=3)

    # Verify it's the throttling error
    assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"

    # Verify converse was called 4 times (initial + 3 retries)
    assert mock_client.converse.call_count == 4

    # Verify sleep was called 3 times (for the 3 retries)
    assert mock_sleep.call_count == 3


def test_call_llm_non_throttling_error_no_retry(mocker):
    """Test that non-throttling errors are not retried."""
    from hackathon_science.utils import call_llm

    # Mock the boto3 client
    mock_client = mocker.MagicMock()
    mock_boto3 = mocker.patch("hackathon_science.utils.boto3")
    mock_boto3.client.return_value = mock_client

    # Mock sleep
    mock_sleep = mocker.patch("hackathon_science.utils.time.sleep")

    # Call fails with a different error
    validation_error = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "Invalid input"}},
        "converse"
    )
    mock_client.converse.side_effect = validation_error

    # Call the function
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]

    with pytest.raises(ClientError) as exc_info:
        call_llm(messages, model_id="anthropic.claude-3-sonnet-20240229-v1:0")

    # Verify it's the validation error
    assert exc_info.value.response["Error"]["Code"] == "ValidationException"

    # Verify converse was called only once (no retries)
    assert mock_client.converse.call_count == 1

    # Verify sleep was never called
    mock_sleep.assert_not_called()


def test_call_llm_openai_basic(mocker):
    """Test basic LLM call with OpenAI model."""
    from hackathon_science.utils import DEFAULT_MAX_TOKENS, call_llm

    # Mock OpenAI client
    mock_openai_class = mocker.MagicMock()
    mock_client = mocker.MagicMock()
    mock_openai_class.return_value = mock_client

    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    # Patch at the point of import within the function
    mocker.patch("openai.OpenAI", mock_openai_class)

    # Mock the OpenAI response
    mock_choice = mocker.MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "Hello! How can I help?"
    mock_choice.message.tool_calls = None
    mock_choice.finish_reason = "stop"

    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15

    mock_client.chat.completions.create.return_value = mock_response

    # Call the function with OpenAI model
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    result = call_llm(messages, model_id="gpt-4o")

    # Verify OpenAI client was created
    mock_openai_class.assert_called_once_with(api_key="test-key")

    # Verify chat.completions.create was called with correct parameters
    mock_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=DEFAULT_MAX_TOKENS
    )

    # Verify the result is in Bedrock format
    assert result["output"]["message"]["role"] == "assistant"
    assert result["output"]["message"]["content"][0]["text"] == "Hello! How can I help?"
    assert result["stopReason"] == "end_turn"
    assert result["usage"]["inputTokens"] == 10
    assert result["usage"]["outputTokens"] == 5


def test_call_llm_openai_with_tools(mocker):
    """Test OpenAI LLM call with tools parameter."""
    from hackathon_science.utils import call_llm

    # Mock OpenAI client
    mock_openai_class = mocker.MagicMock()
    mock_client = mocker.MagicMock()
    mock_openai_class.return_value = mock_client

    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    mocker.patch("openai.OpenAI", mock_openai_class)

    # Mock tool call response
    mock_tool_call = mocker.MagicMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "search"
    mock_tool_call.function.arguments = '{"query": "papers"}'

    mock_choice = mocker.MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = None
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.finish_reason = "tool_calls"

    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15

    mock_client.chat.completions.create.return_value = mock_response

    # Call with tools
    messages = [{"role": "user", "content": [{"text": "Search for papers"}]}]
    tools = [{"toolSpec": {"name": "search", "description": "Search papers", "inputSchema": {}}}]
    result = call_llm(messages, model_id="gpt-4o", tools=tools)

    # Verify tools were converted to OpenAI format
    call_args = mock_client.chat.completions.create.call_args[1]
    assert "tools" in call_args
    assert call_args["tools"][0]["type"] == "function"
    assert call_args["tools"][0]["function"]["name"] == "search"

    # Verify response includes tool use
    assert "toolUse" in result["output"]["message"]["content"][0]
    assert result["output"]["message"]["content"][0]["toolUse"]["name"] == "search"


def test_call_llm_openai_missing_api_key(mocker):
    """Test that OpenAI call fails without API key."""
    from hackathon_science.utils import call_llm

    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("openai.OpenAI")

    messages = [{"role": "user", "content": [{"text": "Hello"}]}]

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        call_llm(messages, model_id="gpt-4o")


def test_call_llm_openai_retry_on_rate_limit(mocker):
    """Test retry logic for OpenAI rate limit errors."""
    from hackathon_science.utils import call_llm

    # Mock OpenAI client
    mock_openai_class = mocker.MagicMock()
    mock_client = mocker.MagicMock()
    mock_openai_class.return_value = mock_client

    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    mocker.patch("openai.OpenAI", mock_openai_class)

    # Mock RateLimitError
    from unittest.mock import Mock
    RateLimitError = type('RateLimitError', (Exception,), {})
    mocker.patch("openai.RateLimitError", RateLimitError)

    # Mock sleep
    mock_sleep = mocker.patch("hackathon_science.utils.time.sleep")

    # First call raises RateLimitError, second succeeds
    mock_choice = mocker.MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "Success"
    mock_choice.message.tool_calls = None
    mock_choice.finish_reason = "stop"

    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15

    mock_client.chat.completions.create.side_effect = [
        RateLimitError("Rate limit exceeded"),
        mock_response
    ]

    # Call the function
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    result = call_llm(messages, model_id="gpt-4o")

    # Verify create was called twice
    assert mock_client.chat.completions.create.call_count == 2

    # Verify sleep was called
    mock_sleep.assert_called_once_with(1)

    # Verify success
    assert result["output"]["message"]["content"][0]["text"] == "Success"


def test_call_llm_is_openai_model():
    """Test model ID detection for OpenAI vs Bedrock."""
    from hackathon_science.utils import _is_openai_model

    # OpenAI models
    assert _is_openai_model("gpt-4o") is True
    assert _is_openai_model("gpt-4-turbo") is True
    assert _is_openai_model("gpt-3.5-turbo") is True
    assert _is_openai_model("o1-preview") is True
    assert _is_openai_model("o3-mini") is True

    # Bedrock models
    assert _is_openai_model("us.anthropic.claude-sonnet-4-5-20250929-v1:0") is False
    assert _is_openai_model("anthropic.claude-3-sonnet-20240229-v1:0") is False
    assert _is_openai_model("global.anthropic.claude-opus-4-7") is False
