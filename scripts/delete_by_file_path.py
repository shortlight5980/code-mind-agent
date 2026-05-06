"""
删除 Chroma 数据库中指定源文件的文档
"""
import sys
import os
import argparse

# 将父目录添加到导入路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from utils.config import Config
from utils.logger import get_logger

Config.load()
embedding_model = Config.get("embeddings.model", "text-embedding-v4")
embeddings = DashScopeEmbeddings(model=embedding_model)

logger = get_logger("chroma_deleter")


def delete_documents_by_source(source_path: str):
    """
    删除指定源文件的所有文档

    Args:
        source_path: 文件路径（需要与存储时的 metadata 中的 source 字段匹配）
    """
    Config.load()

    persist_dir = Config.get("chroma.persist_dir", "./chroma_db")
    embedding_model = Config.get("embeddings.model", "text-embedding-v4")

    logger.info(f"加载向量数据库: {persist_dir}")
    logger.info(f"目标源文件: {source_path}")

    # 初始化 embeddings
    embeddings = DashScopeEmbeddings(model=embedding_model)

    # 加载向量数据库
    vectordb = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )

    # 查询该源文件的所有文档
    logger.info("正在查询匹配的文档...")
    results = vectordb.get(where={"source": source_path})

    if not results['ids']:
        logger.warning(f"未找到源文件 {source_path} 的文档")
        return

    doc_count = len(results['ids'])
    logger.info(f"找到 {doc_count} 个文档")

    # 显示文档 ID 列表（用于确认）
    for i, doc_id in enumerate(results['ids'], 1):
        logger.info(f"  [{i}] ID: {doc_id}")

    # 执行删除
    logger.info(f"开始删除 {doc_count} 个文档...")
    vectordb.delete(ids=results['ids'])

    logger.info(f"✓ 成功删除 {doc_count} 个文档")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="删除 Chroma 数据库中指定源文件的文档")
    parser.add_argument(
        "source_path",
        type=str,
        help="要删除的源文件路径（需与 metadata 中的 source 字段完全匹配）"
    )

    args = parser.parse_args()

    try:
        delete_documents_by_source(args.source_path)
    except Exception as e:
        logger.error(f"删除失败: {e}", exc_info=True)
        print(f"\n删除失败: {e}")

