"""SearchCode MCP wrapper and implementation."""

from __future__ import annotations

import os
import re
from typing import Any

from .base import BaseMCPTool
from .output_truncation import truncate_tool_output
from codemind_mcp.security import is_path_allowed
from codemind_mcp.tool_paths import get_allowed_dirs, get_repo_path, resolve_repo_relative_path
from utils.config import Config
from utils.logger import get_logger

logger = get_logger("codemind_mcp.tools.search_code")


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
    except Exception as exc:
        logger.error(f"Error in SearchCode: {exc}")
        return f"[错误] 搜索失败: {exc}"


class SearchCodeTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_search_code"

    @property
    def description(self) -> str:
        return "在代码库中搜索关键词或正则表达式。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或正则表达式",
                },
                "is_regex": {
                    "type": "boolean",
                    "description": "是否使用正则表达式搜索",
                    "default": False,
                },
                "search_dir": {
                    "type": "string",
                    "description": "搜索目录，相对于仓库根目录",
                    "default": ".",
                },
            },
            "required": ["query"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        return await self.run_blocking(
            search_code_impl,
            query=arguments["query"],
            is_regex=arguments.get("is_regex", False),
            search_dir=arguments.get("search_dir", "."),
        )
