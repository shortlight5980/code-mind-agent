"""RunCommand MCP wrapper and implementation."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from typing import Any

from .base import BaseMCPTool
from codemind_mcp.output_truncation import truncate_tool_output
from codemind_mcp.security import is_command_allowed
from codemind_mcp.tool_paths import get_repo_path, resolve_repo_relative_path
from utils.config import Config
from utils.logger import get_logger

logger = get_logger("codemind_mcp.tools.run_command")

IS_WINDOWS = sys.platform.startswith("win")

WINDOWS_CMD_MAPPING = {
    "ls": ["dir"],
    "cat": ["type"],
    "grep": ["findstr"],
    "find": None,
    "head": None,
    "tail": None,
    "wc": None,
    "git": ["git"],
}

WINDOWS_ALLOWED_COMMANDS = ["dir", "type", "findstr", "where"]


def _normalize_command_for_windows(command: str) -> tuple[str, list]:
    cmd_parts = command.strip().split()
    if not cmd_parts:
        return "native", cmd_parts

    base_cmd = cmd_parts[0].lower()
    args = cmd_parts[1:]
    if base_cmd in WINDOWS_ALLOWED_COMMANDS:
        return "native", cmd_parts
    if base_cmd not in WINDOWS_CMD_MAPPING:
        return "native", cmd_parts

    mapped = WINDOWS_CMD_MAPPING[base_cmd]
    if mapped is None:
        return "python", (base_cmd, args)

    new_cmd_parts = mapped + args
    if base_cmd == "ls":
        new_args = []
        for arg in args:
            if arg in {"-l", "-la", "-al"}:
                new_args.append("/Q")
            elif arg == "-a":
                new_args.append("/A")
            elif arg in {"-R", "-h", "--human-readable"}:
                continue
            elif not arg.startswith("-"):
                new_args.append(arg)
        new_cmd_parts = ["dir"] + new_args
    if base_cmd == "grep":
        new_cmd_parts = ["findstr"] + args
    return "native", new_cmd_parts


def _execute_python_command(cmd_name: str, args: list) -> str:
    repo_path = get_repo_path()
    try:
        if cmd_name == "find":
            import fnmatch

            max_results = 100
            result = []
            start_path = repo_path
            pattern = "*"
            if args:
                if "-name" in args:
                    idx = args.index("-name")
                    if idx + 1 < len(args):
                        pattern = args[idx + 1]
                for arg in args:
                    if not arg.startswith("-"):
                        start_path = arg
                        break
            start_path = resolve_repo_relative_path(start_path, repo_path)
            for root, dirs, files in os.walk(start_path):
                for name in files + dirs:
                    if fnmatch.fnmatch(name, pattern):
                        result.append(os.path.relpath(os.path.join(root, name), repo_path))
                        if len(result) >= max_results:
                            break
                if len(result) >= max_results:
                    break
            output = "\n".join(result)
            if len(result) >= max_results:
                output += f"\n\n[警告] 结果已截断，仅显示前 {max_results} 条"
            return output

        if cmd_name in {"head", "tail"}:
            n_lines = 10
            file_args = list(args)
            if file_args:
                first = file_args[0]
                if first.startswith("-n"):
                    if len(first) > 2:
                        n_lines = int(first[2:])
                    elif len(file_args) > 1:
                        n_lines = int(file_args[1])
                        file_args = file_args[1:]
                    file_args = file_args[1:]
                elif first.startswith("-") and first[1:].isdigit():
                    n_lines = int(first[1:])
                    file_args = file_args[1:]
            if not file_args:
                return f"[错误] {cmd_name} 命令需要指定文件名"
            file_path = resolve_repo_relative_path(file_args[0], repo_path)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                lines = handle.read().splitlines()
            return "\n".join(lines[:n_lines] if cmd_name == "head" else lines[-n_lines:])

        if cmd_name == "wc":
            if not args:
                return "[错误] wc 命令需要指定文件名"
            show_lines = show_words = show_chars = False
            file_path = None
            for arg in args:
                if arg == "-l":
                    show_lines = True
                elif arg == "-w":
                    show_words = True
                elif arg == "-c":
                    show_chars = True
                elif not arg.startswith("-"):
                    file_path = arg
            if not show_lines and not show_words and not show_chars:
                show_lines = show_words = show_chars = True
            if file_path is None:
                return "[错误] wc 命令需要指定文件名"
            file_path = resolve_repo_relative_path(file_path, repo_path)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
            result = []
            if show_lines:
                result.append(str(content.count("\n") + 1 if content else 0))
            if show_words:
                result.append(str(len(content.split())))
            if show_chars:
                result.append(str(len(content)))
            result.append(file_path)
            return " ".join(result)

        return f"[错误] 不支持的命令: {cmd_name}"
    except Exception as exc:
        logger.error(f"Python command error: {exc}")
        return f"[错误] 命令执行失败: {exc}"


def run_command_impl(command: str) -> str:
    allowed_commands = Config.get("agent.allowed_commands", ["ls", "cat", "grep", "git", "find", "head", "tail", "wc"])
    timeout = Config.get("agent.command_timeout", 5)
    repo_path = get_repo_path()

    if IS_WINDOWS:
        allowed_commands = allowed_commands + WINDOWS_ALLOWED_COMMANDS
    if not is_command_allowed(command, allowed_commands):
        return f"[错误] 命令不在白名单内，禁止执行: {command}"

    try:
        if IS_WINDOWS:
            cmd_type, cmd_data = _normalize_command_for_windows(command)
            if cmd_type == "python":
                result = _execute_python_command(cmd_data[0], cmd_data[1])
                return truncate_tool_output("标准输出:\n" + "-" * 40 + "\n" + result, "RunCommand")
            args = cmd_data
            base_cmd = args[0].lower() if args else ""
            use_shell = base_cmd in {"dir", "type", "findstr"}
            result = subprocess.run(
                args if not use_shell else " ".join(args),
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=use_shell,
                encoding="utf-8",
                errors="ignore",
            )
        else:
            result = subprocess.run(
                shlex.split(command),
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )

        output = []
        if result.stdout:
            output.append("标准输出:\n" + "-" * 40 + "\n" + result.stdout)
        if result.stderr:
            output.append("标准错误:\n" + "-" * 40 + "\n" + result.stderr)
        output.append(f"\n返回码: {result.returncode}")
        return truncate_tool_output("\n".join(output), "RunCommand")
    except subprocess.TimeoutExpired:
        return f"[错误] 命令执行超时（{timeout}秒）: {command}"
    except FileNotFoundError:
        return f"[错误] 命令未找到: {command}"
    except ValueError as exc:
        return f"[错误] 命令格式无效: {exc}"
    except Exception as exc:
        logger.error(f"Error executing command: {exc}")
        return f"[错误] 命令执行失败: {exc}"


class RunCommandTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_run_command"

    @property
    def description(self) -> str:
        return "执行白名单内的只读 shell 命令。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                }
            },
            "required": ["command"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        return await self.run_blocking(run_command_impl, command=arguments["command"])
