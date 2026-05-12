"""
MCP host-side integration.

`CodeMindAgent` is the MCP host. This module provides the MCP client used by
that host to discover and call MCP server tools.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
from concurrent.futures import Future
from dataclasses import dataclass
from threading import Thread
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

from utils.config import Config
from utils.logger import get_logger

logger = get_logger("agent.mcp_host")


class MCPHostError(RuntimeError):
    """Raised when host-side MCP integration fails."""


class _AsyncioLoopThread:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run, daemon=True, name="codemind-mcp-host")
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()


@dataclass
class _WorkerRequest:
    action: str
    payload: Any
    future: Future


class MCPClient:
    """Reusable MCP client used by the agent host to talk to an MCP server."""

    def __init__(
        self,
        *,
        transport: str | None = None,
        server_command: list[str] | None = None,
        call_timeout: float | None = None,
        startup_timeout: float | None = None,
    ) -> None:
        self.transport = Config.get("mcp.transport", "stdio") if transport is None else transport
        self.server_command = server_command or Config.get("mcp.server_command", self._default_server_command())
        self.server_env = Config.get("mcp.server_env", {})
        self.call_timeout = float(Config.get("mcp.call_timeout", 10) if call_timeout is None else call_timeout)
        self.startup_timeout = float(
            Config.get("mcp.startup_timeout", 15) if startup_timeout is None else startup_timeout
        )

        self._loop_thread: _AsyncioLoopThread | None = None
        self._initialized = False
        self._request_queue = None
        self._startup_future: Future | None = None
        self._worker_future: Future | None = None

    @staticmethod
    def _default_server_command() -> list[str]:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        server_path = os.path.join(project_root, "codemind_mcp", "server.py")
        return ["conda", "run", "--no-capture-output", "-n", "AIP312", "python", server_path]

    def initialize(self) -> None:
        if self._initialized:
            return

        if self.transport.lower() == "local":
            self._initialized = True
            logger.info("MCP client initialized with local transport")
            return

        self._loop_thread = _AsyncioLoopThread()
        try:
            self._startup_future = Future()
            self._worker_future = asyncio.run_coroutine_threadsafe(
                self._worker(self._startup_future),
                self._loop_thread._loop,
            )
            self._startup_future.result(timeout=self.startup_timeout)
            self._initialized = True
        except Exception:
            if self._loop_thread is not None:
                self._loop_thread.stop()
                self._loop_thread = None
            raise

    async def _worker(self, startup_future: Future) -> None:
        try:
            from mcp import ClientSession, types
            from mcp.client.stdio import StdioServerParameters, stdio_client
        except Exception as exc:
            startup_future.set_exception(MCPHostError(f"Failed to import external MCP client SDK: {exc}"))
            return

        params_kwargs = {"command": self.server_command[0], "args": self.server_command[1:]}
        if self.server_env:
            params_kwargs["env"] = {str(k): str(v) for k, v in self.server_env.items()}
        params = StdioServerParameters(**params_kwargs)
        self._request_queue = asyncio.Queue()

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=dt.timedelta(seconds=self.call_timeout),
            ) as session:
                await asyncio.wait_for(session.initialize(), timeout=self.startup_timeout)
                logger.info("MCP client initialized")
                startup_future.set_result(True)

                while True:
                    request = await self._request_queue.get()
                    if request.action == "stop":
                        request.future.set_result(True)
                        return
                    try:
                        if request.action == "list_tools":
                            req = types.ListToolsRequest()
                            params = getattr(req, "params", None)
                            cursor = getattr(params, "cursor", None) if params is not None else None
                            result = await asyncio.wait_for(
                                session.list_tools(cursor=cursor, params=params),
                                timeout=self.call_timeout,
                            )
                            request.future.set_result([self._tool_to_dict(tool) for tool in result.tools])
                        elif request.action == "call_tool":
                            name, arguments = request.payload
                            result = await session.call_tool(
                                name,
                                arguments,
                                read_timeout_seconds=dt.timedelta(seconds=self.call_timeout),
                            )
                            request.future.set_result(self._flatten_content(result.content))
                        else:
                            request.future.set_exception(MCPHostError(f"Unknown worker action: {request.action}"))
                    except Exception as exc:
                        request.future.set_exception(exc)

    def close(self) -> None:
        if self.transport.lower() == "local":
            self._initialized = False
            return
        if self._loop_thread is None:
            self._initialized = False
            return
        try:
            self._submit_worker_request("stop", None)
            if self._worker_future is not None:
                self._worker_future.result(timeout=5)
        finally:
            self._loop_thread.stop()
            self._loop_thread = None
            self._initialized = False
            self._request_queue = None
            self._startup_future = None
            self._worker_future = None

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure_available()
        if self.transport.lower() == "local":
            return asyncio.run(self._async_list_tools())
        return self._submit_worker_request("list_tools", None)

    async def _async_list_tools(self) -> list[dict[str, Any]]:
        if self.transport.lower() != "local":
            raise MCPHostError("_async_list_tools should not be used for stdio transport")
        from codemind_mcp.server import list_registered_tools

        return [self._tool_to_dict(tool) for tool in await list_registered_tools()]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        self._ensure_available()
        if self.transport.lower() == "local":
            return asyncio.run(self._async_call_tool(name, arguments or {}))
        return self._submit_worker_request("call_tool", (name, arguments or {}))

    async def _async_call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if self.transport.lower() != "local":
            raise MCPHostError("_async_call_tool should not be used for stdio transport")
        from codemind_mcp.server import call_registered_tool

        return await asyncio.wait_for(call_registered_tool(name, arguments), timeout=self.call_timeout)

    def health_check(self) -> bool:
        try:
            return bool(self.list_tools())
        except Exception as exc:
            logger.warning(f"MCP client health check failed: {exc}")
            return False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _ensure_available(self) -> None:
        if not self._initialized:
            raise MCPHostError("MCP client is not initialized")

    def _submit_worker_request(self, action: str, payload: Any) -> Any:
        if self._loop_thread is None or self._request_queue is None:
            raise MCPHostError("MCP client worker is not running")
        result_future: Future = Future()
        request = _WorkerRequest(action=action, payload=payload, future=result_future)
        enqueue = self._request_queue.put(request)
        asyncio.run_coroutine_threadsafe(enqueue, self._loop_thread._loop).result(timeout=self.call_timeout)
        return result_future.result(timeout=self.call_timeout + 1)

    @staticmethod
    def _flatten_content(content: Any) -> str:
        parts: list[str] = []
        for item in content or []:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _tool_to_dict(tool: Any) -> dict[str, Any]:
        return {
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", ""),
            "inputSchema": getattr(tool, "inputSchema", {}),
        }


def _json_schema_to_python_type(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type", "string")
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list
    if schema_type == "object":
        return dict
    return str


MCPHostClient = MCPClient
"""Backward-compatible alias for older host-side naming."""


def build_langchain_mcp_tools(mcp_client: MCPClient) -> list[StructuredTool]:
    """Fetch MCP tools and adapt them into LangChain tools."""

    tools = []
    for tool_def in mcp_client.list_tools():
        schema = tool_def.get("inputSchema", {})
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        fields = {}
        for field_name, field_schema in properties.items():
            python_type = _json_schema_to_python_type(field_schema)
            default = ... if field_name in required else field_schema.get("default", None)
            fields[field_name] = (python_type, default)

        args_model = create_model(f"MCPToolInput_{tool_def['name']}", **fields)

        def _invoke_factory(tool_name: str):
            def _invoke(**kwargs):
                return mcp_client.call_tool(tool_name, kwargs)

            return _invoke

        tools.append(
            StructuredTool.from_function(
                func=_invoke_factory(tool_def["name"]),
                name=tool_def["name"],
                description=tool_def.get("description", tool_def["name"]),
                args_schema=args_model,
            )
        )

    return tools
