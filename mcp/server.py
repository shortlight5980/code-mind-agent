"""
CodeMind MCP server entrypoint.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import sys

if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    local_package_root = os.path.dirname(os.path.abspath(__file__))
    local_alias = "codemind_local_mcp"
    if local_alias not in sys.modules:
        alias_spec = importlib.util.spec_from_file_location(
            local_alias,
            os.path.join(local_package_root, "__init__.py"),
            submodule_search_locations=[local_package_root],
        )
        if alias_spec is None or alias_spec.loader is None:
            raise RuntimeError("Failed to bootstrap local MCP package")
        alias_module = importlib.util.module_from_spec(alias_spec)
        sys.modules[local_alias] = alias_module
        alias_spec.loader.exec_module(alias_module)

    sdk_module = importlib.import_module(f"{local_alias}.sdk")
    LocalServerShim = sdk_module.LocalServerShim
    load_sdk_modules = sdk_module.load_sdk_modules
    local_stdio_server = sdk_module.local_stdio_server
    ServerType, stdio_server, _ = load_sdk_modules()

    tools_module = importlib.import_module(f"{local_alias}.tools")
    index_module = importlib.import_module(f"{local_alias}.tools.index_manager")
    ReadFileTool = tools_module.ReadFileTool
    RunCommandTool = tools_module.RunCommandTool
    SearchCodeTool = tools_module.SearchCodeTool
    AddByFilePathTool = index_module.AddByFilePathTool
    DeleteByFilePathTool = index_module.DeleteByFilePathTool
    IndexRepoTool = index_module.IndexRepoTool
else:
    from .sdk import LocalServerShim, load_sdk_modules, local_stdio_server
    from .tools.index_manager import AddByFilePathTool, DeleteByFilePathTool, IndexRepoTool
    from .tools.read_file import ReadFileTool
    from .tools.run_command import RunCommandTool
    from .tools.search_code import SearchCodeTool

if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from utils.config import Config
from utils.logger import get_logger

logger = get_logger("mcp.server")

if __package__ not in (None, ""):
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
