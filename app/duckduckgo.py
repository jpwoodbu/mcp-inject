"""Interface to the DuckDuckGo MCP server"""

import contextlib

import mcp
from mcp.client import stdio as mcp_stdio


_SERVER_COMMAND = "duckduckgo-mcp-server"
_SERVER_ARGS = []


class DuckDuckGo:

    def __init__(self):
        self.server_params = mcp.StdioServerParameters(
            command=_SERVER_COMMAND, args=_SERVER_ARGS, env=None
        )
        self._exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self):
        read, write = await self._exit_stack.enter_async_context(
            mcp_stdio.stdio_client(self.server_params)
        )
        self.session = await self._exit_stack.enter_async_context(
            mcp.ClientSession(read, write)
        )
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._exit_stack.aclose()

    async def list_tools(self) -> mcp.types.ListToolsResult:
        return await self.session.list_tools()

    async def search(self, query: str):
        return await self.session.call_tool(
            "search", arguments={"query": query}
        )

    async def fetch_content(self, url: str):
        return await self.session.call_tool(
            "fetch_content", arguments={"url": url}
        )
