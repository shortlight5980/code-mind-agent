import os
import re
import argparse
import sys

# Add parent directory to path for utils import
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
    Extract Python classes and functions, keeping classes intact when possible.

    Strategy:
    1. First identify all class boundaries
    2. For each class: if length < max_class_length, keep as whole
    3. For long classes: split by method
    4. Extract standalone functions
    """
    blocks = []
    lines = content.split('\n')

    # Pattern to match class and def definitions at any indentation level
    class_pattern = re.compile(r'^(\s*)class\s+\w+')
    def_pattern = re.compile(r'^(\s*)def\s+\w+')

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Check for class definition
        class_match = class_pattern.match(line)
        if class_match:
            class_indent = class_match.group(1)
            class_start = i
            i += 1

            # Find end of class (next non-indented or EOF)
            while i < n:
                curr_line = lines[i]
                if curr_line.strip() and not curr_line.startswith(class_indent + ' ') and not curr_line.startswith(class_indent + '\t'):
                    # Check if it's not just a blank line continuation
                    if not (def_pattern.match(curr_line) and len(curr_line) - len(curr_line.lstrip()) > len(class_indent)):
                        break
                i += 1

            class_content = '\n'.join(lines[class_start:i])

            if len(class_content) <= max_class_length:
                # Keep small classes intact
                if class_content.strip():
                    blocks.append(class_content)
            else:
                # Split long class by methods
                method_blocks = _split_class_by_methods(class_content, class_indent)
                blocks.extend(method_blocks)
            continue

        # Check for standalone function
        def_match = def_pattern.match(line)
        if def_match:
            def_indent = def_match.group(1)
            # Only consider top-level functions (not inside classes)
            if len(def_indent) == 0:
                def_start = i
                i += 1

                # Find end of function
                while i < n:
                    curr_line = lines[i]
                    if curr_line.strip() and not curr_line.startswith(' ') and not curr_line.startswith('\t'):
                        break
                    i += 1

                func_content = '\n'.join(lines[def_start:i])
                if func_content.strip():
                    blocks.append(func_content)
                continue

        # Collect other code as-is until next class/function
        other_start = i
        while i < n:
            curr_line = lines[i]
            if class_pattern.match(curr_line) or def_pattern.match(curr_line):
                break
            i += 1

        other_content = '\n'.join(lines[other_start:i])
        if other_content.strip():
            blocks.append(other_content)

    return blocks


def _split_class_by_methods(class_content: str, class_indent: str):
    """Split a long class by its methods."""
    lines = class_content.split('\n')
    if not lines:
        return []

    blocks = []
    # First block: class definition up to first method
    method_pattern = re.compile(r'^' + re.escape(class_indent) + r'(\s+)def\s+\w+')

    i = 0
    n = len(lines)

    # Class signature + fields
    while i < n:
        if method_pattern.match(lines[i]):
            break
        i += 1

    class_header = '\n'.join(lines[:i])
    if class_header.strip():
        blocks.append(class_header)

    # Now split by methods
    while i < n:
        method_match = method_pattern.match(lines[i])
        if method_match:
            method_indent = class_indent + method_match.group(1)
            method_start = i
            i += 1

            while i < n:
                curr_line = lines[i]
                if curr_line.strip():
                    # Check if next line is less indented than method body
                    curr_indent = len(curr_line) - len(curr_line.lstrip())
                    method_body_indent = len(method_indent) + 4  # Assume 4-space indent
                    if curr_indent <= len(method_indent) and not method_pattern.match(curr_line):
                        break
                i += 1

            method_content = '\n'.join(lines[method_start:i])
            if method_content.strip():
                blocks.append(method_content)
        else:
            i += 1

    return blocks


def split_by_code_blocks(content: str, file_ext: str, max_class_length: int = 3000):
    """
    Split code by intelligent boundaries.

    For Python: uses special class-aware splitting
    For other languages: falls back to simple pattern splitting
    """
    if file_ext == '.py':
        return extract_python_classes_and_functions(content, max_class_length)

    # Simple pattern-based splitting for other languages
    patterns = {
        ".java": r"\n(?=public |private |protected |class |interface )",
        ".js": r"\n(?=function |class |const |let |var )",
        ".ts": r"\n(?=function |class |interface |export )",
        ".go": r"\n(?=func |type |struct )",
    }
    pattern = patterns.get(file_ext)
    if pattern:
        return re.split(pattern, content)
    else:
        return [content]


def index_repo(repo_path: str, persist_dir: str = None):
    """Index code repository into vector database."""
    Config.load()

    if persist_dir is None:
        persist_dir = Config.get("chroma.persist_dir", "./chroma_db")

    chunk_size = Config.get("chroma.chunk_size", 800)
    chunk_overlap = Config.get("chroma.chunk_overlap", 100)
    max_class_length = Config.get("splitting.max_class_length", 3000)
    embedding_model = Config.get("embeddings.model", "text-embedding-v3")

    all_chunks = []
    supported_exts = ('.py', '.java', '.js', '.ts', '.go', '.md')

    # Directories to exclude
    exclude_dirs = {
        'node_modules', '__pycache__', '.git', '.svn', '.hg',
        'dist', 'build', 'target', 'venv', '.venv', 'env', '.env',
        'vendor', 'bower_components', 'learn_docs'
    }

    logger.info(f"Starting repository scan: {repo_path}")

    for root, _, files in os.walk(repo_path):
        # Skip excluded directories
        path_parts = root.replace('\\', '/').split('/')
        if any(part in exclude_dirs for part in path_parts):
            continue

        for file in files:
            if file.endswith(supported_exts):
                file_path = os.path.join(root, file)
                logger.info(f"Processing file: {file_path}")

                try:
                    loader = TextLoader(file_path, encoding='utf-8')
                    docs = loader.load()

                    # Smart splitting by code boundaries
                    for doc in docs:
                        ext = os.path.splitext(file)[1]
                        blocks = split_by_code_blocks(doc.page_content, ext, max_class_length)
                        for block in blocks:
                            if block.strip():
                                # Fine-grained splitting with context overlap
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

    if not all_chunks:
        logger.error("No indexable code files found")
        return

    logger.info(f"Total {len(all_chunks)} code chunks, starting vectorization...")

    # Use Alibaba Bailian embedding model
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
    parser = argparse.ArgumentParser(description="Index Git repository to vector database")
    parser.add_argument("repo_path", help="Repository path to index")
    parser.add_argument("--persist-dir", help="Vector database save directory")
    args = parser.parse_args()

    index_repo(args.repo_path, args.persist_dir)
