"""基于沙箱的 MCP 工具封装。"""

from __future__ import annotations

from typing import Any

from codemind_mcp.tool_paths import get_allowed_dirs, get_repo_path
from codemind_mcp.tools.base import BaseMCPTool
from codemind_mcp.tools.read_file import ReadFileTool
from codemind_mcp.tools.run_command import RunCommandTool
from codemind_mcp.tools.search_code import SearchCodeTool
from utils.config import Config

from .e2b_sandbox import E2BSandbox
from .tool_executor import SandboxedToolExecutor


class _SandboxedToolMixin(BaseMCPTool):
    """沙箱工具混入类，用于在 E2B 沙箱中执行工具操作。"""

    async def _with_executor(self, handler):
        """
        创建 E2B 沙箱实例并执行处理函数。

        Args:
            handler: 接收 SandboxedToolExecutor 实例的异步处理函数。

        Returns:
            处理函数的执行结果。
        """
        # 获取 E2B 配置信息
        api_key = Config.get("e2b.api_key") or Config.get_env("E2B_API_KEY", "")
        template = Config.get("e2b.template", "base")
        timeout = int(Config.get("e2b.timeout", 30))
        
        # 获取仓库路径和允许访问的目录
        repo_path = get_repo_path()
        allowed_dirs = get_allowed_dirs()
        workspace_root = Config.get("e2b.workspace_root", "/workspace")

        # 创建沙箱上下文并执行任务
        async with E2BSandbox(api_key=api_key, template=template, timeout=timeout) as sandbox:
            executor = SandboxedToolExecutor(
                sandbox=sandbox,
                repo_path=repo_path,
                allowed_dirs=allowed_dirs,
                workspace_root=workspace_root,
            )
            return await handler(executor)


class SandboxedReadFileTool(_SandboxedToolMixin, ReadFileTool):
    """沙箱化的文件读取工具。"""

    async def call(self, arguments: dict[str, Any]) -> str:
        """
        在沙箱环境中读取文件内容。

        Args:
            arguments: 包含 file_path, start_line, end_line 等参数的字典。

        Returns:
            文件内容的字符串表示。
        """
        return await self._with_executor(
            lambda executor: executor.execute_read_file(
                file_path=arguments["file_path"],
                start_line=arguments.get("start_line"),
                end_line=arguments.get("end_line"),
            )
        )


class SandboxedSearchCodeTool(_SandboxedToolMixin, SearchCodeTool):
    """沙箱化的代码搜索工具。"""

    async def call(self, arguments: dict[str, Any]) -> str:
        """
        在沙箱环境中搜索代码。

        Args:
            arguments: 包含 query, is_regex, search_dir 等参数的字典。

        Returns:
            搜索结果的字符串表示。
        """
        return await self._with_executor(
            lambda executor: executor.execute_search_code(
                query=arguments["query"],
                is_regex=arguments.get("is_regex", False),
                search_dir=arguments.get("search_dir", "."),
            )
        )


class SandboxedRunCommandTool(_SandboxedToolMixin, RunCommandTool):
    """沙箱化的命令执行工具。"""

    async def call(self, arguments: dict[str, Any]) -> str:
        """
        在沙箱环境中执行系统命令。

        Args:
            arguments: 包含 command 等参数的字典。

        Returns:
            命令执行输出的字符串表示。
        """
        # 获取命令执行超时时间
        timeout = int(Config.get("agent.command_timeout", 5))
        return await self._with_executor(
            lambda executor: executor.execute_run_command(
                command=arguments["command"],
                timeout=timeout,
            )
        )
