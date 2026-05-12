"""
Agent-side MCP proxy for ReadFile.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from agent.tools.mcp_common import get_mcp_client, should_fallback_to_local
from agent.tools.read_file import ReadFile as LocalReadFile
from utils.logger import get_logger

logger = get_logger("agent.tools.mcp_read_file")


@tool
def MCPReadFile(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """读取指定文件的内容，优先通过 MCP 服务执行。"""
    payload = {"file_path": file_path}
    if start_line is not None:
        payload["start_line"] = start_line
    if end_line is not None:
        payload["end_line"] = end_line

    try:
        client = get_mcp_client()
        if client is None:
            raise RuntimeError("MCP client unavailable")
        return client.call_tool("codemind_read_file", payload)
    except Exception as exc:
        logger.warning(f"MCPReadFile failed, fallback={should_fallback_to_local()}: {exc}")
        if should_fallback_to_local():
            return LocalReadFile.invoke(payload)
        return f"[错误] MCP ReadFile 调用失败: {exc}"
