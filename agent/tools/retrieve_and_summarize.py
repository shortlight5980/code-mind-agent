
"""
RetrieveAndSummarize 工具

使用 LangChain @tool 装饰器定义，封装向量搜索和上下文总结功能。
这是一个组合工具，一次性完成检索和总结两个步骤。
"""
from typing import Optional, Any
from langchain_core.documents import Document
from langchain_core.tools import tool

from utils.logger import get_logger
from utils.fusion import rrf_fuse
from utils.query_rewriting import aget_query_key_words, aget_query_answer_guess
from utils.summarizer import asummarize_context

logger = get_logger("agent.tools.retrieve_and_summarize")


# 全局服务管理器引用，用于在工具中访问 vectordb 和 summarizer_llm
_service_manager: Optional[Any] = None


def initialize_tool_service_manager(service_manager: Any) -> None:
    """
    初始化工具的服务管理器引用

    Args:
        service_manager: 服务管理器实例
    """
    global _service_manager
    _service_manager = service_manager
    logger.info("RetrieveAndSummarize 工具服务管理器已初始化")


@tool
async def RetrieveAndSummarize(question: str) -> str:
    """
    根据用户问题从代码库中检索相关文档并进行总结提炼。
    这个工具会自动完成向量检索和上下文总结两个步骤，返回精炼后的参考资料。

    Args:
        question: 用户的问题，用于检索相关文档

    Returns:
        总结精炼后的参考资料上下文
    """

    logger.info(f"[ToolsCall] RetrieveAndSummarize called: question={question}")

    if _service_manager is None:
        error_msg = "[错误] RetrieveAndSummarize 工具未初始化，无法访问向量数据库"
        logger.error(error_msg)
        return error_msg

    vectordb = _service_manager.vectordb
    summarizer_llm = _service_manager.summarizer_llm
    query_rewriting_llm = _service_manager.query_rewriting_llm

    if vectordb is None:
        error_msg = "[错误] 向量数据库未初始化"
        logger.error(error_msg)
        return error_msg

    if summarizer_llm is None:
        error_msg = "[错误] 总结模型未初始化"
        logger.error(error_msg)
        return error_msg

    if query_rewriting_llm is None:
        error_msg = "[错误] 查询改写模型未初始化"
        logger.error(error_msg)
        return error_msg

    try:
        # 步骤1: 查询优化
        key_words = await aget_query_key_words(question, query_rewriting_llm)
        answer_guess = await aget_query_answer_guess(question, query_rewriting_llm)

        temp_question = answer_guess + " 关键词：" + (', '.join(key_words)) * 3

        logger.info("=" * 80)
        logger.info(f"最终用于检索的文本：{temp_question}")
        logger.info("=" * 80)

        docs = await _retrieve_documents(temp_question, _service_manager)

        if not docs:
            logger.warning("未检索到相关文档")
            return "未检索到相关的代码库文档。"

        # 记录来源信息（INFO级别）
        logger.info("=" * 60)
        logger.info(" 检索到的参考资料:")
        for i, doc in enumerate(docs):
            src = doc.metadata.get("source", "unknown")
            snippet = doc.page_content[:150].replace("\n", " ")
            logger.info(f"  [{i + 1}] {src}")
            logger.info(f"       片段: {snippet}...")
        logger.info("=" * 60)

        # 步骤2: 上下文总结
        logger.info("正在总结检索到的上下文...")
        summarized_context = await asummarize_context(question, docs, summarizer_llm)
        logger.info("上下文总结完成")

        return summarized_context

    except Exception as e:
        logger.error(f"RetrieveAndSummarize 执行失败: {e}")
        return f"[错误] 检索和总结失败: {str(e)}"


def _get_k(config: dict, plural_key: str, singular_key: str, default: int) -> int:
    """
    从配置中获取检索数量 k，兼容复数和单数键名。

    兼容说明：
    - 优先使用复数键（如 "docs"）
    - 降级到单数键（如 "doc"）
    - 最后使用默认值

    Args:
        config: 配置字典
        plural_key: 复数键名
        singular_key: 单数键名
        default: 默认值

    Returns:
        检索数量 k
    """
    return int(config.get(plural_key, config.get(singular_key, default)))


async def _retrieve_documents(query: str, service_manager: Any) -> list[Document]:
    """
    根据配置执行检索，支持向量检索、BM25 检索、混合检索三种模式。

    检索流程：
    1. 根据 mode 决定执行哪些检索
    2. 向量检索：分 doc 和 code 两类分别检索
    3. BM25 检索：分 doc 和 code 两类分别检索
    4. 混合模式：用 RRF 融合向量和 BM25 的结果

    设计说明：
    - doc 和 code 分开检索、分开融合，保证两类结果的比例
    - 融合后再截断到目标数量，避免过早截断丢失相关结果

    Args:
        query: 检索查询字符串
        service_manager: 服务管理器实例

    Returns:
        检索到的 Document 列表
    """
    vectordb = service_manager.vectordb
    bm25_index = getattr(service_manager, "bm25_index", None)
    vector_k = service_manager.retrieval_k
    bm25_k = getattr(service_manager, "bm25_retrieval_k", {"docs": 10, "codes": 20})
    retrieval_config = getattr(
        service_manager,
        "retrieval_config",
        {"mode": "hybrid", "fusion": "rrf", "rrf_k": 60, "identifier_boost": 0.0},
    )

    mode = retrieval_config.get("mode", "hybrid")
    docs_target_k = _get_k(vector_k, "docs", "doc", 5)
    codes_target_k = _get_k(vector_k, "codes", "code", 10)

    # ========== 步骤 1: 向量检索（如果 mode 是 vector 或 hybrid） ==========
    vector_docs: list[Document] = []
    vector_codes: list[Document] = []
    if mode in {"vector", "hybrid"}:
        logger.info(f"开始向量检索，数量: docs={docs_target_k}, codes={codes_target_k}")
        vector_docs = await vectordb.asimilarity_search(
            query,
            k=docs_target_k,
            filter={"type": "doc"},
        )
        vector_codes = await vectordb.asimilarity_search(
            query,
            k=codes_target_k,
            filter={"type": "code"},
        )

    # ========== 步骤 2: BM25 检索（如果 mode 是 bm25 或 hybrid，且索引可用） ==========
    bm25_docs: list[Document] = []
    bm25_codes: list[Document] = []
    if mode in {"bm25", "hybrid"} and bm25_index is not None:
        docs_bm25_k = _get_k(bm25_k, "docs", "doc", 10)
        codes_bm25_k = _get_k(bm25_k, "codes", "code", 20)
        logger.info(f"开始BM25检索，数量: docs={docs_bm25_k}, codes={codes_bm25_k}")
        bm25_docs = _bm25_results_to_documents(
            bm25_index.search(query, k=docs_bm25_k, filter_type="doc")
        )
        bm25_codes = _bm25_results_to_documents(
            bm25_index.search(query, k=codes_bm25_k, filter_type="code")
        )

    # ========== 步骤 3: 根据 mode 返回结果 ==========
    # 模式 1: 纯 BM25
    if mode == "bm25":
        return bm25_docs[:docs_target_k] + bm25_codes[:codes_target_k]

    # 模式 2: 纯向量，或者混合模式但 BM25 索引不可用
    if mode != "hybrid" or bm25_index is None:
        return vector_docs + vector_codes

    # 模式 3: 混合检索 + RRF 融合
    rrf_k = int(retrieval_config.get("rrf_k", 60))
    identifier_boost = float(retrieval_config.get("identifier_boost", 0.0))

    # doc 和 code 分开融合，保证两类结果的比例
    fused_docs = _fused_items_to_documents(
        rrf_fuse(
            [vector_docs, bm25_docs],
            rrf_k=rrf_k,
            identifier_query=query,
            identifier_boost=identifier_boost,
        )
    )[:docs_target_k]
    fused_codes = _fused_items_to_documents(
        rrf_fuse(
            [vector_codes, bm25_codes],
            rrf_k=rrf_k,
            identifier_query=query,
            identifier_boost=identifier_boost,
        )
    )[:codes_target_k]
    return fused_docs + fused_codes


def _bm25_results_to_documents(results: list[tuple[str, dict, float]]) -> list[Document]:
    """
    将 BM25 检索结果转换为 LangChain Document 列表。

    转换时会将 BM25 分数保存到 metadata 的 "bm25_score" 字段。

    Args:
        results: BM25 检索结果列表，每个元素是 (content, metadata, score)

    Returns:
        Document 列表
    """
    documents = []
    for content, metadata, score in results:
        enriched_metadata = dict(metadata)
        enriched_metadata["bm25_score"] = score  # 保存 BM25 分数
        documents.append(Document(page_content=content, metadata=enriched_metadata))
    return documents


def _fused_items_to_documents(items: list[dict]) -> list[Document]:
    """
    将 RRF 融合后的结果转换为 LangChain Document 列表。

    转换时会将融合分数保存到 metadata 的 "fusion_score" 字段。

    Args:
        items: RRF 融合结果列表，每个元素是 {"content": ..., "metadata": ..., "score": ...}

    Returns:
        Document 列表
    """
    return [
        Document(
            page_content=item["content"],
            metadata={**item["metadata"], "fusion_score": item["score"]},  # 保存融合分数
        )
        for item in items
    ]

