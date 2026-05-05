"""
总结层模块（Summarizer Layer）

负责对向量检索返回的结果进行总结提炼，
避免将过多原始文档直接传给主 LLM。
"""
from typing import List

from langchain_core.callbacks import UsageMetadataCallbackHandler

from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from prompts.prompt_manager import PromptManager, PromptScenario, PromptLanguage

logger = get_logger("summarizer")


def get_summarizer_prompt_template() -> PromptTemplate:
    """
    获取总结提示词模板。

    Returns:
        总结提示词模板
    """
    prompt_manager = PromptManager.get_instance()
    return prompt_manager.get_prompt(
        scenario=PromptScenario.SUMMARIZATION,
        language=PromptLanguage.ZH_CN
    )


def build_context(docs: List) -> str:
    """
    从检索到的文档构建上下文字符串。

    Args:
        docs: 检索到的文档列表

    Returns:
        格式化后的上下文字符串
    """
    context_parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get('source', 'unknown')
        content = doc.page_content
        context_parts.append(f"### 来源 {i}: {source}\n```\n{content}\n```")
    return "\n\n".join(context_parts)


def _build_context(docs: List) -> str:
    """
    从检索到的文档构建上下文字符串（内部函数，别名）。

    Args:
        docs: 检索到的文档列表

    Returns:
        格式化后的上下文字符串
    """
    return build_context(docs)


async def asummarize_context(question: str, context_or_docs, summarizer_llm: ChatTongyi) -> str:
    """
    异步版本：使用总结模型对检索文档进行总结（兼容新旧接口）。

    Args:
        question: 用户原始问题
        context_or_docs: 原始上下文字符串（旧接口）或检索文档列表（新接口）
        summarizer_llm: 总结模型实例

    Returns:
        总结后的精炼内容
    """
    # 判断参数类型以决定使用哪个接口
    if isinstance(context_or_docs, str):
        # 旧接口：直接使用提供的原始上下文
        raw_context = context_or_docs
    else:
        # 新接口：从文档列表构建原始上下文
        raw_context = _build_context(context_or_docs)
        logger.debug("原始上下文已构建")

    # 使用总结模型进行总结
    prompt_template = get_summarizer_prompt_template()
    prompt = prompt_template.format(input=question, context=raw_context)

    # Debug: 输出总结模块的提示词
    logger.debug("=" * 80)
    logger.debug("📝 总结模块提示词 (异步):")
    logger.debug(prompt)
    logger.debug("=" * 80)

    logger.info("正在调用总结模型 (异步)...")
    response = await summarizer_llm.ainvoke(prompt, config={"callbacks": [UsageMetadataCallbackHandler()]})
    summary = response.content if hasattr(response, 'content') else str(response)

    # Debug: 输出总结模型的返回结果
    logger.debug("=" * 80)
    logger.debug("🤖 总结模型返回结果 (异步):")
    logger.debug(summary)
    logger.debug("=" * 80)

    logger.debug("上下文总结完成 (异步)")
    return summary


def create_summarizer(model: str = "qwen-max", temperature: float = 0.1) -> ChatTongyi:
    """
    创建总结模型实例。

    Args:
        model: 模型名称
        temperature: 温度参数

    Returns:
        ChatTongyi 实例
    """
    logger.info(f"Creating summarizer LLM: model={model}, temperature={temperature}")
    return ChatTongyi(
        model=model
    )
