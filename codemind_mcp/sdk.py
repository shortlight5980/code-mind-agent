"""
Helpers for interacting with the third-party MCP SDK without colliding with the
local ``mcp`` package name used by this repository.
"""

from __future__ import annotations

import importlib
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    """Minimal tool definition compatible with the MCP Tool shape."""

    name: str
    description: str
    inputSchema: dict[str, Any]


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _search_paths_without_project() -> list[str]:
    project_root = _project_root()
    filtered: list[str] = []
    for path in sys.path:
        normalized = os.path.abspath(path or os.getcwd())
        if normalized != project_root:
            filtered.append(path)
    return filtered


def _is_local_package_bound() -> bool:
    current = sys.modules.get("mcp")
    if current is None:
        return False

    module_file = getattr(current, "__file__", None)
    if not module_file:
        return False

    module_file = os.path.abspath(module_file)
    return module_file.startswith(os.path.join(_project_root(), "mcp"))


def _import_external_mcp_module(module_name: str):
    original_sys_path = list(sys.path)
    try:
        sys.path = _search_paths_without_project()
        return importlib.import_module(module_name)
    finally:
        sys.path = original_sys_path


def load_sdk_modules() -> tuple[Any, Any, Any, Any] | tuple[None, None, None, None]:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ = project_root
    if _is_local_package_bound():
        return None, None, None, None

    try:
        server_module = _import_external_mcp_module("mcp.server")
        stdio_module = _import_external_mcp_module("mcp.server.stdio")
        types_module = _import_external_mcp_module("mcp.types")
    except Exception:
        return None, None, None, None

    return (
        getattr(server_module, "Server", None),
        getattr(stdio_module, "stdio_server", None),
        getattr(types_module, "Tool", None),
        types_module,
    )


class LocalServerShim:
    """A small decorator-based registry used for tests and local fallback."""

    def __init__(self, name: str):
        self.name = name
        self._list_tools_handler = None
        self._call_tool_handler = None

    def list_tools(self):
        def decorator(func):
            self._list_tools_handler = func
            return func

        return decorator

    def call_tool(self):
        def decorator(func):
            self._call_tool_handler = func
            return func

        return decorator

    def create_initialization_options(self) -> dict[str, Any]:
        return {"server_name": self.name}

    async def run(self, read_stream, write_stream, init_options):
        raise RuntimeError("MCP SDK is not installed; stdio server cannot start.")


@asynccontextmanager
async def local_stdio_server():
    raise RuntimeError("MCP SDK is not installed; stdio server cannot start.")
    yield None, None
