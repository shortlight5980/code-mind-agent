"""
SearchCode 工具

使用 LangChain @tool 装饰器定义，用于在代码库中搜索关键词或正则表达式。
"""
import os
import re
from typing import List
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import is_path_allowed, normalize_path

logger = get_logger("agent.tools.search_code")


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


@tool
def SearchCode(query: str, is_regex: bool = False, search_dir: str = ".") -> str:
    """
    在代码库中搜索关键词或正则表达式。

    Args:
        query: 搜索关键词或正则表达式
        is_regex: 是否使用正则表达式搜索，默认为 False
        search_dir: 搜索目录，默认为当前目录 "."

    Returns:
        搜索结果字符串
    """
    from utils.config import Config

    logger.info(f"SearchCode called: query={query}, is_regex={is_regex}, search_dir={search_dir}")

    # 加载配置
    allowed_dirs = Config.get("agent.allowed_dirs", ["."])
    max_results = Config.get("agent.max_search_results", 50)

    # 安全验证：搜索目录必须在白名单内
    if not is_path_allowed(search_dir, allowed_dirs):
        return f"[错误] 搜索目录不在允许的白名单内: {search_dir}"

    abs_search_dir = normalize_path(search_dir)

    if not os.path.exists(abs_search_dir):
        return f"[错误] 搜索目录不存在: {search_dir}"

    if not os.path.isdir(abs_search_dir):
        return f"[错误] 不是目录: {search_dir}"

    try:
        # 编译正则表达式
        if is_regex:
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error as e:
                return f"[错误] 正则表达式语法错误: {str(e)}"
        else:
            # 普通关键词搜索，转义特殊字符
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        results: List[str] = []
        match_count = 0

        # 遍历目录
        for root, dirs, files in os.walk(abs_search_dir):
            # 过滤掉需要忽略的目录
            dirs[:] = [d for d in dirs if not should_ignore_dir(d)]

            for file_name in files:
                if should_ignore_file(file_name):
                    continue

                file_path = os.path.join(root, file_name)

                # 再次验证文件路径安全
                if not is_path_allowed(file_path, allowed_dirs):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                    # 在文件中搜索
                    file_matches = []
                    for line_num, line in enumerate(lines, 1):
                        if pattern.search(line):
                            # 找到匹配，截取上下文
                            snippet = line.rstrip('\n')
                            file_matches.append(f"    行 {line_num}: {snippet}")
                            match_count += 1

                    if file_matches:
                        # 显示相对路径
                        rel_path = os.path.relpath(file_path, abs_search_dir)
                        results.append(f"📄 {rel_path}")
                        results.extend(file_matches)
                        results.append("")

                    # 检查是否超过结果限制
                    if len(results) >= max_results * 3:  # 每个文件可能有多行结果
                        results.append(f"... (结果数量已达上限，仅显示前 {max_results} 个匹配)")
                        break

                except UnicodeDecodeError:
                    # 跳过非文本文件
                    continue
                except Exception as e:
                    logger.debug(f"Error searching file {file_path}: {e}")
                    continue

            if len(results) >= max_results * 3:
                break

        # 构建返回结果
        if not results:
            return f"未找到匹配内容: {query}"

        header = f"搜索结果 (共 {match_count} 个匹配):\n" + "=" * 80 + "\n"
        logger.info("[ToolsCall] " + header)
        logger.debug("\n".join(results))
        return header + "\n".join(results)

    except Exception as e:
        logger.error(f"Error in SearchCode: {e}")
        return f"[错误] 搜索失败: {str(e)}"


