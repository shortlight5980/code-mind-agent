"""
MCP-owned implementations for the tools that must only execute via MCP.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from typing import Optional

from agent.security import is_command_allowed, is_path_allowed, validate_file_access
from agent.tool_paths import (
    get_allowed_dirs,
    get_repo_path,
    get_repo_paths_for_read,
    resolve_repo_relative_path,
)
from agent.tools.output_truncation import truncate_tool_output
from utils.config import Config
from utils.logger import get_logger

logger = get_logger("codemind_mcp.tool_impl")

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


def should_ignore_dir(dir_name: str) -> bool:
    ignore_dirs = {
        ".git", "__pycache__", ".venv", "venv", "env", ".env",
        "node_modules", "build", "dist", ".idea", ".vscode",
        "chroma_db", "logs", ".pytest_cache", ".mypy_cache",
    }
    return dir_name in ignore_dirs


def should_ignore_file(file_name: str) -> bool:
    ignore_extensions = {
        ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
        ".bin", ".obj", ".o", ".a", ".lib",
        ".zip", ".tar", ".tar.gz", ".rar",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico",
        ".pdf", ".doc", ".docx", ".ppt", ".pptx",
        ".db", ".sqlite", ".sqlite3",
    }
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ignore_extensions


def resolve_file_path(file_path: str, repo_path: str) -> Optional[str]:
    from agent.security import normalize_path

    if os.path.exists(file_path) and os.path.isfile(file_path):
        return normalize_path(file_path)

    path_in_repo = os.path.join(repo_path, file_path)
    if os.path.exists(path_in_repo) and os.path.isfile(path_in_repo):
        return normalize_path(path_in_repo)

    if os.path.isabs(file_path):
        file_name = os.path.basename(file_path)
        path_in_repo_by_name = os.path.join(repo_path, file_name)
        if os.path.exists(path_in_repo_by_name) and os.path.isfile(path_in_repo_by_name):
            return normalize_path(path_in_repo_by_name)

    return None


def search_file_by_name(file_name: str, search_dirs: list[str]) -> list[str]:
    from agent.security import normalize_path

    allowed_dirs = get_allowed_dirs(include_repo_path=False)
    repo_path = get_repo_path()
    matches: list[str] = []

    for search_root in search_dirs:
        for root, dirs, files in os.walk(search_root):
            dirs[:] = [d for d in dirs if not should_ignore_dir(d)]
            for candidate in files:
                if candidate == file_name and not should_ignore_file(candidate):
                    full_path = os.path.join(root, candidate)
                    if is_path_allowed(full_path, allowed_dirs + [repo_path]):
                        if full_path.startswith(repo_path + os.sep):
                            display_path = os.path.relpath(full_path, repo_path)
                        else:
                            display_path = os.path.relpath(full_path, normalize_path("."))
                        if display_path not in matches:
                            matches.append(display_path)

    return matches


def get_absolute_path_for_display_path(display_path: str, repo_path: str) -> Optional[str]:
    from agent.security import normalize_path

    path_in_repo = os.path.join(repo_path, display_path)
    if os.path.exists(path_in_repo) and os.path.isfile(path_in_repo):
        return normalize_path(path_in_repo)

    path_in_project = normalize_path(display_path)
    if os.path.exists(path_in_project) and os.path.isfile(path_in_project):
        return path_in_project

    return None


def _read_file_with_lines(
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()

        total_lines = len(lines)
        start_idx = 0 if start_line is None else max(0, start_line - 1)
        end_idx = total_lines if end_line is None else min(total_lines, end_line)

        if start_idx >= end_idx:
            return f"[警告] 行号范围无效: start_line={start_line}, end_line={end_line}, 文件共 {total_lines} 行"

        result_lines = [f"{line_num:6d} | {lines[line_num - 1]}" for line_num in range(start_idx + 1, end_idx + 1)]
        content = "".join(result_lines)
        file_info = f"文件: {file_path} (总行数: {total_lines}, 显示: {start_idx + 1}-{end_idx})\n"
        separator = "-" * 80 + "\n"
        return truncate_tool_output(file_info + separator + content, "ReadFile")
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="gbk") as handle:
                content = handle.read()
            return truncate_tool_output(
                f"文件: {file_path} (GBK 编码)\n" + "-" * 80 + "\n" + content,
                "ReadFile",
            )
        except Exception:
            return f"[错误] 无法读取文件 {file_path}: 编码不支持"


def read_file_impl(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    allowed_dirs = get_allowed_dirs(include_repo_path=False)
    blocked_patterns = Config.get("agent.blocked_files", None)
    repo_path, search_dirs = get_repo_paths_for_read()

    try:
        abs_file_path = resolve_file_path(file_path, repo_path)
        if abs_file_path is not None:
            is_allowed, error_msg = validate_file_access(abs_file_path, allowed_dirs + [repo_path], blocked_patterns)
            if not is_allowed:
                return f"[错误] {error_msg}"
            return _read_file_with_lines(abs_file_path, start_line, end_line)

        file_name = os.path.basename(file_path)
        matches = search_file_by_name(file_name, search_dirs)
        if not matches:
            return f"[错误] 读取文件失败: 文件不存在: {file_path} (在仓库路径 {repo_path} 中未找到)"
        if len(matches) == 1:
            abs_found_path = get_absolute_path_for_display_path(matches[0], repo_path)
            if abs_found_path is None:
                return f"[错误] 找到文件但无法访问: {matches[0]}"
            is_allowed, error_msg = validate_file_access(abs_found_path, allowed_dirs + [repo_path], blocked_patterns)
            if not is_allowed:
                return f"[错误] {error_msg}"
            return _read_file_with_lines(abs_found_path, start_line, end_line)

        result = "存在多个同名文件，请传入相对于仓库根目录的完整路径！\n\n找到的文件:\n"
        for index, match in enumerate(matches, 1):
            result += f"{index}. {match}\n"
        return truncate_tool_output(result, "ReadFile")
    except Exception as exc:
        logger.error(f"Error reading file {file_path}: {exc}")
        return f"[错误] 读取文件失败: {exc}"


def search_code_impl(query: str, is_regex: bool = False, search_dir: str = ".") -> str:
    allowed_dirs = get_allowed_dirs()
    max_results = Config.get("agent.max_search_results", 50)
    repo_path = get_repo_path()
    abs_search_dir = resolve_repo_relative_path(search_dir, repo_path)

    if not is_path_allowed(abs_search_dir, allowed_dirs):
        return f"[错误] 搜索目录不在允许的白名单内: {search_dir}"
    if not os.path.exists(abs_search_dir):
        return f"[错误] 搜索目录不存在: {search_dir}"
    if not os.path.isdir(abs_search_dir):
        return f"[错误] 不是目录: {search_dir}"

    try:
        pattern = re.compile(query if is_regex else re.escape(query), re.IGNORECASE)
    except re.error as exc:
        return f"[错误] 正则表达式语法错误: {exc}"

    try:
        results: list[str] = []
        match_count = 0
        for root, dirs, files in os.walk(abs_search_dir):
            dirs[:] = [d for d in dirs if not should_ignore_dir(d)]
            for file_name in files:
                if should_ignore_file(file_name):
                    continue
                file_path = os.path.join(root, file_name)
                if not is_path_allowed(file_path, allowed_dirs):
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as handle:
                        lines = handle.readlines()
                except (UnicodeDecodeError, OSError):
                    continue

                file_matches: list[str] = []
                for line_num, line in enumerate(lines, 1):
                    if pattern.search(line):
                        file_matches.append(f"    行 {line_num}: {line.rstrip(chr(10))}")
                        match_count += 1

                if file_matches:
                    rel_path = os.path.relpath(file_path, abs_search_dir)
                    results.append(f"📄 {rel_path}")
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
    except Exception as exc:
        logger.error(f"Error in SearchCode: {exc}")
        return f"[错误] 搜索失败: {exc}"


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
