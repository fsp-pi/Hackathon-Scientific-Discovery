"""Utility functions for the Hackathon Science platform."""

import os
import time
import boto3
from botocore.exceptions import ClientError


DEFAULT_MAX_TOKENS = 8000


def _is_openai_model(model_id: str) -> bool:
    """Check if model_id indicates an OpenAI model."""
    openai_prefixes = ("gpt-", "o1-", "o3-")
    return model_id.startswith(openai_prefixes)


def _call_bedrock_llm(
    messages: list,
    model_id: str,
    region: str,
    tools: list,
    max_retries: int,
    **kwargs
) -> dict:
    """Call AWS Bedrock with retry logic."""
    client = boto3.client("bedrock-runtime", region_name=region)

    inference_config = dict(kwargs.pop("inferenceConfig", None) or {})
    inference_config.setdefault("maxTokens", DEFAULT_MAX_TOKENS)

    request_params = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": inference_config,
        **kwargs
    }

    if tools is not None:
        # Convert tools to Bedrock format (wrap inputSchema in {"json": ...})
        bedrock_tools = []
        for tool in tools:
            if "toolSpec" in tool:
                spec = tool["toolSpec"].copy()
                # If inputSchema is a plain object, wrap it in {"json": ...}
                if "inputSchema" in spec and "json" not in spec["inputSchema"]:
                    spec["inputSchema"] = {"json": spec["inputSchema"]}
                bedrock_tools.append({"toolSpec": spec})
            else:
                bedrock_tools.append(tool)
        request_params["toolConfig"] = {"tools": bedrock_tools}

    for attempt in range(max_retries + 1):
        try:
            response = client.converse(**request_params)
            return response
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ThrottlingException" and attempt < max_retries:
                sleep_time = 2 ** attempt
                time.sleep(sleep_time)
                continue
            if error_code in ("ExpiredToken", "ExpiredTokenException"):
                raise RuntimeError(
                    "AWS credentials have expired. Open the Settings page in "
                    "the web app, click 'Regenerate Bedrock Credentials', "
                    "re-export the new block in your shell, and re-run."
                ) from e
            raise


def _call_openai_llm(
    messages: list,
    model_id: str,
    tools: list,
    max_retries: int,
    **kwargs
) -> dict:
    """Call OpenAI API with retry logic."""
    try:
        from openai import OpenAI, RateLimitError
    except ImportError:
        raise ImportError(
            "OpenAI package required for OpenAI models. Install with: pip install openai"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)

    # Extract max_tokens from kwargs or use default
    max_tokens = kwargs.pop("max_tokens", None)
    inference_config = kwargs.pop("inferenceConfig", None)
    if inference_config and "maxTokens" in inference_config:
        max_tokens = inference_config["maxTokens"]
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS

    # Convert messages from Bedrock format to OpenAI format
    openai_messages = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        # Handle content as list (Bedrock format) or string
        if isinstance(content, list):
            # Extract text from content blocks
            text_parts = [block.get("text", "") for block in content if "text" in block]
            content_str = " ".join(text_parts)
        else:
            content_str = content

        openai_messages.append({"role": role, "content": content_str})

    request_params = {
        "model": model_id,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        **kwargs
    }

    # Convert tools from Bedrock format to OpenAI format if provided
    if tools is not None:
        openai_tools = []
        for tool in tools:
            if "toolSpec" in tool:
                spec = tool["toolSpec"]
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": spec["name"],
                        "description": spec.get("description", ""),
                        "parameters": spec.get("inputSchema", {})
                    }
                })
        if openai_tools:
            request_params["tools"] = openai_tools

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(**request_params)

            # Convert OpenAI response to Bedrock-like format
            choice = response.choices[0]
            message = choice.message

            bedrock_format = {
                "output": {
                    "message": {
                        "role": message.role,
                        "content": [{"text": message.content or ""}]
                    }
                },
                "stopReason": "end_turn" if choice.finish_reason == "stop" else choice.finish_reason,
                "usage": {
                    "inputTokens": response.usage.prompt_tokens,
                    "outputTokens": response.usage.completion_tokens,
                    "totalTokens": response.usage.total_tokens
                }
            }

            # Add tool calls if present
            if message.tool_calls:
                bedrock_format["output"]["message"]["content"] = []
                for tool_call in message.tool_calls:
                    bedrock_format["output"]["message"]["content"].append({
                        "toolUse": {
                            "toolUseId": tool_call.id,
                            "name": tool_call.function.name,
                            "input": tool_call.function.arguments
                        }
                    })

            return bedrock_format

        except RateLimitError as e:
            if attempt < max_retries:
                sleep_time = 2 ** attempt
                time.sleep(sleep_time)
                continue
            else:
                raise


def call_llm(
    messages: list,
    model_id: str,
    region: str = "us-east-1",
    tools: list = None,
    max_retries: int = 3,
    **kwargs
) -> dict:
    """
    Call LLM API with retry logic for throttling.

    Automatically routes to Bedrock or OpenAI based on model_id prefix.

    Args:
        messages: List of message dicts with role and content
        model_id: Model identifier. Examples:
            - Bedrock: "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
            - OpenAI: "gpt-4o", "gpt-4-turbo", "o1-preview"
        region: AWS region name (default: "us-east-1", only used for Bedrock)
        tools: Optional list of tool specifications for tool use
        max_retries: Maximum number of retries on throttling (default: 3)
        **kwargs: Additional parameters to pass to the API.
            For Bedrock: Pass `inferenceConfig={"maxTokens": N}` to override default
            For OpenAI: Pass `max_tokens=N` or `inferenceConfig={"maxTokens": N}`

    Returns:
        Response dict in Bedrock converse API format

    Raises:
        ClientError/OpenAI error: If max retries are exhausted or a non-throttling error occurs
        ImportError: If OpenAI package is not installed for OpenAI models
        ValueError: If OPENAI_API_KEY is not set for OpenAI models
    """
    if _is_openai_model(model_id):
        return _call_openai_llm(messages, model_id, tools, max_retries, **kwargs)
    else:
        return _call_bedrock_llm(messages, model_id, region, tools, max_retries, **kwargs)
