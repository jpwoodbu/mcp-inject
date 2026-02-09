import openai


def main():
    client = openai.OpenAI(
        api_key="unused", base_url="http://192.168.86.14:8000/v3"
    )
    stream = client.chat.completions.create(
        model="qwen3",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {
                "role": "user",
                "content": "How do I check if a Python object is an instances of a class?",
            },
        ],
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if getattr(delta, "reasoning_content", None):
            print(
                f"\033[94m{delta.reasoning_content}\033[0m", end="", flush=True  # type: ignore
            )
        if delta.content is not None:
            print(delta.content, end="", flush=True)


if __name__ == "__main__":
    main()
