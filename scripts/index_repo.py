import os
import re
import ast
import argparse
import sys
import fnmatch
from abc import ABC, abstractmethod

try:
    import tree_sitter_languages as tslang
    from tree_sitter import Parser
except ImportError:
    tslang = None
    Parser = None

# 将父目录添加到utils导入路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

from utils.logger import get_logger
from utils.config import Config

logger = get_logger("indexer")

supported_exts = ('.py', '.java', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs', '.c', '.cpp', '.md', '.txt')

LANGUAGE_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.go': 'go',
    '.rs': 'rust',
    '.java': 'java',
    '.c': 'c',
    '.cpp': 'cpp',
}

CLASS_CHUNK_TYPES = {
    'javascript': ['class_declaration'],
    'typescript': ['class_declaration'],
    'tsx': ['class_declaration'],
    'rust': ['impl_item', 'struct_item'],
    'java': ['class_declaration'],
    'cpp': ['class_specifier'],
}

FUNCTION_CHUNK_TYPES = {
    'javascript': ['function_declaration', 'generator_function_declaration', 'arrow_function', 'method_definition'],
    'typescript': ['function_declaration', 'generator_function_declaration', 'arrow_function', 'method_definition'],
    'tsx': ['function_declaration', 'generator_function_declaration', 'arrow_function', 'method_definition'],
    'go': ['function_declaration', 'method_declaration'],
    'rust': ['function_item'],
    'java': ['method_declaration'],
    'c': ['function_definition'],
    'cpp': ['function_definition'],
}

# Directories to exclude
exclude_dirs = {
    # 版本控制系统目录
    '.git', '.svn', '.hg', '.bzr', '_darcs', 'CVS',

    # Python 相关
    '__pycache__', '.pytest_cache', '.mypy_cache', '.tox', '.nox',
    'venv', '.venv', 'env', '.env', 'virtualenv',
    '*.egg-info', '.eggs', 'dist', 'build', 'eggs',

    # Node.js / JavaScript 相关
    'node_modules', 'bower_components', 'npm-debug.log*', 'yarn-debug.log*', 'yarn-error.log*',
    '.npm', '.yarn-integrity', '.parcel-cache',

    # Java / JVM 相关
    'target', 'bin', 'out', '.gradle', 'build', '.idea', '.classpath', '.project', '.settings',

    # Go 相关
    'vendor',

    # Rust 相关
    'target',

    # C/C++ 相关
    'Debug', 'Release', 'x64', 'x86', 'ipch', '.vs',

    # IDE 和编辑器配置/临时目录
    '.idea', '.vscode', '.eclipse', '.metadata', '.repl_history',
    '*.swp', '*.swo', '*~', '#*#', '.DS_Store', 'Thumbs.db',

    # 数据库和缓存
    'chroma_db', 'logs', 'log', 'tmp', 'temp', '.cache',

    # 其他常见构建/依赖目录
    'packages', '.next', 'nuxt', '.nuxt', '.output',
    '.terraform', '.serverless',

    # .understand-anything
    '.understand-anything'
}

# Files to exclude (exact names or patterns)
exclude_files = {
    # 依赖锁定文件 (Dependency Lock Files)
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'poetry.lock', 'Pipfile.lock', 'requirements.txt',
    'composer.lock', 'Gemfile.lock', 'Podfile.lock', 'Cartfile.resolved',
    'go.sum', 'Cargo.lock', 'mix.lock',

    # 环境与配置文件 (Environment & Config Files)
    '.env', '.env.local', '.env.production', '.env.development',
    '.gitignore', '.dockerignore', '.npmignore',

    # 项目元数据与配置 (Project Metadata & Config)
    'tsconfig.json', 'jsconfig.json', 'webpack.config.js',
    'vite.config.ts', 'babel.config.js', '.eslintrc.json',
    '.prettierrc', 'Makefile', 'Dockerfile', 'docker-compose.yml',

    # 文档与说明 (Documentation)
    'LICENSE', 'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md',
    'CODE_OF_CONDUCT.md', 'SECURITY.md',
}

# File extensions/patterns to exclude
exclude_file_patterns = {
    # IDE 和编辑器配置/临时文件
    '*.iml', '.idea/*', '.vscode/*', '*.swp', '*.swo', '*~', '#*#',

    # 日志和数据库文件
    '*.log', '*.db', '*.sqlite', '*.sqlite3',

    # 文档和办公文件
    '*.pdf', '*.doc', '*.docx', '*.xls', '*.xlsx', '*.ppt', '*.pptx', '*.csv', '*.tsv',

    # 压缩和归档文件
    '*.zip', '*.rar', '*.7z', '*.tar', '*.gz', '*.bz2', '*.iso', '*.dmg', '*.pkg', '*.deb', '*.rpm', '*.whl', '*.egg',

    # 环境变量和敏感信息
    '.env.*', '*.key', '*.pem', '*.crt', '*.cer', '*.pfx', '*.p12',

    # 图片和多媒体文件
    '*.jpg', '*.png', '*.svg', '*.gif', '*.bmp', '*.ico', '*.tiff', '*.webp',
    '*.mp3', '*.mp4', '*.avi', '*.mov', '*.wmv', '*.flv', '*.wav', '*.aac',

    # 可执行文件和二进制库
    '*.exe', '*.dll', '*.so', '*.dylib', '*.bin', '*.o', '*.obj', '*.node',

    # Python 编译文件和包
    '*.pyc', '*.pyo', '*.pyd', '__pycache__/*', '*.egg-info/*', '*.coverage',

    # Java/JVM 编译文件和包
    '*.class', '*.jar', '*.war', '*.ear',

    # 数据科学和机器学习模型/数据
    '*.npy', '*.npz', '*.pickle', '*.pkl', '*.model', '*.h5', '*.pb', '*.onnx', '*.pt', '*.pth', '*.ckpt',
    '*.parquet', '*.avro', '*.orc',

    # 字体文件
    '*.woff', '*.woff2', '*.ttf', '*.eot', '*.otf',

    # 系统隐藏文件和锁文件
    '*.DS_Store', 'Thumbs.db', '*.lock', '*.pid', '*.sock',

    # 网络抓包和转储文件
    '*.pcap', '*.dump'
}

def should_exclude_file(filename: str) -> bool:
    """检查是否应该根据名称或模式排除文件"""
    if filename in exclude_files:
        return True

    for pattern in exclude_file_patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False


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


class CodeSplitter(ABC):
    """Unified interface for code chunking strategies."""

    @abstractmethod
    def split(self, content: str, max_class_length: int = 3000) -> list[str]:
        pass


class PythonCodeSplitter(CodeSplitter):
    def split(self, content: str, max_class_length: int = 3000) -> list[str]:
        return extract_python_classes_and_functions(content, max_class_length)


class TreeSitterCodeSplitter(CodeSplitter):
    def __init__(self, language_name: str, fallback_splitter: CodeSplitter | None = None):
        self.language_name = language_name
        self.fallback_splitter = fallback_splitter or RegexCodeSplitter("")

    def split(self, content: str, max_class_length: int = 3000) -> list[str]:
        if tslang is None:
            logger.warning("tree_sitter_languages is not installed; falling back to regex code splitter")
            return self.fallback_splitter.split(content, max_class_length)

        class_types = set(CLASS_CHUNK_TYPES.get(self.language_name, []))
        function_types = set(FUNCTION_CHUNK_TYPES.get(self.language_name, []))
        if not class_types and not function_types:
            return self.fallback_splitter.split(content, max_class_length)

        try:
            parser = self._build_parser()
            tree = parser.parse(content.encode('utf-8'))
        except Exception as exc:
            logger.warning(f"Tree-sitter parsing failed for {self.language_name}: {exc}")
            return self.fallback_splitter.split(content, max_class_length)

        chunks = self._extract_priority_chunks(
            content,
            tree.root_node,
            class_types,
            function_types,
            max_class_length,
        )
        return chunks or self.fallback_splitter.split(content, max_class_length)

    def _build_parser(self):
        language = tslang.get_language(self.language_name)

        try:
            return tslang.Parser(language)
        except AttributeError:
            parser = Parser()
            parser.set_language(language)
            return parser

    def _expand_chunk_to_statement(self, content: str, node) -> str:
        _, _, chunk = self._expanded_chunk(content, node)
        return chunk

    def _expanded_chunk(self, content: str, node) -> tuple[int, int, str]:
        start_byte = node.start_byte
        end_byte = node.end_byte
        parent = node.parent

        while parent is not None and parent.type in {
            'variable_declarator',
            'lexical_declaration',
            'variable_declaration',
            'export_statement',
        }:
            start_byte = min(start_byte, parent.start_byte)
            end_byte = max(end_byte, parent.end_byte)
            parent = parent.parent

        return start_byte, end_byte, content[start_byte:end_byte].strip()

    def _extract_priority_chunks(
        self,
        content: str,
        root,
        class_types: set[str],
        function_types: set[str],
        max_class_length: int,
    ) -> list[str]:
        class_nodes = []
        if class_types:
            self._collect_nodes(root, class_types, class_nodes)

        primary_chunks = []
        covered_ranges = []
        for node in class_nodes:
            class_chunk = self._expand_chunk_to_statement(content, node)
            if not class_chunk.strip():
                continue

            covered_ranges.append((node.start_byte, node.end_byte))
            if len(class_chunk) <= max_class_length:
                primary_chunks.append((node.start_byte, node.end_byte, class_chunk))
            else:
                method_chunks = self._split_container_by_functions(
                    content,
                    node,
                    function_types,
                )
                primary_chunks.extend(method_chunks or [(node.start_byte, node.end_byte, class_chunk)])

        occupied_ranges = covered_ranges + [(start, end) for start, end, _ in primary_chunks]

        function_nodes = []
        if function_types:
            self._collect_nodes(root, function_types, function_nodes)

        for node in function_nodes:
            if self._is_inside_any_range(node, occupied_ranges):
                continue

            start_byte, end_byte, chunk = self._expanded_chunk(content, node)
            if chunk.strip():
                primary_chunks.append((start_byte, end_byte, chunk))

        return self._merge_primary_chunks_with_fragments(content, primary_chunks, covered_ranges)

    def _collect_nodes(self, node, target_types: set[str], results: list):
        if node.type in target_types:
            results.append(node)
            return

        for child in node.children:
            self._collect_nodes(child, target_types, results)

    def _split_container_by_functions(
        self,
        content: str,
        container_node,
        function_types: set[str],
    ) -> list[tuple[int, int, str]]:
        if not function_types:
            return []

        method_nodes = []
        for child in container_node.children:
            self._collect_direct_function_nodes(child, function_types, method_nodes)

        chunks = []
        for node in method_nodes:
            start_byte, end_byte, chunk = self._expanded_chunk(content, node)
            if chunk.strip():
                chunks.append((start_byte, end_byte, chunk))
        return chunks

    def _collect_direct_function_nodes(self, node, function_types: set[str], results: list):
        if node.type in function_types:
            results.append(node)
            return

        for child in node.children:
            if child.type in CLASS_CHUNK_TYPES.get(self.language_name, []):
                continue
            self._collect_direct_function_nodes(child, function_types, results)

    def _is_inside_any_range(self, node, ranges: list[tuple[int, int]]) -> bool:
        return any(start <= node.start_byte and node.end_byte <= end for start, end in ranges)

    def _merge_primary_chunks_with_fragments(
        self,
        content: str,
        primary_chunks: list[tuple[int, int, str]],
        covered_ranges: list[tuple[int, int]],
    ) -> list[str]:
        sorted_chunks = sorted(primary_chunks, key=lambda item: (item[0], item[1]))
        sorted_covered_ranges = sorted(covered_ranges)
        merged = []
        cursor = 0

        for start_byte, end_byte, chunk in sorted_chunks:
            if start_byte < cursor:
                continue

            fragment_start = self._skip_covered_ranges(cursor, start_byte, sorted_covered_ranges, merged, content)
            self._append_fragment(merged, content[fragment_start:start_byte])
            if chunk.strip():
                merged.append(chunk)
            cursor = max(cursor, end_byte)

        fragment_start = self._skip_covered_ranges(cursor, len(content), sorted_covered_ranges, merged, content)
        self._append_fragment(merged, content[fragment_start:])
        return merged

    def _append_fragment(self, chunks: list[str], fragment: str):
        cleaned = fragment.strip()
        if cleaned and re.search(r"\w", cleaned):
            chunks.append(cleaned)

    def _skip_covered_ranges(
        self,
        start: int,
        end: int,
        covered_ranges: list[tuple[int, int]],
        chunks: list[str],
        content: str,
    ) -> int:
        cursor = start
        for covered_start, covered_end in covered_ranges:
            if covered_end <= cursor:
                continue
            if covered_start >= end:
                break
            if cursor < covered_start:
                self._append_fragment(chunks, content[cursor:min(covered_start, end)])
            cursor = max(cursor, covered_end)
            if cursor >= end:
                break
        return cursor


class RegexCodeSplitter(CodeSplitter):
    def __init__(self, file_ext: str):
        self.file_ext = file_ext

    def split(self, content: str, max_class_length: int = 3000) -> list[str]:
        patterns = {
            ".java": r"\n(?=public |private |protected |class |interface )",
            ".js": r"\n(?=function |class |const |let |var |export )",
            ".jsx": r"\n(?=function |class |const |let |var |export )",
            ".ts": r"\n(?=function |class |interface |export |const |let |var )",
            ".tsx": r"\n(?=function |class |interface |export |const |let |var )",
            ".go": r"\n(?=func |type |struct )",
            ".rs": r"\n(?=fn |impl |struct |enum |trait )",
            ".c": r"\n(?=[A-Za-z_][\\w\\s\\*]*\\s+[A-Za-z_]\\w*\\s*\\()",
            ".cpp": r"\n(?=class |struct |[A-Za-z_:][\\w:\\s\\*<>~]*\\s+[A-Za-z_:~]\\w*\\s*\\()",
        }
        pattern = patterns.get(self.file_ext)
        if pattern:
            blocks = re.split(pattern, content)
            return [
                block.strip()
                for block in blocks
                if self._is_indexable_block(block)
            ]

        return [content] if content.strip() else []

    def _is_indexable_block(self, block: str) -> bool:
        stripped = block.strip()
        if not stripped:
            return False

        indexable_prefixes = {
            ".java": ("public ", "private ", "protected ", "class ", "interface "),
            ".js": ("function ", "class ", "const ", "let ", "var ", "export "),
            ".jsx": ("function ", "class ", "const ", "let ", "var ", "export "),
            ".ts": ("function ", "class ", "interface ", "export ", "const ", "let ", "var "),
            ".tsx": ("function ", "class ", "interface ", "export ", "const ", "let ", "var "),
            ".go": ("func ", "type ", "struct "),
            ".rs": ("fn ", "impl ", "struct ", "enum ", "trait "),
            ".c": tuple(),
            ".cpp": ("class ", "struct "),
        }
        prefixes = indexable_prefixes.get(self.file_ext)
        if prefixes is None:
            return True
        if prefixes and stripped.startswith(prefixes):
            return True

        return self.file_ext in {".c", ".cpp"} and bool(re.match(
            r"^[A-Za-z_:][\w:\s\*<>~]*\s+[A-Za-z_:~]\w*\s*\(",
            stripped,
        ))


def get_language_for_file(filename: str) -> str | None:
    ext = os.path.splitext(filename)[-1].lower()
    return LANGUAGE_MAP.get(ext)


def get_code_splitter(file_ext: str) -> CodeSplitter:
    normalized_ext = file_ext.lower()
    if normalized_ext == '.py':
        return PythonCodeSplitter()

    language_name = LANGUAGE_MAP.get(normalized_ext)
    fallback_splitter = RegexCodeSplitter(normalized_ext)
    if language_name:
        return TreeSitterCodeSplitter(language_name, fallback_splitter)

    return fallback_splitter

def split_by_code_blocks(content: str, file_ext: str, max_class_length: int = 3000):
    return get_code_splitter(file_ext).split(content, max_class_length)


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

    chunk_size_doc = Config.get("chroma.chunk_size.doc", 800)
    chunk_size_code = Config.get("chroma.chunk_size.code", 2000)
    chunk_overlap = Config.get("chroma.chunk_overlap", 100)
    max_class_length = Config.get("splitting.max_class_length", 3000)
    embedding_model = Config.get("embeddings.model", "text-embedding-v4")

    all_chunks = []

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
                        if not doc.page_content.strip():
                            continue
                        ext = os.path.splitext(file)[1]
                        blocks = get_code_splitter(ext).split(doc.page_content, max_class_length)
                        for block in blocks:
                            if not block.strip():
                                continue

                            splitter = RecursiveCharacterTextSplitter(
                                chunk_size=chunk_size_code,
                                chunk_overlap=chunk_overlap
                            )
                            chunks = splitter.create_documents(
                                [block],
                                metadatas=[{"source": file_path, "type": "code"}]
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
                        # 是普通文档或不支持的语言类型，使用文档切割器
                        splitter = RecursiveCharacterTextSplitter(
                            chunk_size=chunk_size_doc,
                            chunk_overlap=chunk_overlap
                        )
                        chunks = splitter.create_documents(
                            [doc.page_content.strip()],
                            metadatas=[{"source": file_path, "type": "doc"}]
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
