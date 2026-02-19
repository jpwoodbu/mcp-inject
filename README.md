# MCP Inject

An OpenAI API proxy server that injects tools into the context using MCP.

The use case this was made for was to add web search to Home Assistant's Voice
Assistant. Normally when Model Context Protocol is used, the client is
responsible for all of these:
* Telling the LLM what tools are available
* Running the tools on behalf on the LLM
* Including the results from running those tools in the context

The purpose of this tool is to do all of the above so the client doesn't have
to. This is especially useful in cases where the client doesn't have MCP
features (e.g. many Home Assistant LLM integrations).

## Configuration

Set the `MCP_INJECT_BACKEND_URL` environment variable to the base URL of your
model server. For example, `http://127.0.0.1:8000/v1`. URL paths like
`/chat/completions` will be suffixed to the provided URL.

## Starting the proxy server
If you have `uv` installed, you can start the server like so:
```sh
cd mcp-inject
uv sync
uv run fastapi run app/main.py
```

Without `uv`, you can start the server like so:
```sh
cd mcp-inject
python3 -m venv .venv
source .venv/bin/activate
pip install .
fastapi run app/main.py
```

Since the proxy server is a [FastAPI](https://fastapi.tiangolo.com/) server, you can pass FastAPI flags, like `port` to bind to a specific port:
```sh
fastapi run app/main.py --port 8001
```

## Example setup

1. Set up an OpenAI compatible model server.
1. Run _MCP Inject_ and point it at the
model server.
1. Run an OpenAI API client, for example, the
[Local LLMs](https://github.com/acon96/home-llm) Home Assistant integration.
Configure it to talk to _MCP Inject_.

Now that Home Assistant integration will be able to respond to prompts with the
help of web search.

## Currently included tools

* [duckduckgo-mcp](https://github.com/CyranoB/duckduckgo-mcp) - Web search through DuckDuckGo. This search backend was chosen for simplicity as it doesn't require an API key. This MCP search also provides a tool to fetch the content of a URL.
* **Getting the current date and time** - This is handy, but it's really here because it was the simplest tool to integrate during initial development. 