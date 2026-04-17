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
    检查命令是否在白名单内，同时禁止可能产生大量输出的参数。

    Args:
        command: 待检查的命令（完整命令字符串）
        allowed_commands: 允许的命令列表（仅基础命令名）

    Returns:
        是否允许执行
    """
    # Unix 命令到 Windows 命令的映射（用于安全检查）
    WINDOWS_CMD_MAPPING = {
        "ls": ["dir"],
        "cat": ["type"],
        "grep": ["findstr"],
        "find": ["find"],
        "head": ["head"],
        "tail": ["tail"],
        "wc": ["wc"],
        "git": ["git"],
    }

    # 禁止的参数列表（可能产生大量输出）
    BLOCKED_ARGS = {
        "ls": ["-R", "-r", "--recursive"],
        "dir": ["/S", "/s"],
        "find": [],  # find 本身已经比较受限，但可以进一步限制
    }

    try:
        # 提取命令的基础名称（第一个词）
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return False

        base_cmd = cmd_parts[0].lower()
        args = cmd_parts[1:]

        # 处理可能包含路径的命令（如 /bin/ls）
        base_cmd = os.path.basename(base_cmd)

        # 检查是否有禁止的参数
        if base_cmd in BLOCKED_ARGS:
            for arg in args:
                if arg in BLOCKED_ARGS[base_cmd]:
                    logger.warning(f"Command execution denied: {command} (contains blocked arg: {arg})")
                    return False

        # 也检查映射后的命令
        for unix_cmd, windows_cmds in WINDOWS_CMD_MAPPING.items():
            if base_cmd in windows_cmds and unix_cmd in BLOCKED_ARGS:
                for arg in args:
                    if arg in BLOCKED_ARGS[unix_cmd]:
                        logger.warning(f"Command execution denied: {command} (contains blocked arg: {arg})")
                        return False

        # 直接检查是否在白名单
        if base_cmd in allowed_commands:
            return True

        # 检查是否是映射后的 Windows 命令
        for unix_cmd, windows_cmds in WINDOWS_CMD_MAPPING.items():
            if unix_cmd in allowed_commands and base_cmd in windows_cmds:
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
        allowed_dirs: 允许的目录列表（可以包含 repo_path）
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
