"""
向 Chroma 和 BM25 索引中增量添加指定文件或文件夹下的文件。

脚本只负责收集用户指定路径下的可索引文件；切分和写入索引的逻辑复用
同目录 `index_repo.py` 中的 build_chunks 和 save_indexes，避免两套规则漂移。
"""
import argparse
import os
import sys

# 将项目根目录加入 import 路径，便于从 scripts 目录直接执行该脚本。
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scripts.index_repo import (
    build_chunks,
    deduplicate_chunks_by_hash,
    is_supported_code_file,
    is_supported_doc_file,
    save_indexes,
    should_exclude_dir,
    should_exclude_file,
)
from utils.config import Config
from utils.logger import get_logger

logger = get_logger("index_adder")


def normalize_source_path(path: str) -> str:
    """
    将文件路径标准化为索引 metadata.source 使用的格式。

    Args:
        path: 用户输入或扫描得到的文件路径。

    Returns:
        使用正斜杠分隔的绝对路径。
    """
    return os.path.abspath(path).replace("\\", "/")


def is_indexable_file(file_path: str) -> bool:
    """
    判断文件是否符合当前索引规则。

    Args:
        file_path: 待判断的文件路径。

    Returns:
        支持的代码文件或文档文件返回 True，否则返回 False。
    """
    filename = os.path.basename(file_path)
    if should_exclude_file(filename):
        return False
    return is_supported_code_file(filename) or is_supported_doc_file(filename)


def collect_indexable_files(source_path: str) -> list[str]:
    """
    收集指定文件或文件夹下所有可索引文件。

    Args:
        source_path: 用户指定的文件路径或文件夹路径。

    Returns:
        标准化后的可索引文件路径列表。

    Raises:
        FileNotFoundError: 当 source_path 不存在时抛出。
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"指定路径不存在: {source_path}")

    if os.path.isfile(source_path):
        return [normalize_source_path(source_path)] if is_indexable_file(source_path) else []

    target_files = []
    for root, dirs, files in os.walk(source_path):
        # 原地裁剪目录列表，避免继续扫描排除目录。
        dirs[:] = [dirname for dirname in dirs if not should_exclude_dir(dirname)]

        path_parts = root.replace("\\", "/").split("/")
        if any(should_exclude_dir(part) for part in path_parts):
            continue

        for filename in files:
            file_path = os.path.join(root, filename)
            if is_indexable_file(file_path):
                target_files.append(normalize_source_path(file_path))

    return target_files


def add_documents_by_source(source_path: str, persist_dir: str | None = None) -> int:
    """
    将指定文件或文件夹下的文件切分后写入 Chroma 和 BM25 索引。

    Args:
        source_path: 用户指定的文件路径或文件夹路径。
        persist_dir: Chroma 持久化目录；为空时读取 config.yml。

    Returns:
        成功生成并参与写入流程的分块数量。
    """
    Config.load()

    if persist_dir is None:
        persist_dir = Config.get("chroma.persist_dir", "./chroma_db")
    bm25_persist_path = Config.get("bm25.persist_path", "./bm25_index/index.pkl")
    embedding_model = Config.get("embeddings.model", "text-embedding-v4")

    logger.info(f"开始收集路径: {source_path}")
    file_paths = collect_indexable_files(source_path)
    if not file_paths:
        logger.warning(f"未找到可索引文件: {source_path}")
        return 0

    logger.info(f"找到 {len(file_paths)} 个可索引文件")
    chunks = deduplicate_chunks_by_hash(build_chunks(file_paths))
    if not chunks:
        logger.warning(f"未生成可索引分块: {source_path}")
        return 0

    return save_indexes(chunks, persist_dir, embedding_model, bm25_persist_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="向 Chroma 和 BM25 索引中添加指定文件或文件夹下的文件"
    )
    parser.add_argument(
        "source_path",
        type=str,
        help="待添加到索引的文件路径或文件夹路径",
    )
    parser.add_argument(
        "--persist-dir",
        help="Chroma 向量库持久化目录；默认读取 config.yml 中的 chroma.persist_dir",
    )

    args = parser.parse_args()

    try:
        added_count = add_documents_by_source(args.source_path, args.persist_dir)
        print(f"\n索引追加完成，新增分块数: {added_count}")
    except Exception as exc:
        logger.error(f"索引追加失败: {exc}", exc_info=True)
        print(f"\n索引追加失败: {exc}")
