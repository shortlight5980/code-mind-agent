"""
ReadFile 工具

使用 LangChain @tool 装饰器定义，用于读取指定仓库文件内容，支持行号范围。
"""
from typing import Optional
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import validate_file_access

logger = get_logger("agent.tools.read_file")


@tool
def ReadFile(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    读取指定文件的内容，支持按行号范围读取。

    Args:
        file_path: 文件路径（相对于项目根目录或绝对路径）
        start_line: 起始行号（从 1 开始，包含），不指定则从文件开头读取
        end_line: 结束行号（包含），不指定则读取到文件末尾

    Returns:
        文件内容字符串
    """
    from utils.config import Config

    logger.info(f"[ToolsCall] ReadFile called: file_path={file_path}, start_line={start_line}, end_line={end_line}")

    # 加载配置
    allowed_dirs = Config.get("agent.allowed_dirs", ["."])
    blocked_patterns = Config.get("agent.blocked_files", None)

    # 安全验证
    is_allowed, error_msg = validate_file_access(file_path, allowed_dirs, blocked_patterns)
    if not is_allowed:
        return f"[错误] {error_msg}"

    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total_lines = len(lines)

        # 处理行号范围
        if start_line is None:
            start_idx = 0
        else:
            start_idx = max(0, start_line - 1)

        if end_line is None:
            end_idx = total_lines
        else:
            end_idx = min(total_lines, end_line)

        if start_idx >= end_idx:
            return f"[警告] 行号范围无效: start_line={start_line}, end_line={end_line}, 文件共 {total_lines} 行"

        # 截取内容并添加行号
        result_lines = []
        for i in range(start_idx, end_idx):
            line_num = i + 1
            result_lines.append(f"{line_num:6d} | {lines[i]}")

        content = ''.join(result_lines)
        file_info = f"文件: {file_path} (总行数: {total_lines}, 显示: {start_idx + 1}-{end_idx})\n"
        separator = "-" * 80 + "\n"

        logger.info(f"Successfully read file: {file_path}")
        logger.debug(file_info + separator + content)
        return file_info + separator + content

    except UnicodeDecodeError:
        # 尝试用其他编码读取
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
            logger.info(f"Successfully read file with gbk encoding: {file_path}")
            return f"文件: {file_path} (GBK 编码)\n" + "-" * 80 + "\n" + content
        except Exception as e2:
            logger.error(f"Failed to read file with fallback encoding: {e2}")
            return f"[错误] 无法读取文件 {file_path}: 编码不支持"
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"[错误] 读取文件失败: {str(e)}"
