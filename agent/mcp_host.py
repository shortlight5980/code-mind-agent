"""
MCP 主机端集成。

`CodeMindAgent` 是 MCP 主机。此模块提供由该主机使用的 MCP 客户端，
用于发现并调用 MCP 服务器工具。
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
from concurrent.futures import Future
from dataclasses import dataclass
from threading import Thread
from typing import Any, List

from langchain_core.tools import StructuredTool
from pydantic import create_model, Field

from utils.config import Config
from utils.logger import get_logger

logger = get_logger("agent.mcp_host")


class MCPHostError(RuntimeError):
    """当主机端 MCP 集成失败时抛出此异常。"""


class _AsyncioLoopThread:
    """在独立线程中运行 asyncio 事件循环的辅助类。"""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run, daemon=True, name="codemind-mcp-host")
        self._thread.start()

    def _run(self) -> None:
        """设置并运行当前线程的事件循环。"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self) -> None:
        """停止事件循环并等待线程结束。"""
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()


@dataclass
class _WorkerRequest:
    """封装发送给工作协程的请求。"""
    action: str
    payload: Any
    future: Future


class MCPClient:
    """可重用的 MCP 客户端，供代理主机与 MCP 服务器通信使用。"""

    def __init__(
            self,
            *,
            transport: str | None = None,
            server_command: list[str] | None = None,
            call_timeout: float | None = None,
            startup_timeout: float | None = None,
    ) -> None:
        # 从配置中获取传输方式，默认为 stdio
        self.transport = Config.get("mcp.transport", "stdio") if transport is None else transport
        # 从配置中获取服务器启动命令，若未提供则使用默认命令
        self.server_command = server_command or Config.get("mcp.server_command", self._default_server_command())
        # 从配置中获取服务器环境变量
        self.server_env = Config.get("mcp.server_env", {})
        # 从配置中获取调用超时时间
        self.call_timeout = float(Config.get("mcp.call_timeout", 10) if call_timeout is None else call_timeout)
        # 从配置中获取启动超时时间
        self.startup_timeout = float(
            Config.get("mcp.startup_timeout", 15) if startup_timeout is None else startup_timeout
        )

        self._loop_thread: _AsyncioLoopThread | None = None
        self._initialized = False
        self._request_queue: asyncio.Queue = None
        self._startup_future: Future | None = None
        self._worker_future: Future | None = None

    @staticmethod
    def _default_server_command() -> list[str]:
        """生成默认的 MCP 服务器启动命令。"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        server_path = os.path.join(project_root, "codemind_mcp", "server.py")
        return ["conda", "run", "--no-capture-output", "-n", "AIP312", "python", server_path]

    def initialize(self) -> None:
        """初始化 MCP 客户端。如果是本地传输模式则直接标记为已初始化，
        否则启动异步工作线程并等待其就绪。"""
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
            # 阻塞等待启动成功
            self._startup_future.result(timeout=self.startup_timeout)
            self._initialized = True
        except Exception:
            if self._loop_thread is not None:
                self._loop_thread.stop()
                self._loop_thread = None
            raise

    async def _worker(self, startup_future: Future) -> None:
        """工作协程：负责建立与 MCP 服务器的连接，并处理后续的工具列表查询和工具调用请求。

        该协程在独立的 asyncio 事件循环线程中运行，主要职责包括：
        1. 导入必要的 MCP SDK 模块，若失败则通知启动线程。
        2. 配置并建立与 MCP 服务器的 stdio 通信通道。
        3. 初始化会话并通知主线程启动成功。
        4. 进入无限循环，从内部队列获取请求并执行相应操作（列出工具或调用工具）。
        5. 处理异常并将结果或错误返回给发起请求的未来对象。

        Args:
            startup_future: 用于向初始化线程信号通知启动状态（成功或失败）的 Future 对象。
        """
        # 步骤 1: 动态导入外部 MCP 客户端 SDK
        # 使用 try-except 捕获导入错误，防止因缺少依赖导致整个进程崩溃，
        # 并通过 startup_future 将异常传播回主线程以便正确处理。
        try:
            from mcp import ClientSession, types
            from mcp.client.stdio import StdioServerParameters, stdio_client
        except Exception as exc:
            # 设置启动失败异常，告知调用者 SDK 导入出错
            startup_future.set_exception(MCPHostError(f"Failed to import external MCP client SDK: {exc}"))
            return

        # 步骤 2: 构建服务器启动参数
        # 从配置好的 server_command 中提取命令和参数。
        # server_command[0] 是可执行文件（如 conda），其余部分是参数。
        params_kwargs = {"command": self.server_command[0], "args": self.server_command[1:]}

        # 如果配置了环境变量，将其转换为字符串键值对并加入参数中
        if self.server_env:
            params_kwargs["env"] = {str(k): str(v) for k, v in self.server_env.items()}

        # 创建 StdioServerParameters 对象，用于后续建立 stdio 连接
        params = StdioServerParameters(**params_kwargs)

        # 初始化异步请求队列，用于在主线程和工作协程之间传递任务
        self._request_queue = asyncio.Queue()

        # 步骤 3: 建立与 MCP 服务器的通信连接
        # 使用 stdio_client 上下文管理器启动子进程并建立读写流
        async with stdio_client(params) as (read_stream, write_stream):
            # 创建 MCP 客户端会话，设置读取超时时间
            async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=dt.timedelta(seconds=self.call_timeout),
            ) as session:
                # 步骤 4: 初始化会话
                # 等待服务器完成初始化握手，设置总超时时间以防挂起
                await asyncio.wait_for(session.initialize(), timeout=self.startup_timeout)

                # 记录日志并通知主线程初始化成功
                logger.info("MCP client initialized")
                startup_future.set_result(True)

                # 步骤 5: 主工作循环
                # 持续从队列中获取请求并处理，直到收到停止信号
                while True:
                    # 阻塞等待下一个请求对象
                    request = await self._request_queue.get()

                    # 检查是否为停止信号
                    if request.action == "stop":
                        # 设置停止未来对象的结果为 True，表示正常退出
                        request.future.set_result(True)
                        # 退出循环，结束协程
                        return

                    # 尝试处理具体的业务请求
                    try:
                        if request.action == "list_tools":
                            # 处理“列出工具”请求
                            # 创建 ListToolsRequest 对象以符合 MCP 协议规范
                            req = types.ListToolsRequest()
                            # 安全地提取分页游标参数（如果存在）
                            params = getattr(req, "params", None)
                            cursor = getattr(params, "cursor", None) if params is not None else None

                            # 调用会话的 list_tools 方法，并设置超时保护
                            result = await asyncio.wait_for(
                                session.list_tools(cursor=cursor, params=params),
                                timeout=self.call_timeout,
                            )
                            # 将返回的工具对象转换为字典格式，并设置到未来对象中返回给调用者
                            request.future.set_result([self._tool_to_dict(tool) for tool in result.tools])

                        elif request.action == "call_tool":
                            # 处理“调用工具”请求
                            # 从 payload 中解包工具名称和参数字典
                            name, arguments = request.payload

                            # 调用会话的 call_tool 方法执行远程工具
                            # 注意：此处直接传入 read_timeout_seconds 以控制单次调用的最大等待时间
                            result = await session.call_tool(
                                name,
                                arguments,
                                read_timeout_seconds=dt.timedelta(seconds=self.call_timeout),
                            )
                            # 将响应内容展平为字符串，并设置到未来对象中返回给调用者
                            request.future.set_result(self._flatten_content(result.content))

                        else:
                            # 处理未知动作类型
                            # 设置异常以通知调用者发生了不支持的操作
                            request.future.set_exception(MCPHostError(f"Unknown worker action: {request.action}"))

                    except Exception as exc:
                        # 捕获所有其他异常（如网络错误、超时、序列化错误等）
                        # 将异常设置到未来对象中，以便主线程能捕获并处理
                        request.future.set_exception(exc)

    def close(self) -> None:
        """关闭 MCP 客户端，停止工作线程并清理资源。"""
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
        """获取 MCP 服务器提供的工具列表。"""
        self._ensure_available()
        if self.transport.lower() == "local":
            return asyncio.run(self._async_list_tools())
        return self._submit_worker_request("list_tools", None)

    async def _async_list_tools(self) -> list[dict[str, Any]]:
        """异步获取本地模式下的工具列表。"""
        if self.transport.lower() != "local":
            raise MCPHostError("_async_list_tools should not be used for stdio transport")
        from codemind_mcp.server import list_registered_tools

        return [self._tool_to_dict(tool) for tool in await list_registered_tools()]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """调用指定的 MCP 工具。"""
        self._ensure_available()
        if self.transport.lower() == "local":
            return asyncio.run(self._async_call_tool(name, arguments or {}))
        return self._submit_worker_request("call_tool", (name, arguments or {}))

    async def _async_call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """异步调用本地模式下的指定工具。"""
        if self.transport.lower() != "local":
            raise MCPHostError("_async_call_tool should not be used for stdio transport")
        from codemind_mcp.server import call_registered_tool

        return await asyncio.wait_for(call_registered_tool(name, arguments), timeout=self.call_timeout)

    def health_check(self) -> bool:
        """执行健康检查，尝试获取工具列表以验证连接状态。"""
        try:
            return bool(self.list_tools())
        except Exception as exc:
            logger.warning(f"MCP client health check failed: {exc}")
            return False

    @property
    def is_initialized(self) -> bool:
        """返回客户端是否已初始化。"""
        return self._initialized

    def _ensure_available(self) -> None:
        """确保客户端已初始化，否则抛出异常。"""
        if not self._initialized:
            raise MCPHostError("MCP client is not initialized")

    def _submit_worker_request(self, action: str, payload: Any) -> Any:
        """向工作协程提交请求并等待结果。"""
        if self._loop_thread is None or self._request_queue is None:
            raise MCPHostError("MCP client worker is not running")
        result_future: Future = Future()
        request = _WorkerRequest(action=action, payload=payload, future=result_future)
        enqueue = self._request_queue.put(request)
        # 跨线程调用，并阻塞等待入队完成
        asyncio.run_coroutine_threadsafe(enqueue, self._loop_thread._loop).result(timeout=self.call_timeout)
        return result_future.result(timeout=self.call_timeout + 1)

    @staticmethod
    def _flatten_content(content: Any) -> str:
        """将 MCP 响应内容展平为字符串。"""
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
        """将 MCP 工具对象转换为字典格式。"""
        return {
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", ""),
            "inputSchema": getattr(tool, "inputSchema", {}),
        }


def _json_schema_to_python_type(schema: dict[str, Any]) -> Any:
    """根据 JSON Schema 类型映射到 Python 类型。"""
    schema_type = schema.get("type", "string")
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        items_schema = schema.get("items", {})
        if items_schema:
            item_type = _json_schema_to_python_type(items_schema)
            return List[item_type]
        return list
    if schema_type == "object":
        properties = schema.get("properties", {})
        if properties:
            nested_fields = {}
            required = set(schema.get("required", []))
            for prop_name, prop_schema in properties.items():
                prop_type = _json_schema_to_python_type(prop_schema)
                default = ... if prop_name in required else prop_schema.get("default", None)
                nested_fields[prop_name] = (prop_type, default)

            nested_model = create_model(
                f"NestedObject_{id(schema)}",
                **nested_fields
            )
            return nested_model
        return dict
    return str


MCPHostClient = MCPClient
"""向后兼容的别名，用于旧版主机端命名。"""


def build_langchain_mcp_tools(mcp_client: MCPClient) -> list[StructuredTool]:
    """获取 MCP 工具并将其适配为 LangChain 工具。"""

    tools = []
    for tool_def in mcp_client.list_tools():
        schema = tool_def.get("inputSchema", {})
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        fields = {}
        for field_name, field_schema in properties.items():
            python_type = _json_schema_to_python_type(field_schema)
            default = ... if field_name in required else field_schema.get("default", None)

            field_description = field_schema.get("description", "")
            fields[field_name] = (
                python_type,
                Field(default=default, description=field_description),
            )

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


async def async_build_langchain_mcp_tools(mcp_client: MCPClient) -> list[StructuredTool]:
    """异步版本：获取 MCP 工具并将其适配为 LangChain 工具，不会阻塞事件循环。

    适用于 FastAPI 异步路由等场景，避免阻塞主事件循环。
    """
    loop = asyncio.get_event_loop()

    tool_defs = await loop.run_in_executor(
        None,
        mcp_client.list_tools
    )

    tools = []
    for tool_def in tool_defs:
        schema = tool_def.get("inputSchema", {})
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        fields = {}

        for field_name, field_schema in properties.items():
            python_type = _json_schema_to_python_type(field_schema)
            default = ... if field_name in required else field_schema.get("default", None)

            field_description = field_schema.get("description", "")
            fields[field_name] = (
                python_type,
                Field(default=default, description=field_description),
            )

        args_model = create_model(f"MCPToolInput_{tool_def['name']}", **fields)

        def _invoke_factory(tool_name: str):
            async def _async_invoke(**kwargs):
                return await loop.run_in_executor(
                    None,
                    lambda: mcp_client.call_tool(tool_name, kwargs)
                )

            def _sync_invoke(**kwargs):
                return mcp_client.call_tool(tool_name, kwargs)

            return _async_invoke if hasattr(asyncio, 'current_task') else _sync_invoke

        invoke_func = _invoke_factory(tool_def["name"])

        tools.append(
            StructuredTool.from_function(
                func=invoke_func,
                name=tool_def["name"],
                description=tool_def.get("description", tool_def["name"]),
                args_schema=args_model,
            )
        )

    return tools

