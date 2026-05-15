"""沙箱支持的 MCP 工具执行助手。"""

from __future__ import annotations

import os
import shlex
from typing import Optional

from codemind_mcp.output_truncation import truncate_tool_output
from codemind_mcp.security import is_command_allowed, is_path_allowed, is_sensitive_file, normalize_path
from codemind_mcp.tools.read_file import (
    get_absolute_path_for_display_path,
    resolve_file_path,
    search_file_by_name,
)
from codemind_mcp.tools.run_command import run_command_impl
from codemind_mcp.tools.search_code import should_ignore_dir, should_ignore_file
from utils.config import Config
from utils.logger import get_logger

from .e2b_sandbox import E2BSandbox, E2BSandboxError

logger = get_logger("codemind_mcp.sandbox.executor")


class SandboxedToolExecutor:
    """在 E2B 沙箱中执行现有工具语义。"""

    def __init__(
        self,
        sandbox: E2BSandbox,
        repo_path: str,
        allowed_dirs: list[str],
        workspace_root: str = "/workspace",
    ):
        self.sandbox = sandbox
        self.repo_path = normalize_path(repo_path)
        self.allowed_dirs = [normalize_path(path) for path in allowed_dirs]
        self.workspace_root = workspace_root.rstrip("/") or "/workspace"
        self.remote_repo_path = f"{self.workspace_root}/repo"
        self._synced_files: set[str] = set()

    async def sync_repo_to_sandbox(self) -> None:
        """将允许的仓库目录树同步到沙箱中。"""
        logger.info("同步仓库目录树到沙箱中...")
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [name for name in dirs if not should_ignore_dir(name)]
            for file_name in files:
                if should_ignore_file(file_name):
                    continue
                local_path = os.path.join(root, file_name)
                if not is_path_allowed(local_path, self.allowed_dirs):
                    continue
                await self._sync_local_file(local_path)

    async def ensure_file_available(self, local_path: str) -> str:
        """按需将单个本地文件同步到沙箱。"""
        logger.info(f"同步文件 {local_path} 到沙箱中...")
        normalized = normalize_path(local_path)
        if normalized not in self._synced_files:
            await self._sync_local_file(normalized)
        return self._to_remote_path(normalized)

    async def execute_read_file(
        self,
        file_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """
        读取文件内容并返回结果。

        Args:
            file_path: 文件路径。
            start_line: 开始行数。
            end_line: 结束行数。

        Returns:
            文件内容。
        """
        blocked_patterns = Config.get("agent.blocked_files", None)
        abs_file_path = resolve_file_path(file_path, self.repo_path)

        if abs_file_path is None:
            matches = search_file_by_name(os.path.basename(file_path), [self.repo_path])
            if not matches:
                return f"[错误] 读取文件失败: 文件不存在: {file_path} (在仓库路径 {self.repo_path} 中未找到)"
            if len(matches) > 1:
                result = "存在多个同名文件，请传入相对于仓库根目录的完整路径！\n\n找到的文件:\n"
                for index, match in enumerate(matches, 1):
                    result += f"{index}. {match}\n"
                return truncate_tool_output(result, "ReadFile")
            abs_file_path = get_absolute_path_for_display_path(matches[0], self.repo_path)
            if abs_file_path is None:
                return f"[错误] 找到文件但无法访问: {matches[0]}"

        if not is_path_allowed(abs_file_path, self.allowed_dirs):
            return f"[错误] 路径不在允许的目录白名单内: {abs_file_path}"
        if is_sensitive_file(abs_file_path, blocked_patterns):
            return f"[错误] 禁止访问敏感文件: {abs_file_path}"

        remote_path = await self.ensure_file_available(abs_file_path)
        content = await self.sandbox.read_file(remote_path, start_line=start_line, end_line=end_line)
        return self._format_read_file_output(abs_file_path, content, start_line, end_line)

    async def execute_search_code(self, query: str, is_regex: bool = False, search_dir: str = ".") -> str:
        import re

        max_results = Config.get("agent.max_search_results", 50)
        abs_search_dir = self._resolve_search_dir(search_dir)
        if not is_path_allowed(abs_search_dir, self.allowed_dirs):
            return f"[错误] 搜索目录不在允许的白名单内: {search_dir}"
        if not os.path.exists(abs_search_dir):
            return f"[错误] 搜索目录不存在: {search_dir}"
        if not os.path.isdir(abs_search_dir):
            return f"[错误] 不是目录: {search_dir}"

        try:
            pattern = re.compile(query if is_regex else re.escape(query), re.IGNORECASE)
        except re.error as exc:
            return f"[错误] 正则表达式语法错误: {exc}"

        results: list[str] = []
        match_count = 0
        for root, dirs, files in os.walk(abs_search_dir):
            dirs[:] = [name for name in dirs if not should_ignore_dir(name)]
            for file_name in files:
                if should_ignore_file(file_name):
                    continue
                local_path = os.path.join(root, file_name)
                if not is_path_allowed(local_path, self.allowed_dirs):
                    continue
                remote_path = await self.ensure_file_available(local_path)
                try:
                    content = await self.sandbox.read_file(remote_path)
                except E2BSandboxError as exc:
                    logger.warning(f"跳过无法读取的沙箱文件 {remote_path}: {exc}")
                    continue

                file_matches: list[str] = []
                for line_num, line in enumerate(content.splitlines(), 1):
                    if pattern.search(line):
                        file_matches.append(f"    行 {line_num}: {line}")
                        match_count += 1

                if file_matches:
                    rel_path = os.path.relpath(local_path, abs_search_dir)
                    results.append(f"文件 {rel_path}")
                    results.extend(file_matches)
                    results.append("")

                if len(results) >= max_results * 3:
                    results.append(f"... (结果数量已达上限，仅显示前 {max_results} 个匹配)")
                    break
            if len(results) >= max_results * 3:
                break

        if not results:
            return f"未找到匹配内容: {query}"

        header = f"搜索结果 (共 {match_count} 个匹配):\n" + "=" * 80 + "\n"
        return truncate_tool_output(header + "\n".join(results), "SearchCode")

    async def execute_run_command(self, command: str, timeout: int = 5) -> str:
        allowed_commands = Config.get(
            "agent.allowed_commands",
            ["ls", "cat", "grep", "git", "find", "head", "tail", "wc"],
        )
        if not is_command_allowed(command, allowed_commands):
            return f"[错误] 命令不在白名单内，禁止执行: {command}"

        if self._should_use_local_readonly_execution(command):
            logger.info("Using local readonly command path for sandboxed command: %s", command)
            return run_command_impl(command)

        if Config.get("e2b.repo_sync_enabled", True):
            await self.sync_repo_to_sandbox()

        result = await self.sandbox.run_command(command, timeout=timeout, cwd=self.remote_repo_path)
        output: list[str] = []
        if result["stdout"]:
            output.append("标准输出:\n" + "-" * 40 + "\n" + result["stdout"])
        if result["stderr"]:
            output.append("标准错误:\n" + "-" * 40 + "\n" + result["stderr"])
        output.append(f"\n返回码: {result['returncode']}")
        return truncate_tool_output("\n".join(output), "RunCommand")

    @staticmethod
    def _should_use_local_readonly_execution(command: str) -> bool:
        """避免为轻量级只读命令进行完整的仓库沙箱同步。"""
        try:
            parts = shlex.split(command)
        except ValueError:
            return False

        if not parts:
            return False
        return os.path.basename(parts[0]).lower() in {"ls", "cat", "grep", "find", "head", "tail", "wc"}

    def _resolve_search_dir(self, search_dir: str) -> str:
        if not search_dir or search_dir == ".":
            return self.repo_path
        if os.path.isabs(search_dir):
            return normalize_path(search_dir)
        return normalize_path(os.path.join(self.repo_path, search_dir))

    async def _sync_local_file(self, local_path: str) -> None:
        remote_path = self._to_remote_path(local_path)
        await self.sandbox.upload_file(local_path, remote_path)
        self._synced_files.add(normalize_path(local_path))

    def _to_remote_path(self, local_path: str) -> str:
        relative = os.path.relpath(normalize_path(local_path), self.repo_path).replace(os.sep, "/")
        return f"{self.remote_repo_path}/{relative}"

    @staticmethod
    def _format_read_file_output(
        file_path: str,
        content: str,
        start_line: Optional[int],
        end_line: Optional[int],
    ) -> str:
        lines = content.splitlines(keepends=True)
        if start_line is None and end_line is None:
            start_idx = 0
        else:
            start_idx = 0 if start_line is None else max(0, start_line - 1)
        end_idx = start_idx + len(lines)
        if not lines:
            return "[警告] 文件为空或指定范围无内容"
        result_lines = [f"{line_num:6d} | {line}" for line_num, line in enumerate(lines, start_idx + 1)]
        file_info = f"文件: {file_path} (显示: {start_idx + 1}-{end_idx})\n"
        separator = "-" * 80 + "\n"
        return truncate_tool_output(file_info + separator + "".join(result_lines), "ReadFile")
