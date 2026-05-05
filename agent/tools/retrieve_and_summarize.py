
"""
RetrieveAndSummarize 工具

使用 LangChain @tool 装饰器定义，封装向量搜索和上下文总结功能。
这是一个组合工具，一次性完成检索和总结两个步骤。
"""
from typing import Optional, Any
from langchain_core.tools import tool

from utils.logger import get_logger
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

    # TODO: 混合检索：向量检索+BM25检索

    logger.info(f"[ToolsCall] RetrieveAndSummarize called: question={question}")

    if _service_manager is None:
        error_msg = "[错误] RetrieveAndSummarize 工具未初始化，无法访问向量数据库"
        logger.error(error_msg)
        return error_msg

    vectordb = _service_manager.vectordb
    summarizer_llm = _service_manager.summarizer_llm
    retrieval_k = _service_manager.retrieval_k

    if vectordb is None:
        error_msg = "[错误] 向量数据库未初始化"
        logger.error(error_msg)
        return error_msg

    if summarizer_llm is None:
        error_msg = "[错误] 总结模型未初始化"
        logger.error(error_msg)
        return error_msg

    try:
        # 步骤1: 向量检索
        logger.info(f"开始向量数据库检索，数量: {retrieval_k}")
        # TODO
        """
        第一步：Query优化
        •Query Rewriting：把用户的问题改写成更适合检索的形式•Query Decomposition：把复杂问题拆成几个子问题•HyDE：先让LLM生成一个假设性的答案，再用这个答案去检索
        """

        docs = await vectordb.asimilarity_search(question, k=retrieval_k)

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

