"""
Agent 核心模块

负责创建和运行 CodeMind Agent，集成工具调用和总结模块。
"""
from typing import List, Any, Dict
from langchain.agents import create_agent
from langchain_core.tools import Tool
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from utils.config import Config
from utils.summarizer import build_context, summarize_context
from agent.prompts import CODEMIND_AGENT_PROMPT
from agent.tools import ReadFile, SearchCode, RunCommand

logger = get_logger("agent.core")


def get_tools() -> List[Tool]:
    """
    获取所有可用的 Agent 工具列表。

    Returns:
        工具对象列表
    """
    return [ReadFile, SearchCode, RunCommand]


def create_codemind_agent(
    model: str = None,
    temperature: float = None
):
    """
    创建并配置 CodeMind Agent。

    Args:
        model: 模型名称，默认从配置读取
        temperature: 温度参数，默认从配置读取

    Returns:
        配置好的 Agent 实例（可直接调用 invoke/stream）
    """
    if model is None:
        model = Config.get("agent.model", "qwen-max")
    if temperature is None:
        temperature = Config.get("agent.temperature", 0.1)

    logger.info(f"Creating CodeMind Agent: model={model}, temperature={temperature}")

    # 初始化 LLM
    llm = ChatTongyi(
        model=model,
        temperature=temperature,
    )

    # 获取工具列表
    tools = get_tools()

    # 从 PromptTemplate 中提取纯文本作为 system_prompt
    system_prompt_text = """你是 CodeMind Agent，一个专业的代码仓库智能助手。你的任务是基于提供的上下文信息和可用工具，帮助用户分析和理解代码仓库。

## 可用工具
你可以使用以下工具来帮助完成任务：
1. ReadFile - 读取指定文件内容，支持行号范围
2. SearchCode - 在代码库中搜索关键词或正则表达式
3. RunCommand - 执行只读 shell 命令（如 ls, cat, grep, git 等）

## 回答要求
1. 如果答案在上下文中，请直接引用相关代码片段并给出详细解释
2. 如果需要更多信息，可以使用工具来获取
3. 回答要条理清晰，分点说明
4. 对于代码相关问题，给出具体的代码示例或修改建议
5. 请用中文回答"""

    logger.debug("=" * 80)
    logger.debug("🤖 Agent 系统提示词:")
    logger.debug(system_prompt_text)
    logger.debug("=" * 80)

    # 创建 Agent（LangChain 1.0 新 API）
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt_text,
    )

    logger.info("CodeMind Agent created successfully")
    return agent


def run_agent_with_summary(
    question: str,
    agent,
    raw_docs: List[Any],
    summarizer_llm: ChatTongyi
) -> Dict[str, Any]:
    """
    运行 Agent，先对检索结果进行总结，再执行 Agent。

    执行流程：
    1. 从检索文档构建原始上下文
    2. 使用总结模块进行总结
    3. 将总结后的上下文传给 Agent
    4. 运行 Agent 并返回结果

    Args:
        question: 用户问题
        agent: Agent 实例（来自 create_codemind_agent）
        raw_docs: 向量检索返回的原始文档列表
        summarizer_llm: 总结模型实例

    Returns:
        包含回答和来源的字典
    """
    logger.info(f"Running agent with summary for question: {question}")

    # 步骤 1：从检索文档构建原始上下文
    raw_context = build_context(raw_docs)
    logger.debug("原始上下文已构建")

    # 步骤 2：使用总结模块进行总结
    logger.info("Summarizing retrieved context...")
    summarized_context = summarize_context(question, raw_context, summarizer_llm)
    logger.debug("上下文总结完成")

    # 步骤 3：构建用户消息内容，将上下文和问题组合
    user_message_content = f"""## 上下文信息
{summarized_context}

## 用户问题
{question}"""

    # Debug: 输出发送给 Agent 的提示词
    logger.debug("=" * 80)
    logger.debug("💬 发送给 Agent 的用户消息:")
    logger.debug(user_message_content)
    logger.debug("=" * 80)

    # 步骤 4：运行 Agent（LangChain 1.0 新 API）
    logger.info("Invoking agent...")
    try:
        # 新 API 调用格式：传入 messages 列表
        response = agent.invoke({
            "messages": [
                {"role": "user", "content": user_message_content}
            ]
        })

        logger.info("Agent execution completed")

        # Debug: 输出 Agent 的完整返回结果
        logger.debug("=" * 80)
        logger.debug("🤖 Agent 完整返回结果:")
        for i, msg in enumerate(response["messages"]):
            role = msg.get("role", "unknown") if isinstance(msg, dict) else getattr(msg, "role", "unknown")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            logger.debug(f"  [{i+1}] 角色: {role}")
            logger.debug(f"  内容:\n{content}")
            logger.debug("-" * 60)
        logger.debug("=" * 80)

        # 获取最终回答：messages 列表的最后一条
        answer = response["messages"][-1].content

        # Info: 输出最终答案
        logger.info("=" * 80)
        logger.info("✅ Agent 最终答案:")
        logger.info(answer)
        logger.info("=" * 80)

        return {
            "answer": answer,
            "sources": [
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "content": doc.page_content
                }
                for doc in raw_docs
            ],
            "summarized_context": summarized_context
        }
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        # 降级方案：如果 Agent 失败，使用总结后的上下文直接回答
        logger.info("Falling back to summarized context...")
        return {
            "answer": f"Agent 执行遇到问题，以下是基于检索结果的总结：\n\n{summarized_context}",
            "sources": [
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "content": doc.page_content
                }
                for doc in raw_docs
            ],
            "summarized_context": summarized_context,
            "error": str(e)
        }
