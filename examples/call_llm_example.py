"""
Example showing how to use call_llm with both Bedrock and OpenAI models.
"""
from hackathon_science.utils import call_llm

def bedrock_example():
    """Example using AWS Bedrock Claude model."""
    messages = [
        {
            "role": "user",
            "content": [{"text": "What is the capital of France?"}]
        }
    ]

    # Using Bedrock with Claude
    response = call_llm(
        messages=messages,
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region="us-east-1"
    )

    # Extract response text
    output = response.get("output", {}).get("message", {}).get("content", [])
    text = output[0].get("text", "") if output else ""
    print(f"Bedrock response: {text}")
    return text


def openai_example():
    """Example using OpenAI GPT model."""
    # Note: Requires OPENAI_API_KEY environment variable
    messages = [
        {
            "role": "user",
            "content": [{"text": "What is the capital of France?"}]
        }
    ]

    # Using OpenAI GPT
    response = call_llm(
        messages=messages,
        model_id="gpt-4o"
    )

    # Extract response text (same format as Bedrock)
    output = response.get("output", {}).get("message", {}).get("content", [])
    text = output[0].get("text", "") if output else ""
    print(f"OpenAI response: {text}")
    return text


def with_tools_example():
    """Example using tools with either provider."""
    messages = [
        {
            "role": "user",
            "content": [{"text": "What's the weather in Paris?"}]
        }
    ]

    # Define a tool
    tools = [
        {
            "toolSpec": {
                "name": "get_weather",
                "description": "Get current weather for a city",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ]

    # Works with both Bedrock and OpenAI
    response = call_llm(
        messages=messages,
        model_id="gpt-4o",  # or use a Bedrock model
        tools=tools
    )

    print(f"Response with tools: {response}")
    return response


if __name__ == "__main__":
    print("=== Bedrock Example ===")
    try:
        bedrock_example()
    except Exception as e:
        print(f"Bedrock example failed: {e}")

    print("\n=== OpenAI Example ===")
    try:
        openai_example()
    except Exception as e:
        print(f"OpenAI example failed (requires OPENAI_API_KEY): {e}")

    print("\n=== Tools Example ===")
    try:
        with_tools_example()
    except Exception as e:
        print(f"Tools example failed: {e}")
