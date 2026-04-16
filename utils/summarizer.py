"""
总结层模块（Summarizer Layer）

负责对向量检索返回的结果进行总结提炼，
避免将过多原始文档直接传给主 LLM。
"""
from typing import List
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger

logger = get_logger("summarizer")


# 总结提示词模板
SUMMARIZER_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["input", "context"],
    template="""你是专注于"基于参考资料总结"的AI助手，需结合用户提问和向量检索到的参考资料，生成简洁准确的概括回答。

### 输入信息
1. 用户提问：{input}
2. 参考资料(在下一个###之前内容均为参考资料)：{context}

### 严格遵守以下约束（违反将导致回答无效）
1. 内容合规：禁止包含违法、侵权、攻击性信息；
2. 事实准确：回答必须完全基于参考资料中的信息，不编造、不添加未提及的内容，不做主观推断；
3. 语言要求：仅用中文回答，语气客观、简洁，不冗余；
4. 聚焦提问：严格围绕用户原始提问总结，不扩充问题范围、不额外追问、不构造新query；
5. 格式要求：仅输出概括内容本身，以纯文本字符串形式呈现，不封装为字典、列表、JSON等任何结构，不附带额外说明。
"""
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


def summarize_context(question: str, raw_context: str, summarizer_llm: ChatTongyi) -> str:
    """
    使用总结模型对原始上下文进行总结。

    Args:
        question: 用户原始问题
        raw_context: 由检索文档构建的原始上下文
        summarizer_llm: 总结模型实例

    Returns:
        总结后的精炼内容
    """
    prompt = SUMMARIZER_PROMPT_TEMPLATE.format(input=question, context=raw_context)

    # Debug: 输出总结模块的提示词
    logger.debug("=" * 80)
    logger.debug("📝 总结模块提示词:")
    logger.debug(prompt)
    logger.debug("=" * 80)

    logger.info("正在调用总结模型...")
    response = summarizer_llm.invoke(prompt)
    summary = response.content if hasattr(response, 'content') else str(response)

    # Debug: 输出总结模型的返回结果
    logger.debug("=" * 80)
    logger.debug("🤖 总结模型返回结果:")
    logger.debug(summary)
    logger.debug("=" * 80)

    logger.debug("上下文总结完成")
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
        model=model,
        temperature=temperature,
    )
