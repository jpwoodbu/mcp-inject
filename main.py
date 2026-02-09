import datetime

import openai


def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    client = openai.OpenAI(
        api_key="unused", base_url="http://192.168.86.14:8000/v3"
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "What time is it right now?"},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current time",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    # 1. First call: Check if the model wants to use a tool (stream=False for simplicity)
    response = client.chat.completions.create(
        model="qwen3",
        messages=messages,  # type: ignore
        tools=tools,  # type: ignore
        stream=False,
    )  # type: ignore

    response_msg = response.choices[0].message

    # 2. If tool called, execute it and append result to history
    if response_msg.tool_calls:
        messages.append(response_msg)
        for tool_call in response_msg.tool_calls:
            if tool_call.function.name == "get_current_time":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": get_current_time(),
                    }
                )

    # 3. Final call: Get the answer using the tool result
    stream = client.chat.completions.create(
        model="qwen3",
        messages=messages,  # type: ignore
        stream=True,
    )  # type: ignore

    for chunk in stream:
        delta = chunk.choices[0].delta
        if getattr(delta, "reasoning_content", None):
            print(
                f"\033[94m{delta.reasoning_content}\033[0m", end="", flush=True  # type: ignore
            )
        if delta.content is not None:
            print(delta.content, end="", flush=True)
    print()  # Add a newline at the end for a cleaner prompt.


if __name__ == "__main__":
    main()
