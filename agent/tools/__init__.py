"""
Agent 工具模块

提供 ReadFile、SearchCode、RunCommand、RetrieveAndSummarize 四个工具供 Agent 调用。
"""
from utils.config import Config

from .read_file import ReadFile
from .search_code import SearchCode
from .run_command import RunCommand
from .retrieve_and_summarize import RetrieveAndSummarize, initialize_tool_service_manager
from .mcp_common import initialize_mcp_tool_service_manager
from .mcp_read_file import MCPReadFile
from .mcp_search_code import MCPSearchCode
from .mcp_run_command import MCPRunCommand


def get_agent_toolset():
    if Config.get("mcp.enabled", True):
        return MCPReadFile, MCPSearchCode, MCPRunCommand, RetrieveAndSummarize
    return ReadFile, SearchCode, RunCommand, RetrieveAndSummarize


__all__ = [
    "ReadFile",
    "SearchCode",
    "RunCommand",
    "MCPReadFile",
    "MCPSearchCode",
    "MCPRunCommand",
    "RetrieveAndSummarize",
    "initialize_tool_service_manager",
    "initialize_mcp_tool_service_manager",
    "get_agent_toolset",
]
