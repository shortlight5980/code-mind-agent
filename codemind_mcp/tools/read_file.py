"""ReadFile MCP wrapper and implementation."""

from __future__ import annotations

import os
from typing import Any, Optional

from .base import BaseMCPTool
from .output_truncation import truncate_tool_output
from codemind_mcp.security import is_path_allowed, validate_file_access
from codemind_mcp.tool_paths import get_allowed_dirs, get_repo_path, get_repo_paths_for_read
from utils.config import Config
from utils.logger import get_logger

logger = get_logger("codemind_mcp.tools.read_file")


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
    from codemind_mcp.security import normalize_path

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
    from codemind_mcp.security import normalize_path

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
    from codemind_mcp.security import normalize_path

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


class ReadFileTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_read_file"

    @property
    def description(self) -> str:
        return "读取指定文件内容，支持按行号范围读取。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（相对于被索引仓库根目录）",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从 1 开始，包含）",
                    "minimum": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（包含）",
                    "minimum": 1,
                },
            },
            "required": ["file_path"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        return await self.run_blocking(
            read_file_impl,
            file_path=arguments["file_path"],
            start_line=arguments.get("start_line"),
            end_line=arguments.get("end_line"),
        )
