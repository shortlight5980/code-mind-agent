"""
MCP 安全检查模块。

提供路径、文件、命令的安全验证功能，防止 MCP 工具执行危险操作。
"""

from __future__ import annotations

import os
from fnmatch import fnmatch

from utils.logger import get_logger

logger = get_logger("codemind_mcp.security")


def normalize_path(path: str) -> str:
    """规范化路径，解析相对路径符号。"""
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.normpath(path)
    return os.path.abspath(path)


def is_path_allowed(path: str, allowed_dirs: list[str]) -> bool:
    """检查路径是否在允许的目录白名单内。"""
    try:
        abs_path = normalize_path(path)

        for allowed_dir in allowed_dirs:
            abs_allowed_dir = normalize_path(allowed_dir)
            if abs_path == abs_allowed_dir or abs_path.startswith(abs_allowed_dir + os.sep):
                return True

        logger.warning(f"Path access denied: {path} (not in allowed dirs)")
        return False
    except Exception as exc:
        logger.error(f"Error checking path allowance: {exc}")
        return False


def is_sensitive_file(path: str, blocked_patterns: list[str] | None = None) -> bool:
    """检查文件是否为敏感文件。"""
    if blocked_patterns is None:
        blocked_patterns = [
            ".env",
            ".env.*",
            "*.key",
            "*.pem",
            "*.p12",
            "*.pfx",
            "*.cer",
            "*.crt",
            "id_rsa",
            "id_dsa",
            "id_ed25519",
            "*.p8",
            "secrets.yml",
            "config/secrets.yml",
            "*.secret",
        ]

    try:
        filename = os.path.basename(path)

        for pattern in blocked_patterns:
            if fnmatch(filename, pattern) or fnmatch(path, pattern):
                logger.warning(f"Sensitive file access blocked: {path} (matched {pattern})")
                return True

        return False
    except Exception as exc:
        logger.error(f"Error checking sensitive file: {exc}")
        return True


def is_command_allowed(command: str, allowed_commands: list[str]) -> bool:
    """检查命令是否在白名单内，同时禁止可能产生大量输出的参数。"""
    windows_cmd_mapping = {
        "ls": ["dir"],
        "cat": ["type"],
        "grep": ["findstr"],
        "find": ["find"],
        "head": ["head"],
        "tail": ["tail"],
        "wc": ["wc"],
        "git": ["git"],
    }
    blocked_args = {
        "ls": ["-R", "-r", "--recursive"],
        "dir": ["/S", "/s"],
        "find": [],
    }

    try:
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return False

        base_cmd = os.path.basename(cmd_parts[0].lower())
        args = cmd_parts[1:]

        if base_cmd in blocked_args:
            for arg in args:
                if arg in blocked_args[base_cmd]:
                    logger.warning(f"Command execution denied: {command} (contains blocked arg: {arg})")
                    return False

        for unix_cmd, windows_cmds in windows_cmd_mapping.items():
            if base_cmd in windows_cmds and unix_cmd in blocked_args:
                for arg in args:
                    if arg in blocked_args[unix_cmd]:
                        logger.warning(f"Command execution denied: {command} (contains blocked arg: {arg})")
                        return False

        if base_cmd in allowed_commands:
            return True

        for unix_cmd, windows_cmds in windows_cmd_mapping.items():
            if unix_cmd in allowed_commands and base_cmd in windows_cmds:
                return True

        logger.warning(f"Command execution denied: {command} (base cmd: {base_cmd})")
        return False
    except Exception as exc:
        logger.error(f"Error checking command allowance: {exc}")
        return False


def validate_file_access(
    file_path: str,
    allowed_dirs: list[str],
    blocked_patterns: list[str] | None = None,
) -> tuple[bool, str]:
    """综合验证文件访问权限。"""
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"

    if not os.path.isfile(file_path):
        return False, f"不是文件: {file_path}"

    if not is_path_allowed(file_path, allowed_dirs):
        return False, f"路径不在允许的目录白名单内: {file_path}"

    if is_sensitive_file(file_path, blocked_patterns):
        return False, f"禁止访问敏感文件: {file_path}"

    return True, ""
