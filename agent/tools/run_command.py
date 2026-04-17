"""
RunCommand 工具

使用 LangChain @tool 装饰器定义，用于执行只读 shell 命令。
"""
import subprocess
import shlex
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import is_command_allowed

logger = get_logger("agent.tools.run_command")


@tool
def RunCommand(command: str) -> str:
    """
    执行只读 shell 命令（仅白名单内的命令允许执行）。

    允许的命令: ls, cat, grep, git, find, head, tail, wc

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

    # 安全验证：检查命令是否在白名单内
    if not is_command_allowed(command, allowed_commands):
        return f"[错误] 命令不在白名单内，禁止执行: {command}"

    try:
        # 解析命令（安全解析，防止 shell 注入）
        args = shlex.split(command)

        # 执行命令，不使用 shell=True
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False  # 关键安全设置：不使用 shell
        )

        output = []

        if result.stdout:
            output.append("标准输出:\n" + "-" * 40 + "\n" + result.stdout)

        if result.stderr:
            output.append("标准错误:\n" + "-" * 40 + "\n" + result.stderr)

        output.append(f"\n返回码: {result.returncode}")

        logger.info(f"Command executed successfully: {command}")
        logger.debug("\n".join(output))
        return "\n".join(output)

    except subprocess.TimeoutExpired:
        logger.warning(f"Command timeout: {command}")
        return f"[错误] 命令执行超时（{timeout}秒）: {command}"
    except FileNotFoundError:
        logger.error(f"Command not found: {command}")
        return f"[错误] 命令未找到: {command}"
    except ValueError as e:
        logger.error(f"Invalid command: {e}")
        return f"[错误] 命令格式无效: {str(e)}"
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return f"[错误] 命令执行失败: {str(e)}"
