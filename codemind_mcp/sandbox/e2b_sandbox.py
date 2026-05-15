"""E2B 沙箱 SDK 的轻量级封装。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger

logger = get_logger("codemind_mcp.sandbox.e2b")


class E2BSandboxError(RuntimeError):
    """当沙箱操作失败时抛出此异常。"""


@dataclass
class _CommandResult:
    """命令执行结果的内部数据结构。"""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class E2BSandbox:
    """管理单个 E2B 沙箱会话。"""

    def __init__(self, api_key: str | None = None, template: str | None = None, timeout: int = 30):
        """初始化 E2B 沙箱客户端。

        Args:
            api_key: E2B API 密钥，如果未提供则使用环境变量。
            template: 沙箱模板 ID。
            timeout: 默认超时时间（秒）。
        """
        self.api_key = api_key
        self.template = template
        self.timeout = timeout
        self._sandbox: Any | None = None

    async def __aenter__(self) -> "E2BSandbox":
        """异步上下文管理器入口，自动连接沙箱。"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口，自动关闭沙箱。"""
        await self.close()

    async def connect(self) -> None:
        """懒加载创建底层沙箱实例。"""
        if self._sandbox is not None:
            return

        try:
            from e2b import Sandbox
        except Exception as exc:
            raise E2BSandboxError(f"无法导入 E2B SDK: {exc}") from exc

        kwargs: dict[str, Any] = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.template:
            kwargs["template"] = self.template
        if self.timeout:
            kwargs["timeout"] = self.timeout

        try:
            # 兼容不同版本的 SDK 初始化方式
            create = getattr(Sandbox, "create", None)
            if callable(create):
                self._sandbox = await self._maybe_await(create(**kwargs))
            else:
                self._sandbox = await self._maybe_await(Sandbox(**kwargs))
        except Exception as exc:
            raise E2BSandboxError(f"创建 E2B 沙箱失败: {exc}") from exc

    async def close(self) -> None:
        """关闭底层沙箱会话。"""
        if self._sandbox is None:
            return
        try:
            close = getattr(self._sandbox, "close", None)
            if asyncio.iscoroutinefunction(close):
                await close()
            elif callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        except Exception as exc:
            logger.warning(f"关闭 E2B 沙箱失败: {exc}")
        finally:
            self._sandbox = None

    async def upload_file(self, local_path: str, remote_path: str) -> None:
        """上传本地文件到沙箱。

        Args:
            local_path: 本地文件路径。
            remote_path: 沙箱内的目标路径。
        """
        await self.connect()
        try:
            with open(local_path, "rb") as handle:
                data = handle.read()
            await self._maybe_await(self._sandbox.files.write(remote_path, data))
        except Exception as exc:
            raise E2BSandboxError(f"上传文件失败 {local_path} -> {remote_path}: {exc}") from exc

    async def write_file(self, remote_path: str, content: str) -> None:
        """将字符串内容写入沙箱文件。

        Args:
            remote_path: 沙箱内的文件路径。
            content: 要写入的文件内容。
        """
        await self.connect()
        try:
            await self._maybe_await(self._sandbox.files.write(remote_path, content))
        except Exception as exc:
            raise E2BSandboxError(f"写入沙箱文件失败 {remote_path}: {exc}") from exc

    async def download_file(self, remote_path: str) -> str:
        """从沙箱下载文件内容。

        Args:
            remote_path: 沙箱内的文件路径。

        Returns:
            文件内容字符串。
        """
        await self.connect()

        try:
            content = await self._maybe_await(self._sandbox.files.read(remote_path))
        except Exception as exc:
            raise E2BSandboxError(f"读取沙箱文件失败 {remote_path}: {exc}") from exc

        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore")
        return str(content)

    async def run_command(self, command: str, timeout: int = 30, cwd: str | None = None) -> dict[str, Any]:
        """在沙箱中执行命令。

        Args:
            command: 要执行的 shell 命令。
            timeout: 命令执行超时时间（秒）。
            cwd: 工作目录。

        Returns:
            包含 stdout, stderr 和 returncode 的字典。
        """
        await self.connect()
        try:
            kwargs: dict[str, Any] = {"timeout": timeout}
            if cwd:
                kwargs["cwd"] = cwd
            result = await self._maybe_await(self._sandbox.commands.run(command, **kwargs))
        except Exception as exc:
            raise E2BSandboxError(f"执行沙箱命令失败: {exc}") from exc
        normalized = self._normalize_command_result(result)
        return {
            "stdout": normalized.stdout,
            "stderr": normalized.stderr,
            "returncode": normalized.exit_code,
        }

    async def list_dir(self, path: str) -> list[str]:
        """列出沙箱目录下的文件和子目录。

        Args:
            path: 沙箱内的目录路径。

        Returns:
            文件名列表。
        """
        await self.connect()
        try:
            entries = await self._maybe_await(self._sandbox.files.list(path))
        except Exception as exc:
            raise E2BSandboxError(f"列出沙箱目录失败 {path}: {exc}") from exc

        names: list[str] = []
        for entry in entries or []:
            name = getattr(entry, "name", None)
            if name is not None:
                names.append(str(name))
            else:
                names.append(str(entry))
        return names

    async def file_exists(self, path: str) -> bool:
        """检查沙箱内文件或目录是否存在。

        Args:
            path: 沙箱内的路径。

        Returns:
            如果存在返回 True，否则返回 False。
        """
        await self.connect()
        try:
            exists = getattr(self._sandbox.files, "exists", None)
            if callable(exists):
                return bool(await self._maybe_await(exists(path)))
            # 如果没有 exists 方法，尝试读取文件作为存在性检查
            await self._maybe_await(self._sandbox.files.read(path))
            return True
        except Exception:
            return False

    async def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """读取沙箱文件内容，支持按行范围读取。

        Args:
            path: 沙箱内的文件路径。
            start_line: 起始行号（从1开始），None 表示从头开始。
            end_line: 结束行号（包含），None 表示到末尾。

        Returns:
            指定行范围的文件内容字符串。
        """
        content = await self.download_file(path)
        if start_line is None and end_line is None:
            return content

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)
        start_idx = 0 if start_line is None else max(0, start_line - 1)
        end_idx = total_lines if end_line is None else min(total_lines, end_line)
        if start_idx >= end_idx:
            return ""
        return "".join(lines[start_idx:end_idx])

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        """如果值是协程则等待它，否则直接返回。用于兼容同步/异步 API。"""
        if asyncio.iscoroutine(value):
            return await value
        return value

    @staticmethod
    def _normalize_command_result(result: Any) -> _CommandResult:
        """标准化命令执行结果对象。"""
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")
        exit_code = getattr(result, "exit_code", getattr(result, "returncode", 0))
        return _CommandResult(stdout=str(stdout or ""), stderr=str(stderr or ""), exit_code=int(exit_code or 0))
