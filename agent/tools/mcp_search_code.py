"""
Agent-side MCP proxy for SearchCode.
"""

from __future__ import annotations

from langchain_core.tools import tool

from agent.tools.mcp_common import get_mcp_client, should_fallback_to_local
from agent.tools.search_code import SearchCode as LocalSearchCode
from utils.logger import get_logger

logger = get_logger("agent.tools.mcp_search_code")


@tool
def MCPSearchCode(query: str, is_regex: bool = False, search_dir: str = ".") -> str:
    """在代码库中搜索关键词或正则表达式，优先通过 MCP 服务执行。"""
    payload = {
        "query": query,
        "is_regex": is_regex,
        "search_dir": search_dir,
    }
    try:
        client = get_mcp_client()
        if client is None:
            raise RuntimeError("MCP client unavailable")
        return client.call_tool("codemind_search_code", payload)
    except Exception as exc:
        logger.warning(f"MCPSearchCode failed, fallback={should_fallback_to_local()}: {exc}")
        if should_fallback_to_local():
            return LocalSearchCode.invoke(payload)
        return f"[错误] MCP SearchCode 调用失败: {exc}"
