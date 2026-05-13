"""CodeMind MCP 服务器入口点。"""

from __future__ import annotations

import asyncio
import os
import sys

# 如果作为脚本直接运行，确保项目根目录在 sys.path 中
if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent

from codemind_mcp.tools.index_manager import AddByFilePathTool, DeleteByFilePathTool, IndexRepoTool
from codemind_mcp.tools.output_truncation import truncate_tool_output
from codemind_mcp.tools.read_file import ReadFileTool
from codemind_mcp.tools.run_command import RunCommandTool
from codemind_mcp.tools.search_code import SearchCodeTool
from utils.config import Config
from utils.logger import get_logger

# 默认将日志输出到 stderr
os.environ.setdefault("CODEMIND_LOG_STDERR", "1")

logger = get_logger("mcp.server")
app = Server("codemind-mcp-server")
_TOOLS = None


def get_tools():
    """返回懒初始化的 CodeMind MCP 工具列表。"""
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
    """返回 MCP 工具定义列表。"""
    return [tool.get_definition() for tool in get_tools()]


async def call_registered_tool(name: str, arguments: dict | None = None) -> str:
    """根据 MCP 工具名称分发工具调用。"""
    for tool in get_tools():
        if tool.name == name:
            return await tool.call(arguments or {})

    raise ValueError(f"未知工具: {name}")


def _get_truncation_tool_name(name: str) -> str:
    """将 MCP 工具名称转换为用于截断消息的显示名称。"""
    if name.startswith("codemind_"):
        name = name[9:]
    return "".join(part.capitalize() for part in name.split("_") if part)


@app.list_tools()
async def list_tools():
    """列出所有可用的 MCP 工具。"""
    return await list_registered_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """处理 MCP 工具调用请求。"""
    result = await call_registered_tool(name, arguments)
    # 对工具输出进行截断处理，防止输出过大
    result = truncate_tool_output(result, _get_truncation_tool_name(name))
    return CallToolResult(content=[TextContent(type="text", text=result)])


async def main():
    """主函数：启动 CodeMind MCP 服务器。"""
    Config.load()
    logger.info("CodeMind MCP 服务器正在启动...")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
