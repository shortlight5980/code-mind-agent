"""
RunCommand 工具

使用 LangChain @tool 装饰器定义，用于执行只读 shell 命令。
支持 Windows 和 Unix 系统，自动进行命令映射。
"""
import subprocess
import shlex
import os
import sys
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import is_command_allowed

logger = get_logger("agent.tools.run_command")

# 操作系统检测
IS_WINDOWS = sys.platform.startswith("win")

# Unix 命令到 Windows 命令的映射
# 对于复杂命令，我们提供 Python 实现
WINDOWS_CMD_MAPPING = {
    "ls": ["dir"],
    "cat": ["type"],
    "grep": ["findstr"],
    "find": None,  # 使用 Python 实现
    "head": None,  # 使用 Python 实现
    "tail": None,  # 使用 Python 实现
    "wc": None,    # 使用 Python 实现
    "git": ["git"],  # git 在 Windows 上通常也可用
}

# 同时也允许直接使用 Windows 命令
WINDOWS_ALLOWED_COMMANDS = ["dir", "type", "findstr", "where"]


def _normalize_command_for_windows(command: str) -> tuple[str, list]:
    """
    将 Unix 命令转换为 Windows 命令或 Python 实现

    Returns:
        (command_type, command_data)
        - "native": 使用原生命令，command_data 是 args 列表
        - "python": 使用 Python 实现，command_data 是函数名和参数
    """
    cmd_parts = command.strip().split()
    if not cmd_parts:
        return "native", cmd_parts

    base_cmd = cmd_parts[0].lower()
    args = cmd_parts[1:]

    # 如果已经是 Windows 命令，直接返回
    if base_cmd in WINDOWS_ALLOWED_COMMANDS:
        return "native", cmd_parts

    # 检查是否有映射
    if base_cmd not in WINDOWS_CMD_MAPPING:
        return "native", cmd_parts

    mapped = WINDOWS_CMD_MAPPING[base_cmd]

    # 如果映射为 None，表示使用 Python 实现
    if mapped is None:
        return "python", (base_cmd, args)

    # 替换命令并调整参数
    new_cmd_parts = mapped + args

    # 特殊处理：dir 命令的参数调整
    if base_cmd == "ls":
        # 将 ls 的常见参数转换为 dir 的参数
        new_args = []
        for arg in args:
            if arg == "-l" or arg == "-la" or arg == "-al":
                new_args.append("/Q")  # 显示所有者
            elif arg == "-a":
                new_args.append("/A")  # 显示所有文件
            elif arg == "-R":
                # 禁止递归，跳过此参数
                continue
            elif arg == "-h" or arg == "--human-readable":
                continue  # dir 默认就比较友好
            elif not arg.startswith("-"):
                new_args.append(arg)
        new_cmd_parts = ["dir"] + new_args

    # 特殊处理：grep -> findstr
    if base_cmd == "grep":
        # findstr 的参数顺序不同：pattern file
        new_cmd_parts = ["findstr"] + args

    return "native", new_cmd_parts


def _execute_python_command(cmd_name: str, args: list) -> str:
    """使用 Python 实现的命令"""
    from utils.config import Config

    repo_path = Config.get("repo.path", ".")

    try:
        if cmd_name == "find":
            # 实现简单的 find 命令（限制最多 100 条结果）
            MAX_RESULTS = 100
            result = []
            start_path = repo_path
            pattern = "*"

            # 简单解析参数
            if args:
                # 查找 -name 参数
                if "-name" in args:
                    idx = args.index("-name")
                    if idx + 1 < len(args):
                        pattern = args[idx + 1]
                # 第一个非 - 开头的参数作为起始路径
                for arg in args:
                    if not arg.startswith("-"):
                        start_path = arg
                        break

            # 确保起始路径是绝对路径
            if not os.path.isabs(start_path):
                start_path = os.path.join(repo_path, start_path)

            # 递归查找
            import fnmatch
            for root, dirs, files in os.walk(start_path):
                for name in files + dirs:
                    if fnmatch.fnmatch(name, pattern):
                        rel_path = os.path.relpath(os.path.join(root, name), repo_path)
                        result.append(rel_path)
                        if len(result) >= MAX_RESULTS:
                            break
                if len(result) >= MAX_RESULTS:
                    break

            output = "\n".join(result)
            if len(result) >= MAX_RESULTS:
                output += f"\n\n[警告] 结果已截断，仅显示前 {MAX_RESULTS} 条"

            return output

        elif cmd_name == "head":
            # 实现 head 命令
            n_lines = 10
            file_path = None

            if args:
                if args[0].startswith("-n"):
                    if len(args[0]) > 2:
                        n_lines = int(args[0][2:])
                    elif len(args) > 1:
                        n_lines = int(args[1])
                        args = args[1:]
                    args = args[1:]
                elif args[0].startswith("-") and args[0][1:].isdigit():
                    n_lines = int(args[0][1:])
                    args = args[1:]

            if args:
                file_path = args[0]
                if not os.path.isabs(file_path):
                    file_path = os.path.join(repo_path, file_path)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= n_lines:
                            break
                        lines.append(line.rstrip("\n"))
                    return "\n".join(lines)
            else:
                return "[错误] head 命令需要指定文件名"

        elif cmd_name == "tail":
            # 实现 tail 命令
            n_lines = 10
            file_path = None

            if args:
                if args[0].startswith("-n"):
                    if len(args[0]) > 2:
                        n_lines = int(args[0][2:])
                    elif len(args) > 1:
                        n_lines = int(args[1])
                        args = args[1:]
                    args = args[1:]
                elif args[0].startswith("-") and args[0][1:].isdigit():
                    n_lines = int(args[0][1:])
                    args = args[1:]

            if args:
                file_path = args[0]
                if not os.path.isabs(file_path):
                    file_path = os.path.join(repo_path, file_path)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                    return "\n".join(lines[-n_lines:])
            else:
                return "[错误] tail 命令需要指定文件名"

        elif cmd_name == "wc":
            # 实现 wc 命令
            show_lines = False
            show_words = False
            show_chars = False
            file_path = None

            if not args:
                return "[错误] wc 命令需要指定文件名"

            # 解析参数
            for arg in args:
                if arg == "-l":
                    show_lines = True
                elif arg == "-w":
                    show_words = True
                elif arg == "-c":
                    show_chars = True
                elif not arg.startswith("-"):
                    file_path = arg

            # 默认显示全部
            if not show_lines and not show_words and not show_chars:
                show_lines = show_words = show_chars = True

            if file_path:
                if not os.path.isabs(file_path):
                    file_path = os.path.join(repo_path, file_path)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.count("\n") + 1 if content else 0
                    words = len(content.split())
                    chars = len(content)

                    result = []
                    if show_lines:
                        result.append(str(lines))
                    if show_words:
                        result.append(str(words))
                    if show_chars:
                        result.append(str(chars))
                    result.append(file_path)

                    return " ".join(result)
            else:
                return "[错误] wc 命令需要指定文件名"

        else:
            return f"[错误] 不支持的命令: {cmd_name}"

    except Exception as e:
        logger.error(f"Python command error: {e}")
        return f"[错误] 命令执行失败: {str(e)}"


@tool
def RunCommand(command: str) -> str:
    """
    执行只读 shell 命令（仅白名单内的命令允许执行）。

    允许的命令: ls（推荐-l,禁止-R）, cat, grep, git, find, head, tail, wc
    （Windows 系统自动映射到等效命令或使用 Python 实现）

    Args:
        command: 要执行的 shell 命令字符串

    Returns:
        命令执行结果（stdout + stderr）
    """
    from utils.config import Config

    logger.info(f"RunCommand called: {command}")

    # 加载配置
    allowed_commands = Config.get("agent.allowed_commands", [
        "ls", "cat", "grep", "git", "find", "head", "tail", "wc"
    ])
    timeout = Config.get("agent.command_timeout", 5)
    repo_path = Config.get("repo.path", ".")

    # Windows 下也允许使用 Windows 原生命令
    if IS_WINDOWS:
        allowed_commands = allowed_commands + WINDOWS_ALLOWED_COMMANDS

    # 安全验证：检查命令是否在白名单内
    if not is_command_allowed(command, allowed_commands):
        return f"[错误] 命令不在白名单内，禁止执行: {command}"

    try:
        # Windows 系统特殊处理
        if IS_WINDOWS:
            cmd_type, cmd_data = _normalize_command_for_windows(command)

            if cmd_type == "python":
                # 使用 Python 实现
                logger.info(f"Using Python implementation for: {command}")
                result = _execute_python_command(cmd_data[0], cmd_data[1])
                return "标准输出:\n" + "-" * 40 + "\n" + result

            # 使用原生命令，但需要设置 shell=True 才能正确执行 dir 等内置命令
            args = cmd_data
            work_dir = os.path.abspath(repo_path)

            logger.info(f"Executing Windows command: {args} in {work_dir}")

            # 对于 Windows 内置命令（如 dir），需要使用 shell=True
            base_cmd = args[0].lower() if args else ""
            use_shell = base_cmd in ["dir", "type", "findstr"]

            result = subprocess.run(
                args if not use_shell else " ".join(args),
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=use_shell,
                encoding="utf-8",
                errors="ignore"
            )
        else:
            # Unix 系统正常处理
            args = shlex.split(command)
            work_dir = os.path.abspath(repo_path)

            result = subprocess.run(
                args,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )

        output = []
        MAX_OUTPUT_CHARS = 10000  # 最大输出字符数

        if result.stdout:
            stdout_content = result.stdout
            if len(stdout_content) > MAX_OUTPUT_CHARS:
                stdout_content = stdout_content[:MAX_OUTPUT_CHARS] + "\n\n[警告] 输出已截断，超过 %d 字符" % MAX_OUTPUT_CHARS
            output.append("标准输出:\n" + "-" * 40 + "\n" + stdout_content)

        if result.stderr:
            stderr_content = result.stderr
            if len(stderr_content) > MAX_OUTPUT_CHARS:
                stderr_content = stderr_content[:MAX_OUTPUT_CHARS] + "\n\n[警告] 输出已截断，超过 %d 字符" % MAX_OUTPUT_CHARS
            output.append("标准错误:\n" + "-" * 40 + "\n" + stderr_content)

        output.append(f"\n返回码: {result.returncode}")

        logger.info(f"Command executed successfully: {command}")
        logger.debug("\n".join(output))
        return "\n".join(output)

    except subprocess.TimeoutExpired:
        logger.warning(f"Command timeout: {command}")
        return f"[错误] 命令执行超时（{timeout}秒）: {command}"
    except FileNotFoundError as e:
        logger.error(f"Command not found: {command} (error: {e})")
        return f"[错误] 命令未找到: {command}"
    except ValueError as e:
        logger.error(f"Invalid command: {e}")
        return f"[错误] 命令格式无效: {str(e)}"
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return f"[错误] 命令执行失败: {str(e)}"
