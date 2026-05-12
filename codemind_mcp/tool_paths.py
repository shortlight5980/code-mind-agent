"""
MCP 工具共享的路径解析逻辑。
"""

from __future__ import annotations

import os

from .security import normalize_path


def get_repo_path() -> str:
    """获取规范化后的仓库根路径。"""
    from utils.config import Config

    repo_path = Config.get("repo.path", ".")
    return normalize_path(repo_path)


def get_allowed_dirs(include_repo_path: bool = True) -> list[str]:
    """获取规范化后的允许访问目录列表。"""
    from utils.config import Config

    allowed_dirs = Config.get("agent.allowed_dirs", ["."])
    normalized = []

    for allowed_dir in allowed_dirs:
        abs_allowed_dir = normalize_path(allowed_dir)
        if abs_allowed_dir not in normalized:
            normalized.append(abs_allowed_dir)

    if include_repo_path:
        repo_path = get_repo_path()
        if repo_path not in normalized:
            normalized.append(repo_path)

    return normalized


def resolve_repo_relative_path(path: str, repo_path: str | None = None) -> str:
    """将工具输入路径解析为绝对路径。"""
    repo_root = repo_path or get_repo_path()

    if not path or path == ".":
        return repo_root

    if os.path.isabs(path):
        return normalize_path(path)

    return normalize_path(os.path.join(repo_root, path))


def get_repo_paths_for_read() -> tuple[str, list[str]]:
    """兼容 ReadFile 的仓库路径和搜索目录需求。"""
    repo_path = get_repo_path()
    search_dirs = []

    if os.path.isdir(repo_path):
        search_dirs.append(repo_path)

    for allowed_dir in get_allowed_dirs(include_repo_path=False):
        if allowed_dir not in search_dirs and os.path.isdir(allowed_dir):
            search_dirs.append(allowed_dir)

    if not search_dirs:
        search_dirs = [normalize_path(".")]

    return repo_path, search_dirs
