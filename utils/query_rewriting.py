"""
查询改写模块

将模型调用时传入的用户问题拆分为关键词，并推测可能的回答
"""
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import PromptTemplate
from prompts.prompt_manager import PromptManager, PromptScenario, PromptLanguage
from utils.logger import get_logger
logger = get_logger("query_rewriting")

def get_query_rewriting_prompt_template(type: str) -> PromptTemplate:
    """
    获取查询改写提示词模板。

    Args:
        type (str): 提示词类型，支持 "key_words"（关键词提取）和 "answer_guess"（回答推测）。

    Returns:
        PromptTemplate: 对应的查询改写提示词模板。

    Raises:
        ValueError: 当传入的 type 不支持时抛出异常。
    """
    prompt_manager = PromptManager.get_instance()

    if type == "key_words":
        return prompt_manager.get_prompt(
            scenario=PromptScenario.QUERY_KEY_WORDS,
            language=PromptLanguage.ZH_CN
        )
    elif type == "answer_guess":
        return prompt_manager.get_prompt(
            scenario=PromptScenario.QUERY_ANSWER_GUESS,
            language=PromptLanguage.ZH_CN
        )
    else:
        raise ValueError("没有相关问题改写提示词！")


async def aget_query_key_words(question: str, query_rewriting_llm: ChatTongyi) -> list:
    """
    异步获取用户问题的关键词列表。

    该函数通过调用大语言模型，根据预设的提示词模板从用户问题中提取关键信息，
    并将结果解析为关键词列表。同时记录详细的调试日志以便追踪处理过程。

    Args:
        question (str): 用户输入的原始问题字符串。
        query_rewriting_llm (ChatTongyi): 用于执行查询改写任务的大语言模型实例。

    Returns:
        list: 提取出的关键词列表。如果模型返回为空或解析失败，可能返回空列表。
    """

    # 使用查询改写模型进行关键词提取
    prompt_template = get_query_rewriting_prompt_template(type="key_words")
    prompt = prompt_template.format(input=question)

    # Debug: 输出关键词提取的提示词
    logger.debug("=" * 80)
    logger.debug("📝 问题关键词提取提示词:")
    logger.debug(prompt)
    logger.debug("=" * 80)

    logger.info("正在调用查询改写模型...")
    response = await query_rewriting_llm.ainvoke(prompt)
    key_words_str = response.content if hasattr(response, 'content') else str(response)
    # 清理和过滤关键词
    key_words = [kw.strip() for kw in key_words_str.split(",") if kw.strip()]

    # Debug: 输出关键词提取的返回结果
    logger.debug("=" * 80)
    logger.debug("🤖 关键词提取返回结果:")
    logger.debug(key_words)
    logger.debug("=" * 80)

    logger.debug("上下文总结完成 (异步)")
    return key_words

async def aget_query_answer_guess(question: str, query_rewriting_llm: ChatTongyi) -> str:
    """
    异步获取对用户问题的可能回答推测。

    该函数通过调用大语言模型，根据预设的提示词模板推测用户问题可能的回答方向或简要内容。
    同时记录详细的调试日志以便追踪处理过程。

    Args:
        question (str): 用户输入的原始问题字符串。
        query_rewriting_llm (ChatTongyi): 用于执行查询改写任务的大语言模型实例。

    Returns:
        str: 模型推测的可能回答内容。如果模型返回为空或解析失败，可能返回空字符串。
    """
    # 使用查询改写模型进行回答推测
    prompt_template = get_query_rewriting_prompt_template(type="answer_guess")
    prompt = prompt_template.format(input=question)

    # Debug: 输出回答推测的提示词
    logger.debug("=" * 80)
    logger.debug("📝 问题回答推测提示词:")
    logger.debug(prompt)
    logger.debug("=" * 80)

    logger.info("正在调用查询改写模型进行回答推测...")
    response = await query_rewriting_llm.ainvoke(prompt)
    answer_guess_str = response.content if hasattr(response, 'content') else str(response)
    
    # 清理结果，去除首尾空白
    answer_guess_str = answer_guess_str.strip()

    # Debug: 输出回答推测的返回结果
    logger.debug("=" * 80)
    logger.debug("🤖 回答推测返回结果:")
    logger.debug(answer_guess_str)
    logger.debug("=" * 80)

    return answer_guess_str


def create_query_rewriter(model: str = "qwen-max") -> ChatTongyi:
    """
    创建查询改写模型实例。

    Args:
        model: 模型名称

    Returns:
        ChatTongyi 实例
    """
    logger.info(f"Creating query rewriter LLM: model={model}")
    return ChatTongyi(
        model=model
    )