import os
import re
import ast
import argparse
import sys
import fnmatch

# 将父目录添加到utils导入路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

from utils.logger import get_logger
from utils.config import Config

logger = get_logger("indexer")


def extract_python_classes_and_functions(content: str, max_class_length: int = 3000):
    """
    提取 Python 代码块，保留“类优先”的切分策略。

    AST 只负责识别类、函数、方法等结构边界；真正切块时使用源码行号回到原文，
    避免格式、注释和装饰器在重新拼装时丢失。只有源码无法被 AST 解析时，才回退
    到旧的缩进扫描逻辑。
    """
    lines = content.split('\n')

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _fallback_extract_python_classes_and_functions(content, max_class_length)

    blocks = []
    top_level_nodes = [
        node for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    top_level_nodes.sort(key=_node_start_lineno)

    next_line = 1
    for node in top_level_nodes:
        start_line = _node_start_lineno(node)
        end_line = _node_end_lineno(node)

        # 顶层结构之间的 import、常量、注释等普通内容独立成块。
        _append_source_block(blocks, lines, next_line, start_line - 1)

        if isinstance(node, ast.ClassDef):
            class_block = _source_block(lines, start_line, end_line)
            if len(class_block) <= max_class_length:
                blocks.append(class_block)
            else:
                blocks.extend(_split_class_by_ast_methods(lines, node))
        else:
            blocks.append(_source_block(lines, start_line, end_line))

        next_line = end_line + 1

    _append_source_block(blocks, lines, next_line, len(lines))
    return blocks


def _node_start_lineno(node: ast.AST) -> int:
    """返回节点在源码中的真实起始行，装饰器优先于 def/class 行。"""
    lineno = getattr(node, "lineno", 1)
    decorators = getattr(node, "decorator_list", None) or []
    if decorators:
        return min(getattr(decorator, "lineno", lineno) for decorator in decorators)
    return lineno


def _node_end_lineno(node: ast.AST) -> int:
    """返回节点结束行；正常 AST 都有 end_lineno，这里保留兜底以兼容异常节点。"""
    end_lineno = getattr(node, "end_lineno", None)
    if end_lineno is not None:
        return end_lineno

    child_lines = [
        _node_end_lineno(child)
        for child in ast.iter_child_nodes(node)
        if hasattr(child, "lineno")
    ]
    return max([getattr(node, "lineno", 1), *child_lines])


def _source_block(lines: list[str], start_line: int, end_line: int) -> str:
    """按 1-based、闭区间行号从原文切出代码块。"""
    block_lines = lines[start_line - 1:end_line]

    # 边界空行只用于分隔结构，不放进索引块；块内部的原文保持不变。
    while block_lines and not block_lines[0].strip():
        block_lines = block_lines[1:]
    while block_lines and not block_lines[-1].strip():
        block_lines = block_lines[:-1]

    return '\n'.join(block_lines)


def _append_source_block(blocks: list[str], lines: list[str], start_line: int, end_line: int):
    """切出普通源码片段，过滤纯空白块。"""
    if start_line > end_line:
        return

    block = _source_block(lines, start_line, end_line)
    if block.strip():
        blocks.append(block)


def _split_class_by_ast_methods(lines: list[str], class_node: ast.ClassDef):
    """
    对超长类按 AST 识别到的“直属方法”拆分。

    这里不会递归拆嵌套类的方法：嵌套类属于外层类的非方法区域，会按原文保留，
    避免把内部类方法误判成外层类方法。
    """
    blocks = []
    class_start = _node_start_lineno(class_node)
    class_end = _node_end_lineno(class_node)
    method_nodes = [
        node for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    method_nodes.sort(key=_node_start_lineno)

    if not method_nodes:
        return [_source_block(lines, class_start, class_end)]

    next_line = class_start
    for method_node in method_nodes:
        method_start = _node_start_lineno(method_node)
        method_end = _node_end_lineno(method_node)

        # 方法之间的类头、类变量、嵌套类等内容按原文保留为上下文块。
        _append_source_block(blocks, lines, next_line, method_start - 1)
        _append_source_block(blocks, lines, method_start, method_end)
        next_line = method_end + 1

    _append_source_block(blocks, lines, next_line, class_end)
    return blocks


def _fallback_extract_python_classes_and_functions(content: str, max_class_length: int = 3000):
    """AST 解析失败时使用的旧式缩进扫描逻辑，只作为 fallback。"""
    blocks = []
    lines = content.split('\n')
    n = len(lines)

    class_pattern = re.compile(r'^(\s*)class\s+\w+')
    def_pattern = re.compile(r'^(\s*)def\s+\w+')

    def get_indent(line: str) -> int | None:
        stripped = line.strip()
        if not stripped:
            return None
        return len(line) - len(stripped)

    def append_block(start: int, end: int):
        block = '\n'.join(lines[start:end])
        if block.strip():
            blocks.append(block)

    def find_indented_block_end(start: int, base_indent: int) -> int:
        i = start + 1
        while i < n:
            curr_indent = get_indent(lines[i])
            if curr_indent is not None and curr_indent <= base_indent:
                break
            i += 1
        return i

    def find_top_level_function_end(start: int) -> int:
        i = start + 1
        while i < n:
            curr_indent = get_indent(lines[i])
            if curr_indent == 0:
                break
            i += 1
        return i

    i = 0
    while i < n:
        line = lines[i]

        class_match = class_pattern.match(line)
        if class_match:
            class_indent_text = class_match.group(1)
            class_end = find_indented_block_end(i, len(class_indent_text))
            class_content = '\n'.join(lines[i:class_end])

            if len(class_content) <= max_class_length:
                append_block(i, class_end)
            else:
                blocks.extend(_fallback_split_class_by_methods(class_content, class_indent_text))

            i = class_end
            continue

        def_match = def_pattern.match(line)
        if def_match and len(def_match.group(1)) == 0:
            func_end = find_top_level_function_end(i)
            append_block(i, func_end)
            i = func_end
            continue

        other_start = i
        i += 1

        while i < n:
            curr_line = lines[i]
            if class_pattern.match(curr_line):
                break

            curr_def = def_pattern.match(curr_line)
            if curr_def and len(curr_def.group(1)) == 0:
                break

            i += 1

        append_block(other_start, i)

    return blocks


def _fallback_split_class_by_methods(class_content: str, class_indent: str):
    """语法错误 fallback 下使用的旧式方法扫描。"""
    lines = class_content.split('\n')
    if not lines:
        return []

    blocks = []
    n = len(lines)
    max_iterations = n * 2

    i = 0
    while i < n and max_iterations > 0:
        max_iterations -= 1
        line = lines[i]
        stripped = line.strip()
        if stripped:
            curr_indent = len(line) - len(stripped)
            if curr_indent > len(class_indent) and stripped.startswith('def '):
                break
        i += 1

    class_header = '\n'.join(lines[:i])
    if class_header.strip():
        blocks.append(class_header)

    while i < n and max_iterations > 0:
        max_iterations -= 1
        line = lines[i]
        stripped = line.strip()

        if stripped and stripped.startswith('def '):
            method_indent_len = len(line) - len(stripped)
            method_start = i
            i += 1

            while i < n and max_iterations > 0:
                max_iterations -= 1
                curr_line = lines[i]
                curr_stripped = curr_line.strip()
                if curr_stripped:
                    curr_indent = len(curr_line) - len(curr_stripped)
                    if curr_indent <= method_indent_len:
                        break
                i += 1

            method_content = '\n'.join(lines[method_start:i])
            if method_content.strip():
                blocks.append(method_content)
        else:
            i += 1

    if max_iterations <= 0:
        logger.warning("Reached max iterations in _fallback_split_class_by_methods")

    return blocks


def split_by_code_blocks(content: str, file_ext: str, max_class_length: int = 3000):
    """
    根据智能边界分割代码。

    对于 Python：使用特殊的类感知分割策略
    对于其他语言：回退到简单的模式分割
    """
    if file_ext == '.py':
        return extract_python_classes_and_functions(content, max_class_length)

    # 针对其他语言的简单基于模式的分割策略
    # 定义不同编程语言的代码块分割正则表达式模式
    # 使用正向先行断言 (?=...) 在匹配换行符的同时，确保后续内容符合特定语法结构的开头
    patterns = {
        # Java: 类、接口及主要访问修饰符
        ".java": r"\n(?=public |private |protected |class |interface )",
        # JavaScript: 函数、类及变量声明
        ".js": r"\n(?=function |class |const |let |var )",
        # TypeScript: 函数、类、接口及导出语句
        ".ts": r"\n(?=function |class |interface |export )",
        # Go: 函数、类型及结构体定义
        ".go": r"\n(?=func |type |struct )",
    }
    pattern = patterns.get(file_ext)
    if pattern:
        return re.split(pattern, content)
    else:
        return [content]


def index_repo(repo_path: str = None, persist_dir: str = None):
    """
    索引代码库到矢量数据库。

    Args:
        repo_path: 仓库路径，如果不指定则从 config.yml 的 repo.path 读取
        persist_dir: 向量数据库保存目录，如果不指定则从配置读取
    """
    Config.load()

    if repo_path is None:
        repo_path = Config.get("repo.path", ".")

    if persist_dir is None:
        persist_dir = Config.get("chroma.persist_dir", "../chroma_db")

    chunk_size = Config.get("chroma.chunk_size", 800)
    chunk_overlap = Config.get("chroma.chunk_overlap", 100)
    max_class_length = Config.get("splitting.max_class_length", 3000)
    embedding_model = Config.get("embeddings.model", "text-embedding-v4")

    all_chunks = []
    supported_exts = ('.py', '.java', '.js', '.ts', '.go', '.md', '.txt')

    # Directories to exclude
    exclude_dirs = {
        'node_modules', '__pycache__', '.git', '.svn', '.hg',
        'dist', 'build', 'target', 'venv', '.venv', 'env',
        'vendor', 'bower_components', 'chroma_db', 'logs',
        '.idea', '.pytest_cache'
    }

    # Files to exclude (exact names or patterns)
    exclude_files = {
        'package-lock.json', 'yarn.lock', 'poetry.lock', 'Pipfile.lock',
        'composer.lock', 'Gemfile.lock', 'Podfile.lock',
        '.env',
    }
    
    # File extensions/patterns to exclude
    exclude_file_patterns = [
        '*.iml', '*.log', '*.db', '*.sqlite', '*.sqlite3',
        '*.pdf', '*.doc', '*.docx', '*.xls', '*.xlsx',
        '*.ppt', '*.pptx', '*.zip', '*.rar', '*.7z',
        '*.tar', '*.gz', '*.bz2', '.env.*', '*.log'
    ]

    def should_exclude_file(filename: str) -> bool:
        """检查是否应该根据名称或模式排除文件"""
        if filename in exclude_files:
            return True

        for pattern in exclude_file_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False

    logger.info(f"Starting repository scan: {repo_path}")

    for root, _, files in os.walk(repo_path):
        # Skip excluded directories
        path_parts = root.replace('\\', '/').split('/')
        if any(part in exclude_dirs for part in path_parts):
            continue

        for file in files:
            file_path = os.path.join(root, file).replace('\\', '/')
            logger.info(f"Processing file: {file_path}")

            if file.endswith(supported_exts):
                try:
                    loader = TextLoader(file_path, encoding='utf-8')
                    docs = loader.load()

                    # 根据代码边界进行智能分割
                    for doc in docs:
                        ext = os.path.splitext(file)[1]
                        blocks = split_by_code_blocks(doc.page_content, ext, max_class_length)
                        for block in blocks:
                            if block.strip():
                                # TODO: 代码文件不继续拆分
                                # 具有上下文重叠的细粒度拆分
                                splitter = RecursiveCharacterTextSplitter(
                                    chunk_size=chunk_size,
                                    chunk_overlap=chunk_overlap
                                )
                                chunks = splitter.create_documents(
                                    [block],
                                    metadatas=[{"source": file_path}]
                                )
                                all_chunks.extend(chunks)
                except Exception as e:
                    logger.warning(f"Skipping file {file_path}: {e}")

            else:
                # 非支持的代码类型，按照文本处理
                if should_exclude_file(file):
                    logger.info(f"Skip file {file_path}")
                    continue

                try:
                    loader = TextLoader(file_path, encoding='utf-8')
                    docs = loader.load()

                    for doc in docs:
                        splitter = RecursiveCharacterTextSplitter(
                            chunk_size=chunk_size,
                            chunk_overlap=chunk_overlap
                        )
                        chunks = splitter.create_documents(
                            [doc.page_content],
                            metadatas=[{"source": file_path}]
                        )
                        all_chunks.extend(chunks)

                except Exception as e:
                    logger.warning(f"Skipping file {file_path}: {e}")

    if not all_chunks:
        logger.error("No indexable code files found")
        return

    logger.info(f"Total {len(all_chunks)} code chunks, starting vectorization...")

    api_key = Config.get_env("DASHSCOPE_API_KEY")
    if not api_key:
        logger.error("DASHSCOPE_API_KEY not found in environment variables")
        return

    embeddings = DashScopeEmbeddings(
        model=embedding_model,
    )

    vectordb = Chroma.from_documents(
        all_chunks,
        embeddings,
        persist_directory=persist_dir
    )

    logger.info(f"Indexing complete! {len(all_chunks)} chunks saved to {persist_dir}")


if __name__ == "__main__":
    # 创建命令行参数解析器，用于处理用户输入的参数
    parser = argparse.ArgumentParser(description="Index Git repository to vector database")
    
    # 添加位置参数 'repo_path'，用于指定要索引的仓库路径
    # nargs="?" 表示该参数是可选的，如果未提供，则默认为 None
    # 在 index_repo 函数中，如果为 None，将从 config.yml 中读取默认值
    parser.add_argument(
        "repo_path", 
        nargs="?", 
        help="Repository path to index (optional, defaults to repo.path in config.yml)"
    )
    
    # 添加可选参数 '--persist-dir'，用于指定向量数据库的保存目录
    # 如果未提供，将使用配置文件中的默认值
    parser.add_argument(
        "--persist-dir", 
        help="Vector database save directory"
    )
    
    # 解析命令行参数
    args = parser.parse_args()

    # 调用索引函数，传入解析后的仓库路径和持久化目录
    # 如果参数为 None，index_repo 内部会从配置文件中加载默认值
    index_repo(args.repo_path, args.persist_dir)
