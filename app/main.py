from collections.abc import AsyncGenerator
import datetime
import json
import logging
import os

import fastapi
import httpx

from app import current_time
from app import duckduckgo
from app import util


_BACKEND_URL: str = os.environ.get("MCP_INJECT_BACKEND_URL", "")
_COMPLETIONS_URL: str = _BACKEND_URL + "/chat/completions"


logger = logging.getLogger(__name__)
app = fastapi.FastAPI()


@app.get("/")
def usage():
    return fastapi.responses.HTMLResponse(
        content="<p>Set your OpenAI API client to use <b>/v1/chat/completions</b></p>"
    )


@app.post("/v1/chat/completions")
async def chat_completions(
    request: fastapi.Request, background_tasks: fastapi.BackgroundTasks
):
    """Proxies requests to the backend LLM, injecting tools."""
    if not _BACKEND_URL:
        raise ValueError("env var MCP_INJECT_BACKEND_URL must be set")

    body = await request.json()
    await _inject_tools(body)

    client = httpx.AsyncClient()
    headers = util.filter_headers(request.headers)
    # This task will be called after the response has been sent to the client.
    background_tasks.add_task(client.aclose)
    proxy_request = client.build_request(
        "POST", _COMPLETIONS_URL, json=body, headers=headers
    )
    response = await client.send(proxy_request, stream=True)
    return fastapi.responses.StreamingResponse(
        _chat_completions_response_stream(client, response, body, headers),
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


# This catch all handler MUST be defined after more specific handlers.
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def proxy_catch_all(request: fastapi.Request, path: str):
    if not _BACKEND_URL:
        raise ValueError("env var MCP_INJECT_BACKEND_URL must be set")

    headers = util.filter_headers(request.headers)

    async with httpx.AsyncClient() as client:
        content = await request.body()
        proxy_request = client.build_request(
            request.method,
            f"{_BACKEND_URL}/{path}",
            headers=headers,
            content=content,
            params=request.query_params,
        )
        response = await client.send(proxy_request)

    return fastapi.responses.Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


async def _inject_tools(body: dict):
    """Make the LLM aware of the tools we can run."""
    util.inject_function_tool(body, "get_current_time", "Get the current time")

    async with duckduckgo.DuckDuckGo() as ddg:
        tools = await ddg.list_tools()
        for t in tools.tools:
            util.inject_function_tool(
                body, t.name, t.description, t.inputSchema
            )


async def _chat_completions_response_stream(
    client, response, body, headers
) -> AsyncGenerator[str, None]:
    requested_tool_calls = {}
    content = ""

    async for line in response.aiter_lines():
        # With the streaming OpenAI API, each chunk should have a "data" prefix.
        # If we get something we don't expect, yield it and let the client deal
        # with it.
        if not line.startswith("data: "):
            yield line + "\n"
        else:
            payload = line[6:].strip()
            # Don't pass along a `[DONE]` message just yet as we may need to
            # process a tool call request and include the LLM's tool call
            # informed response in this stream.
            if payload == "[DONE]":
                continue

            try:
                chunk = json.loads(payload)
            # If we don't get back valid JSON, yield what we got unmodified for
            # the client to deal with it.
            except json.JSONDecodeError:
                yield line + "\n"

            delta = chunk["choices"][0].get("delta", {})
            finish_reason = chunk["choices"][0].get("finish_reason")

            if delta.get("content"):
                content += delta["content"]

            if delta.get("tool_calls"):
                _record_tool_call_requests(
                    requested_tool_calls, delta["tool_calls"]
                )

            # Suppress tool calls and the stop reason associated with them which
            # the client shouldn't see since it didn't offer the tool calls.
            if delta.get("tool_calls") or finish_reason == "tool_calls":
                continue

            # If this chunk wasn't about tool calls, pass it along.
            yield line + "\n"

    await response.aclose()

    if requested_tool_calls:
        await _handle_tool_execution(body, requested_tool_calls, content)

        # Send the result from tool calling to the LLM and get its tool informed
        # response for the original prompt.
        tool_call_result_request = client.build_request(
            "POST", _COMPLETIONS_URL, json=body, headers=headers
        )
        informed_response = await client.send(
            tool_call_result_request, stream=True
        )
        # Stream the entire informed repsonse, which would include a `[DONE]`
        # message.
        async for line in informed_response.aiter_lines():
            yield line + "\n"
        await informed_response.aclose()
    # In the event there was no tool calling, indicate the stream is done.
    else:
        yield "data: [DONE]\n\n"


def _record_tool_call_requests(requested_tool_calls: dict, delta: list[dict]):
    """Updates the proxy's internal tool calls state.

    If the LLM decides to make a tool call, it will send that request along with
    an ID string which is included in the next request to the LLM along with the
    content generated by the tool.

    Note that this function uses the streaming protocol and accepts message
    deltas, not necessarily complete messages.
    """
    for tool_call in delta:
        # The `index` seems redunant with the `id`, but it's used as part of the
        # streaming API. It's used for demultiplexing.
        idx = tool_call["index"]
        if idx not in requested_tool_calls:
            requested_tool_calls[idx] = {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }
        requested_tool_call = requested_tool_calls[idx]
        if id := tool_call.get("id"):
            # id is not streamed, the = operator is safe.
            requested_tool_call["id"] = id
        if function := tool_call.get("function"):
            if name := function.get("name"):
                requested_tool_call["function"]["name"] += name
            if arguments := function.get("arguments"):
                requested_tool_call["function"]["arguments"] += arguments


async def _handle_tool_execution(body: dict, tool_calls: dict, content: str):
    if "messages" not in body:
        body["messages"] = []

    assistant_msg = {
        "role": "assistant",
        "content": content if content else None,
        "tool_calls": list(tool_calls.values()),
    }
    body["messages"].append(assistant_msg)

    for tool_call in tool_calls.values():
        result = None
        if id := tool_call.get("id"):
            match tool_call["function"]["name"]:
                case "get_current_time":
                    result = current_time.current_time(id)
                case "search":
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                        result = await duckduckgo.search(id, args["query"])
                    except (json.JSONDecodeError, KeyError) as e:
                        result = util.tool_call_result(
                            id, f"Error processing tool arguments: {e}"
                        )
                case "fetch_content":
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                        result = await duckduckgo.fetch_content(
                            id, args["url"]
                        )
                    except (json.JSONDecodeError, KeyError) as e:
                        result = util.tool_call_result(
                            id, f"Error processing tool arguments: {e}"
                        )
        else:
            logger.error(f"Tool call missing required 'id' field: {tool_call}")

        if result:
            body["messages"].append(result)
