"""
Agent-side MCP proxy for RunCommand.
"""

from __future__ import annotations

from langchain_core.tools import tool

from agent.tools.mcp_common import get_mcp_client, should_fallback_to_local
from agent.tools.run_command import RunCommand as LocalRunCommand
from utils.logger import get_logger

logger = get_logger("agent.tools.mcp_run_command")


@tool
def MCPRunCommand(command: str) -> str:
    """执行只读 shell 命令，优先通过 MCP 服务执行。"""
    payload = {"command": command}
    try:
        client = get_mcp_client()
        if client is None:
            raise RuntimeError("MCP client unavailable")
        return client.call_tool("codemind_run_command", payload)
    except Exception as exc:
        logger.warning(f"MCPRunCommand failed, fallback={should_fallback_to_local()}: {exc}")
        if should_fallback_to_local():
            return LocalRunCommand.invoke(payload)
        return f"[错误] MCP RunCommand 调用失败: {exc}"
