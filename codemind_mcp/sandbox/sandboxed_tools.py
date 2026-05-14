"""Sandbox-backed MCP tool wrappers."""

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
    async def _with_executor(self, handler):
        api_key = Config.get("e2b.api_key") or Config.get_env("E2B_API_KEY", "")
        template = Config.get("e2b.template", "base")
        timeout = int(Config.get("e2b.timeout", 30))
        repo_path = get_repo_path()
        allowed_dirs = get_allowed_dirs()
        workspace_root = Config.get("e2b.workspace_root", "/workspace")

        async with E2BSandbox(api_key=api_key, template=template, timeout=timeout) as sandbox:
            executor = SandboxedToolExecutor(
                sandbox=sandbox,
                repo_path=repo_path,
                allowed_dirs=allowed_dirs,
                workspace_root=workspace_root,
            )
            return await handler(executor)


class SandboxedReadFileTool(_SandboxedToolMixin, ReadFileTool):
    async def call(self, arguments: dict[str, Any]) -> str:
        return await self._with_executor(
            lambda executor: executor.execute_read_file(
                file_path=arguments["file_path"],
                start_line=arguments.get("start_line"),
                end_line=arguments.get("end_line"),
            )
        )


class SandboxedSearchCodeTool(_SandboxedToolMixin, SearchCodeTool):
    async def call(self, arguments: dict[str, Any]) -> str:
        return await self._with_executor(
            lambda executor: executor.execute_search_code(
                query=arguments["query"],
                is_regex=arguments.get("is_regex", False),
                search_dir=arguments.get("search_dir", "."),
            )
        )


class SandboxedRunCommandTool(_SandboxedToolMixin, RunCommandTool):
    async def call(self, arguments: dict[str, Any]) -> str:
        timeout = int(Config.get("agent.command_timeout", 5))
        return await self._with_executor(
            lambda executor: executor.execute_run_command(
                command=arguments["command"],
                timeout=timeout,
            )
        )
