"""
Agent 工具模块

提供本地 Agent 工具；MCP tools 在 Agent 初始化时动态拉取并合并。
"""
from .retrieve_and_summarize import RetrieveAndSummarize, initialize_tool_service_manager


def get_agent_toolset():
    return (RetrieveAndSummarize,)


__all__ = [
    "RetrieveAndSummarize",
    "initialize_tool_service_manager",
    "get_agent_toolset",
]
