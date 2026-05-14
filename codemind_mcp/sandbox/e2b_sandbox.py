"""Thin wrapper around the E2B sandbox SDK."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger

logger = get_logger("codemind_mcp.sandbox.e2b")


class E2BSandboxError(RuntimeError):
    """Raised when sandbox operations fail."""


@dataclass
class _CommandResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class E2BSandbox:
    """Manage a single E2B sandbox session."""

    def __init__(self, api_key: str | None = None, template: str | None = None, timeout: int = 30):
        self.api_key = api_key
        self.template = template
        self.timeout = timeout
        self._sandbox: Any | None = None

    async def __aenter__(self) -> "E2BSandbox":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """Create the underlying sandbox lazily."""
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

        try:
            create = getattr(Sandbox, "create", None)
            if callable(create):
                self._sandbox = await create(**kwargs)
            else:
                self._sandbox = Sandbox(**kwargs)
        except Exception as exc:
            raise E2BSandboxError(f"创建 E2B 沙箱失败: {exc}") from exc

    async def close(self) -> None:
        """Close the underlying sandbox session."""
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
        await self.connect()
        try:
            with open(local_path, "rb") as handle:
                data = handle.read()
            await self._maybe_await(self._sandbox.files.write(remote_path, data))
        except Exception as exc:
            raise E2BSandboxError(f"上传文件失败 {local_path} -> {remote_path}: {exc}") from exc

    async def write_file(self, remote_path: str, content: str) -> None:
        await self.connect()
        try:
            await self._maybe_await(self._sandbox.files.write(remote_path, content))
        except Exception as exc:
            raise E2BSandboxError(f"写入沙箱文件失败 {remote_path}: {exc}") from exc

    async def download_file(self, remote_path: str) -> str:
        await self.connect()
        try:
            content = await self._maybe_await(self._sandbox.files.read(remote_path))
        except Exception as exc:
            raise E2BSandboxError(f"读取沙箱文件失败 {remote_path}: {exc}") from exc
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore")
        return str(content)

    async def run_command(self, command: str, timeout: int = 30, cwd: str | None = None) -> dict[str, Any]:
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
        await self.connect()
        try:
            exists = getattr(self._sandbox.files, "exists", None)
            if callable(exists):
                return bool(await self._maybe_await(exists(path)))
            await self._maybe_await(self._sandbox.files.read(path))
            return True
        except Exception:
            return False

    async def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
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
        if asyncio.iscoroutine(value):
            return await value
        return value

    @staticmethod
    def _normalize_command_result(result: Any) -> _CommandResult:
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")
        exit_code = getattr(result, "exit_code", getattr(result, "returncode", 0))
        return _CommandResult(stdout=str(stdout or ""), stderr=str(stderr or ""), exit_code=int(exit_code or 0))
