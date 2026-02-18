"""Utility functions which do data transformations"""


def filter_headers(headers) -> dict:
    """Filter out headers which the Proxy may need to change.

    The "Host" header likely always needs to be changed. The "Content-Length"
    header will need to change if tool calling is injected.
    """
    return {
        k: v
        for k, v in headers.items()
        # FastAPI, it seems, might lowercase all the headers.
        if k.lower() not in ("host", "content-length")
    }


def tool_call_result(id: str, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": id,
        "content": content,
    }


def inject_function_tool(
    body: dict,
    name: str,
    description: str | None,
    parameters: dict | None = None,
):
    """Injects a function type tool into the message body."""
    if "tools" not in body:
        body["tools"] = []

    body["tools"].append(
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description or "",
                "parameters": parameters
                or {"type": "object", "properties": {}},
            },
        }
    )
