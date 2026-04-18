"""
RAG 上下文构建模块
负责文档拼接、基于问题的摘要压缩、多文档融合策略等上下文处理逻辑
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from langchain_core.documents import Document
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from utils.summarizer import build_context, summarize_context, asummarize_context

logger = get_logger("context_builder")


@dataclass
class ProcessedContext:
    """处理后的上下文结果"""
    raw_context: str
    summarized_context: str
    sources: List[Dict[str, str]]


class RAGContextBuilder:
    """RAG 上下文构建器"""

    def __init__(self, summarizer_llm: ChatTongyi):
        """
        初始化上下文构建器

        Args:
            summarizer_llm: 用于摘要的 LLM 模型
        """
        self.summarizer_llm = summarizer_llm

    def build_context(
        self,
        docs: List[Document],
        question: Optional[str] = None,
        enable_summarization: bool = True
    ) -> ProcessedContext:
        """
        构建 RAG 上下文

        Args:
            docs: 检索到的文档列表
            question: 用户问题（用于摘要压缩）
            enable_summarization: 是否启用摘要压缩

        Returns:
            处理后的上下文结果
        """
        logger.info(f"开始构建上下文，文档数量: {len(docs)}")

        # 1. 构建原始上下文
        raw_context = self._concat_documents(docs)
        logger.debug(f"原始上下文长度: {len(raw_context)} 字符")

        # 2. 生成来源列表
        sources = self._extract_sources(docs)

        # 3. 如果启用摘要且有问题，则进行摘要压缩
        summarized_context = raw_context
        if enable_summarization and question:
            logger.info("启用摘要压缩...")
            summarized_context = self._compress_context(raw_context, question)
            logger.debug(f"摘要后上下文长度: {len(summarized_context)} 字符")

        return ProcessedContext(
            raw_context=raw_context,
            summarized_context=summarized_context,
            sources=sources
        )

    async def abuild_context(
        self,
        docs: List[Document],
        question: Optional[str] = None,
        enable_summarization: bool = True
    ) -> ProcessedContext:
        """
        异步版本：构建 RAG 上下文

        Args:
            docs: 检索到的文档列表
            question: 用户问题（用于摘要压缩）
            enable_summarization: 是否启用摘要压缩

        Returns:
            处理后的上下文结果
        """
        logger.info(f"开始构建上下文 (异步)，文档数量: {len(docs)}")

        # 1. 构建原始上下文
        raw_context = self._concat_documents(docs)
        logger.debug(f"原始上下文长度: {len(raw_context)} 字符")

        # 2. 生成来源列表
        sources = self._extract_sources(docs)

        # 3. 如果启用摘要且有问题，则进行摘要压缩
        summarized_context = raw_context
        if enable_summarization and question:
            logger.info("启用摘要压缩 (异步)...")
            summarized_context = await self._acompress_context(raw_context, question)
            logger.debug(f"摘要后上下文长度: {len(summarized_context)} 字符")

        return ProcessedContext(
            raw_context=raw_context,
            summarized_context=summarized_context,
            sources=sources
        )

    def _concat_documents(self, docs: List[Document]) -> str:
        """
        拼接文档内容

        Args:
            docs: 文档列表

        Returns:
            拼接后的文本文档
        """
        return build_context(docs)

    def _extract_sources(self, docs: List[Document]) -> List[Dict[str, str]]:
        """
        提取文档来源信息

        Args:
            docs: 文档列表

        Returns:
            来源信息列表
        """
        sources = []
        for doc in docs:
            sources.append({
                "source": doc.metadata.get("source", "unknown"),
                "content": doc.page_content
            })
        return sources

    def _compress_context(self, raw_context: str, question: str) -> str:
        """
        基于问题压缩上下文

        Args:
            raw_context: 原始上下文
            question: 用户问题

        Returns:
            压缩后的上下文
        """
        return summarize_context(question, raw_context, self.summarizer_llm)

    async def _acompress_context(self, raw_context: str, question: str) -> str:
        """
        异步版本：基于问题压缩上下文

        Args:
            raw_context: 原始上下文
            question: 用户问题

        Returns:
            压缩后的上下文
        """
        return await asummarize_context(question, raw_context, self.summarizer_llm)




    def log_context_debug(
        self,
        docs: List[Document],
        processed_context: ProcessedContext
    ) -> None:
        """
        记录上下文调试信息

        Args:
            docs: 原始文档列表
            processed_context: 处理后的上下文
        """
        # 记录向量数据库检索结果
        logger.debug("=" * 80)
        logger.debug(" 向量数据库完整结果:")
        for i, doc in enumerate(docs):
            src = doc.metadata.get("source", "unknown")
            logger.debug(f"  [{i+1}] 来源: {src}")
            logger.debug(f"  内容:\n{doc.page_content}")
            logger.debug("-" * 60)
        logger.debug("=" * 80)

        # 记录原始上下文
        logger.debug("=" * 80)
        logger.debug(" 完整参考资料 (raw_context):")
        logger.debug(processed_context.raw_context)
        logger.debug("=" * 80)

        # 记录摘要上下文
        logger.debug("=" * 80)
        logger.debug(" 摘要上下文:")
        logger.debug(processed_context.summarized_context)
        logger.debug("=" * 80)

    def log_sources_info(self, docs: List[Document]) -> None:
        """
        记录来源信息（INFO级别）

        Args:
            docs: 文档列表
        """
        logger.info("=" * 60)
        logger.info(" 参考资料:")
        for i, doc in enumerate(docs):
            src = doc.metadata.get("source", "unknown")
            snippet = doc.page_content[:150].replace("\n", " ")
            logger.info(f"  [{i+1}] {src}")
            logger.info(f"       片段: {snippet}...")
        logger.info("=" * 60)
