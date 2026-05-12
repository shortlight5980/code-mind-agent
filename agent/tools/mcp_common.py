"""
Shared helpers for Agent-side MCP proxy tools.
"""

from __future__ import annotations

from typing import Any

from utils.config import Config
from utils.logger import get_logger

logger = get_logger("agent.tools.mcp_common")

_service_manager: Any = None


def initialize_mcp_tool_service_manager(service_manager: Any) -> None:
    global _service_manager
    _service_manager = service_manager


def get_mcp_client():
    if _service_manager is None:
        raise RuntimeError("MCP tool service manager is not initialized")
    return getattr(_service_manager, "mcp_client", None)


def use_mcp_tools() -> bool:
    return bool(Config.get("mcp.enabled", True))


def should_fallback_to_local() -> bool:
    return bool(Config.get("mcp.fallback_to_local", True))
