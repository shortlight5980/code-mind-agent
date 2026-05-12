"""
ReadFile 工具

使用 LangChain @tool 装饰器定义，用于读取指定仓库文件内容，支持行号范围。
"""
import os
from typing import Optional, List, Tuple
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import validate_file_access, is_path_allowed, normalize_path
from agent.tool_paths import get_allowed_dirs, get_repo_path, get_repo_paths_for_read
from agent.tools.output_truncation import truncate_tool_output

logger = get_logger("agent.tools.read_file")


def should_ignore_dir(dir_name: str) -> bool:
    """判断是否应该忽略的目录"""
    ignore_dirs = {
        '.git', '__pycache__', '.venv', 'venv', 'env', '.env',
        'node_modules', 'build', 'dist', '.idea', '.vscode',
        'chroma_db', 'logs', '.pytest_cache', '.mypy_cache'
    }
    return dir_name in ignore_dirs


def should_ignore_file(file_name: str) -> bool:
    """判断是否应该忽略的文件"""
    ignore_extensions = {
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe',
        '.bin', '.obj', '.o', '.a', '.lib',
        '.zip', '.tar', '.tar.gz', '.rar',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
        '.pdf', '.doc', '.docx', '.ppt', '.pptx',
        '.db', '.sqlite', '.sqlite3'
    }
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ignore_extensions


def get_repo_paths() -> Tuple[str, List[str]]:
    """
    获取仓库路径配置和有效的搜索目录列表

    Returns:
        (repo_path, search_dirs) - 仓库路径和搜索目录列表
    """
    return get_repo_paths_for_read()


def resolve_file_path(file_path: str, repo_path: str) -> Optional[str]:
    """
    尝试解析文件路径，支持多种方式

    Args:
        file_path: 用户传入的文件路径
        repo_path: 仓库根路径

    Returns:
        解析后的绝对路径，如果不存在返回 None
    """
    # 方式 1：直接尝试原始路径
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return normalize_path(file_path)

    # 方式 2：在 repo_path 下查找
    path_in_repo = os.path.join(repo_path, file_path)
    if os.path.exists(path_in_repo) and os.path.isfile(path_in_repo):
        return normalize_path(path_in_repo)

    # 方式 3：如果传入的是绝对路径，尝试只取文件名在 repo_path 下查找
    if os.path.isabs(file_path):
        file_name = os.path.basename(file_path)
        path_in_repo_by_name = os.path.join(repo_path, file_name)
        if os.path.exists(path_in_repo_by_name) and os.path.isfile(path_in_repo_by_name):
            return normalize_path(path_in_repo_by_name)

    return None


def search_file_by_name(file_name: str, search_dirs: List[str]) -> List[str]:
    """
    在指定目录中搜索指定文件名

    Args:
        file_name: 要搜索的文件名
        search_dirs: 要搜索的目录列表

    Returns:
        匹配的文件路径列表（相对路径或显示路径）
    """
    allowed_dirs = get_allowed_dirs(include_repo_path=False)
    repo_path = get_repo_path()

    matches = []

    # 遍历搜索
    for search_root in search_dirs:
        for root, dirs, files in os.walk(search_root):
            # 过滤忽略目录
            dirs[:] = [d for d in dirs if not should_ignore_dir(d)]

            for f in files:
                if f == file_name and not should_ignore_file(f):
                    full_path = os.path.join(root, f)
                    # 验证路径安全
                    if is_path_allowed(full_path, allowed_dirs + [repo_path]):
                        # 优先显示相对于 repo_path 的路径
                        if full_path.startswith(repo_path + os.sep):
                            display_path = os.path.relpath(full_path, repo_path)
                        else:
                            display_path = os.path.relpath(full_path, normalize_path("."))
                        if display_path not in matches:
                            matches.append(display_path)

    return matches


def get_absolute_path_for_display_path(display_path: str, repo_path: str) -> Optional[str]:
    """
    根据显示路径获取绝对路径

    Args:
        display_path: 显示路径（相对于 repo_path 或项目根目录）
        repo_path: 仓库根路径

    Returns:
        绝对路径，如果不存在返回 None
    """
    # 先尝试在 repo_path 下查找
    path_in_repo = os.path.join(repo_path, display_path)
    if os.path.exists(path_in_repo) and os.path.isfile(path_in_repo):
        return normalize_path(path_in_repo)

    # 再尝试相对于项目根目录
    path_in_project = normalize_path(display_path)
    if os.path.exists(path_in_project) and os.path.isfile(path_in_project):
        return path_in_project

    return None


def _read_file_with_lines(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    内部辅助函数：读取文件内容并处理行号范围

    Args:
        file_path: 文件路径
        start_line: 起始行号
        end_line: 结束行号

    Returns:
        格式化的文件内容字符串
    """
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
        return truncate_tool_output(file_info + separator + content, "ReadFile")

    except UnicodeDecodeError:
        # 尝试用其他编码读取
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
            logger.info(f"Successfully read file with gbk encoding: {file_path}")
            return truncate_tool_output(
                f"文件: {file_path} (GBK 编码)\n" + "-" * 80 + "\n" + content,
                "ReadFile",
            )
        except Exception as e2:
            logger.error(f"Failed to read file with fallback encoding: {e2}")
            return f"[错误] 无法读取文件 {file_path}: 编码不支持"


@tool
def ReadFile(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    读取指定文件的内容，支持按行号范围读取。
    【重要】：文件路径相对于被索引仓库的根目录！
    【重要】：当需要读文档时，按行分批读，防止文件过大！

    Args:
        file_path: 文件路径（相对于被索引仓库根目录）
        start_line: 起始行号（从 1 开始，包含），不指定则从文件开头读取
        end_line: 结束行号（包含），不指定则读取到文件末尾

    Returns:
        文件内容字符串
    """
    logger.info(f"[ToolsCall] ReadFile called: file_path={file_path}, start_line={start_line}, end_line={end_line}")

    # 加载配置
    from utils.config import Config

    allowed_dirs = get_allowed_dirs(include_repo_path=False)
    blocked_patterns = Config.get("agent.blocked_files", None)
    repo_path, search_dirs = get_repo_paths()

    logger.info(f"Repo path: {repo_path}, search dirs: {search_dirs}")

    try:
        # 尝试解析文件路径
        abs_file_path = resolve_file_path(file_path, repo_path)

        if abs_file_path is not None:
            # 安全验证
            is_allowed, error_msg = validate_file_access(abs_file_path, allowed_dirs + [repo_path], blocked_patterns)
            if not is_allowed:
                return f"[错误] {error_msg}"
            return _read_file_with_lines(abs_file_path, start_line, end_line)

        # 文件不存在，尝试搜索文件名
        file_name = os.path.basename(file_path)
        logger.info(f"File not found: {file_path}, searching for filename: {file_name} in {search_dirs}")

        matches = search_file_by_name(file_name, search_dirs)

        if not matches:
            return f"[错误] 读取文件失败: 文件不存在: {file_path} (在仓库路径 {repo_path} 中未找到)"
        elif len(matches) == 1:
            found_display_path = matches[0]
            abs_found_path = get_absolute_path_for_display_path(found_display_path, repo_path)
            if abs_found_path is None:
                return f"[错误] 找到文件但无法访问: {found_display_path}"

            logger.info(f"Found single match: {abs_found_path}")
            # 验证找到的文件路径
            is_allowed, error_msg = validate_file_access(abs_found_path, allowed_dirs + [repo_path], blocked_patterns)
            if not is_allowed:
                return f"[错误] {error_msg}"
            return _read_file_with_lines(abs_found_path, start_line, end_line)
        else:
            # 多个匹配
            logger.info(f"Found multiple matches: {matches}")
            result = "存在多个同名文件，请传入相对于仓库根目录的完整路径！\n\n找到的文件:\n"
            for i, match in enumerate(matches, 1):
                result += f"{i}. {match}\n"
            return truncate_tool_output(result, "ReadFile")

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"[错误] 读取文件失败: {str(e)}"
