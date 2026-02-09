import datetime

import openai


def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def process_stream(stream):
    content = ""
    tool_calls = {}

    for chunk in stream:
        delta = chunk.choices[0].delta

        if getattr(delta, "reasoning_content", None):
            print(
                f"\033[94m{delta.reasoning_content}\033[0m", end="", flush=True
            )
        if delta.content is not None:
            print(delta.content, end="", flush=True)
            content += delta.content

        if delta.tool_calls:
            for tool_call in delta.tool_calls:
                index = tool_call.index
                if index not in tool_calls:
                    tool_calls[index] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                if tool_call.id:
                    tool_calls[index]["id"] = tool_call.id
                if tool_call.type:
                    tool_calls[index]["type"] = tool_call.type
                if tool_call.function:
                    if tool_call.function.name:
                        tool_calls[index]["function"][
                            "name"
                        ] += tool_call.function.name
                    if tool_call.function.arguments:
                        tool_calls[index]["function"][
                            "arguments"
                        ] += tool_call.function.arguments

    print()  # Add a newline at the end

    message = {
        "role": "assistant",
        "content": content if content else None,
    }
    if tool_calls:
        message["tool_calls"] = [
            tool_calls[i] for i in sorted(tool_calls.keys())
        ]
    return message


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

    # 1. First call: Check if the model wants to use a tool
    stream = client.chat.completions.create(
        model="qwen3",
        messages=messages,  # type: ignore
        tools=tools,  # type: ignore
        stream=True,
    )  # type: ignore

    response_msg = process_stream(stream)

    # 2. If tool called, execute it and append result to history
    if response_msg.get("tool_calls"):
        # We must add the assistant's tool call message to the history
        # so the model knows what triggered the tool output.
        messages.append(response_msg)
        for tool_call in response_msg["tool_calls"]:
            if tool_call["function"]["name"] == "get_current_time":
                tool_result = {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": get_current_time(),
                }
                print(f"Inserted: {tool_result}\n")
                messages.append(tool_result)

        # 3. Final call: Get the answer using the tool result
        stream = client.chat.completions.create(
            model="qwen3",
            messages=messages,  # type: ignore
            stream=True,
        )  # type: ignore
        process_stream(stream)


if __name__ == "__main__":
    main()
