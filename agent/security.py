"""
安全检查模块

提供路径、文件、命令的安全验证功能，防止 Agent 执行危险操作。
"""
import os
import re
from typing import List
from fnmatch import fnmatch

from utils.logger import get_logger

logger = get_logger("agent.security")


def normalize_path(path: str) -> str:
    """
    规范化路径，解析相对路径符号。

    Args:
        path: 输入路径

    Returns:
        规范化后的绝对路径
    """
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.normpath(path)
    return os.path.abspath(path)


def is_path_allowed(path: str, allowed_dirs: List[str]) -> bool:
    """
    检查路径是否在允许的目录白名单内。

    Args:
        path: 待检查的路径
        allowed_dirs: 允许访问的目录列表

    Returns:
        是否允许访问
    """
    try:
        abs_path = normalize_path(path)

        for allowed_dir in allowed_dirs:
            abs_allowed_dir = normalize_path(allowed_dir)
            # 检查路径是否以允许目录开头
            if abs_path == abs_allowed_dir or abs_path.startswith(abs_allowed_dir + os.sep):
                return True

        logger.warning(f"Path access denied: {path} (not in allowed dirs)")
        return False
    except Exception as e:
        logger.error(f"Error checking path allowance: {e}")
        return False


def is_sensitive_file(path: str, blocked_patterns: List[str] = None) -> bool:
    """
    检查文件是否为敏感文件。

    Args:
        path: 待检查的文件路径
        blocked_patterns: 敏感文件模式列表（支持 glob 模式）

    Returns:
        是否为敏感文件
    """
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
    except Exception as e:
        logger.error(f"Error checking sensitive file: {e}")
        return True  # 出错时默认阻止访问


def is_command_allowed(command: str, allowed_commands: List[str]) -> bool:
    """
    检查命令是否在白名单内。

    Args:
        command: 待检查的命令（完整命令字符串）
        allowed_commands: 允许的命令列表（仅基础命令名）

    Returns:
        是否允许执行
    """
    try:
        # 提取命令的基础名称（第一个词）
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return False

        base_cmd = cmd_parts[0]

        # 处理可能包含路径的命令（如 /bin/ls）
        base_cmd = os.path.basename(base_cmd)

        if base_cmd in allowed_commands:
            return True

        logger.warning(f"Command execution denied: {command} (base cmd: {base_cmd})")
        return False
    except Exception as e:
        logger.error(f"Error checking command allowance: {e}")
        return False


def validate_file_access(file_path: str, allowed_dirs: List[str], blocked_patterns: List[str] = None) -> tuple[bool, str]:
    """
    综合验证文件访问权限。

    Args:
        file_path: 文件路径
        allowed_dirs: 允许的目录列表
        blocked_patterns: 敏感文件模式列表

    Returns:
        (是否允许, 错误信息)
    """
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"

    if not os.path.isfile(file_path):
        return False, f"不是文件: {file_path}"

    if not is_path_allowed(file_path, allowed_dirs):
        return False, f"路径不在允许的目录白名单内: {file_path}"

    if is_sensitive_file(file_path, blocked_patterns):
        return False, f"禁止访问敏感文件: {file_path}"

    return True, ""
