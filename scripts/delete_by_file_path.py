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
from utils.bm25_index import BM25Index

logger = get_logger("chroma_deleter")


def _normalize_source_path(path: str) -> str:
    """
    标准化文件路径：转换为绝对路径并统一使用正斜杠 '/'。
    
    Args:
        path: 原始文件路径
        
    Returns:
        标准化后的文件路径
    """
    return os.path.abspath(path).replace('\\', '/')


def _collect_target_sources(source_path: str) -> list[str]:
    """
    收集需要处理的目标源文件路径列表。
    
    如果输入是文件，返回包含该文件标准化路径的列表；
    如果输入是目录，递归遍历目录下所有文件，返回所有文件的标准化路径列表。
    
    Args:
        source_path: 文件路径或目录路径
        
    Returns:
        标准化后的源文件路径列表
    """
    is_dir = os.path.isdir(source_path)
    if not is_dir:
        return [_normalize_source_path(source_path)]

    target_sources = []
    for root, _, files in os.walk(source_path):
        for file in files:
            file_path = os.path.join(root, file)
            target_sources.append(_normalize_source_path(file_path))
    return target_sources


def _delete_bm25_documents_by_sources(target_sources: list[str]) -> int:
    """
    从 BM25 索引中删除与指定源文件关联的文档。
    
    Args:
        target_sources: 需要删除的源文件路径列表
        
    Returns:
        成功删除的文档数量
    """
    bm25_persist_path = Config.get("bm25.persist_path", "./bm25_index/index.pkl")
    if not os.path.exists(bm25_persist_path):
        logger.warning(f"BM25索引不存在，跳过删除: {bm25_persist_path}")
        return 0

    bm25_index = BM25Index.load(bm25_persist_path)
    removed_count = bm25_index.delete_by_sources(target_sources)
    if removed_count:
        bm25_index.save(bm25_persist_path)
    logger.info(f"BM25索引删除 {removed_count} 个关联文档")
    return removed_count


def delete_documents_by_source(source_path: str):
    """
    删除指定源文件或源目录下的所有文档

    Args:
        source_path: 文件路径或目录路径。
                     - 如果是文件，将删除 metadata 中 source 字段完全匹配该路径的文档。
                     - 如果是目录，将删除 metadata 中 source 字段以该目录路径开头的所有文档。
    """
    Config.load()

    persist_dir = Config.get("chroma.persist_dir", "../chroma_db")
    embedding_model = Config.get("embeddings.model", "text-embedding-v4")

    logger.info(f"加载向量数据库: {persist_dir}")
    logger.info(f"目标路径: {source_path}")

    # 初始化 embeddings
    embeddings = DashScopeEmbeddings(model=embedding_model)

    # 加载向量数据库
    vectordb = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )

    is_dir = os.path.isdir(source_path)
    target_sources = _collect_target_sources(source_path)
    
    if is_dir:
        # 遍历实际目录下的所有文件，构建需要删除的 source 路径列表
        logger.info(f"检测到目录，正在遍历: {source_path}")

        if not target_sources:
            logger.warning(f"目录下未找到任何文件: {source_path}")
            results = {'ids': []}
        else:
            logger.info(f"找到 {len(target_sources)} 个文件，开始从数据库中检索对应文档...")
            
            ids_to_delete = []
            
            batch_size = 100
            for i in range(0, len(target_sources), batch_size):
                batch_sources = target_sources[i:i+batch_size]
                # 构造 OR 查询条件: {"$or": [{"source": "path1"}, {"source": "path2"}, ...]}
                where_clause = {
                    "$or": [{"source": src} for src in batch_sources]
                }
                
                try:
                    batch_results = vectordb.get(where=where_clause)
                    if batch_results and batch_results['ids']:
                        ids_to_delete.extend(batch_results['ids'])
                except Exception as e:
                    logger.warning(f"批量查询失败，降级为逐个查询: {e}")
                    # 降级方案：逐个查询
                    for src in batch_sources:
                        try:
                            res = vectordb.get(where={"source": src})
                            if res and res['ids']:
                                ids_to_delete.extend(res['ids'])
                        except Exception as inner_e:
                            logger.error(f"查询文件 {src} 失败: {inner_e}")

            # 去重 ID (以防万一)
            ids_to_delete = list(set(ids_to_delete))
            results = {'ids': ids_to_delete}
            logger.info(f"共找到 {len(ids_to_delete)} 个关联文档")

    else:
        # 精确匹配文件路径
        logger.info("检测到文件，将执行精确匹配删除")
        results = vectordb.get(where={"source": target_sources[0]})

    if not results['ids']:
        logger.warning(f"未找到路径 {source_path} 相关的文档")
        _delete_bm25_documents_by_sources(target_sources)
        return

    doc_count = len(results['ids'])
    logger.info(f"找到 {doc_count} 个待删除文档")

    # 显示部分文档 ID 列表（用于确认，最多显示 10 个）
    display_count = min(10, doc_count)
    for i, doc_id in enumerate(results['ids'][:display_count], 1):
        logger.info(f"  [{i}] ID: {doc_id}")
    if doc_count > 10:
        logger.info(f"  ... 还有 {doc_count - 10} 个文档")

    # 执行删除
    logger.info(f"开始删除 {doc_count} 个文档...")
    vectordb.delete(ids=results['ids'])

    logger.info(f"✓ 成功删除 {doc_count} 个文档")
    _delete_bm25_documents_by_sources(target_sources)


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

