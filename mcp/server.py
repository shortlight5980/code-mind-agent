"""
CodeMind MCP server entrypoint.
"""

from __future__ import annotations

import asyncio

from mcp.sdk import LocalServerShim, load_sdk_modules, local_stdio_server
from mcp.tools.index_manager import AddByFilePathTool, DeleteByFilePathTool, IndexRepoTool
from mcp.tools.read_file import ReadFileTool
from mcp.tools.run_command import RunCommandTool
from mcp.tools.search_code import SearchCodeTool
from utils.config import Config
from utils.logger import get_logger

logger = get_logger("mcp.server")

ServerType, stdio_server, _ = load_sdk_modules()
app = (ServerType or LocalServerShim)("codemind-mcp-server")
_TOOLS = None


def get_tools():
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = [
            ReadFileTool(),
            SearchCodeTool(),
            RunCommandTool(),
            IndexRepoTool(),
            AddByFilePathTool(),
            DeleteByFilePathTool(),
        ]
    return _TOOLS


async def list_registered_tools():
    return [tool.get_definition() for tool in get_tools()]


async def call_registered_tool(name: str, arguments: dict | None = None) -> str:
    for tool in get_tools():
        if tool.name == name:
            return await tool.call(arguments or {})
    raise ValueError(f"Unknown tool: {name}")


@app.list_tools()
async def list_tools():
    return await list_registered_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    return await call_registered_tool(name, arguments)


async def main():
    Config.load()
    logger.info("CodeMind MCP Server starting...")

    transport = stdio_server or local_stdio_server
    async with transport() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

