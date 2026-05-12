"""
Helpers for interacting with the third-party MCP SDK without colliding with the
local ``mcp`` package name used by this repository.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import Any


@dataclass
class ToolDefinition:
    """Minimal tool definition compatible with the MCP Tool shape."""

    name: str
    description: str
    inputSchema: dict[str, Any]


def _search_paths_without_project() -> list[str]:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filtered: list[str] = []
    for path in sys.path:
        normalized = os.path.abspath(path or os.getcwd())
        if normalized != project_root:
            filtered.append(path)
    return filtered


def _load_sdk_root_module() -> ModuleType | None:
    search_paths = _search_paths_without_project()
    spec = importlib.machinery.PathFinder.find_spec("mcp", search_paths)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_codemind_external_mcp", module)
    spec.loader.exec_module(module)
    return module


def load_sdk_modules() -> tuple[Any, Any, Any] | tuple[None, None, None]:
    """
    Load ``Server``, ``stdio_server`` and ``Tool`` from the external MCP SDK.

    Returns ``(None, None, None)`` when the SDK is unavailable.
    """
    root = _load_sdk_root_module()
    if root is None:
        return None, None, None

    try:
        server_module = importlib.import_module("mcp.server")
        stdio_module = importlib.import_module("mcp.server.stdio")
        types_module = importlib.import_module("mcp.types")
    except Exception:
        return None, None, None

    return (
        getattr(server_module, "Server", None),
        getattr(stdio_module, "stdio_server", None),
        getattr(types_module, "Tool", None),
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

