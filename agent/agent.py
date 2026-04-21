
"""
Agent 核心模块

负责创建和运行 CodeMind Agent，集成工具调用。
支持流式输出和非流式输出两种模式。
"""
import json
from typing import List, Any, Dict, Optional, AsyncGenerator
from langchain.agents import create_agent
from langchain_core.tools import Tool
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from utils.config import Config
from prompts.prompt_manager import PromptManager, PromptScenario, PromptLanguage
from .tools import ReadFile, SearchCode, RunCommand, RetrieveAndSummarize

from langchain_core.messages import (
    message_to_dict,
    HumanMessage,
    AIMessage,
    ToolMessage, messages_from_dict
)

logger = get_logger("agent.core")


def _process_history(history: list[dict]) -> list:
    """
    处理历史记录，转换为 LangChain 消息对象。

    Args:
        history: 原始历史记录列表

    Returns:
        处理后的 LangChain 消息对象列表
    """
    try:
        processed = messages_from_dict(history)
        return processed

    except Exception as e:
        logger.error(f"历史消息转换错误！")
        return []


def get_tools() -> List[Tool]:
    """
    获取所有可用的 Agent 工具列表。

    Returns:
        工具对象列表
    """
    return [ReadFile, SearchCode, RunCommand, RetrieveAndSummarize]


def load_system_prompts() -> str:
    """
    加载 Agent 系统提示词。

    Returns:
        系统提示词字符串
    """
    prompt_manager = PromptManager.get_instance()
    prompt_template = prompt_manager.get_prompt(
        scenario=PromptScenario.AGENT_SYSTEM,
        language=PromptLanguage.ZH_CN
    )
    # AGENT_SYSTEM 提示词没有输入变量，直接返回模板字符串
    return prompt_template.template


class CodeMindAgent:
    """
    CodeMind Agent 封装类

    提供统一的接口来执行 Agent 任务，支持流式输出和非流式输出。
    Agent 会根据问题自主决定何时使用工具（包括检索和总结）。
    """

    def __init__(
            self,
            model: Optional[str] = None,
            temperature: Optional[float] = None
    ):
        """
        初始化 CodeMind Agent。

        Args:
            model: 模型名称，默认从配置读取
            temperature: 温度参数，默认从配置读取
        """
        if model is None:
            model = Config.get("agent.model", "qwen-max")
        if temperature is None:
            temperature = Config.get("agent.temperature", 0.1)

        logger.info(f"Initializing CodeMindAgent: model={model}, temperature={temperature}")

        # 初始化 LLM
        self.chat_model = ChatTongyi(
            model=model,
            temperature=temperature,
        )

        # 获取工具列表
        self.tools = get_tools()

        # 加载系统提示词
        self.system_prompt = load_system_prompts()

        # 创建 Agent（LangChain 1.0 新 API）
        self.agent = create_agent(
            model=self.chat_model,
            system_prompt=self.system_prompt,
            tools=self.tools
        )

        logger.info("CodeMindAgent initialized successfully")

    def _build_user_message(self, question: str) -> str:
        """
        构建用户消息内容。

        Args:
            question: 用户问题

        Returns:
            用户消息
        """
        return question


    async def aexecute(
            self,
            question: str,
            history: list[dict] = []
    ) -> Dict[str, Any]:
        """
        异步版本：非流式执行 Agent 任务。

        Args:
            question: 用户问题
            history: 历史消息列表

        Returns:
            包含回答的字典
        """
        logger.info(f"执行 Agent，问题: {question}")

        # 构建用户消息内容
        user_message_content = self._build_user_message(question)

        # 处理历史记录，从 content1 中提取 content2
        processed_history = _process_history(history)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息 >:")
        logger.debug(user_message_content)
        logger.debug(f"📜 历史消息数量: {len(processed_history)}")
        logger.debug("=" * 80)

        # 构建完整的消息列表
        messages = processed_history.copy()
        messages.append(HumanMessage(content=user_message_content))

        # 运行 Agent（异步）
        logger.info("正在调用 Agent >...")
        try:
            response = await self.agent.ainvoke({
                "messages": messages
            })

            logger.info("Agent 执行完成 >")

            # Debug: 输出 Agent 的完整返回结果
            logger.debug("=" * 80)
            logger.debug("🤖 Agent 完整返回结果 >:")
            for i, msg in enumerate(response["messages"]):
                role = msg.get("role", "unknown") if isinstance(msg, dict) else getattr(msg, "role", "unknown")
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                logger.debug(f"  [{i + 1}] 角色: {role}")
                logger.debug(f"  内容:\n{content}")
                logger.debug("-" * 60)
            logger.debug("=" * 80)

            # 获取最终回答：messages 列表的最后一条
            answer = response["messages"][-1].content

            # Info: 输出最终答案
            logger.info("=" * 80)
            logger.info("✅ Agent 最终答案 >:")
            logger.info(answer)
            logger.info("=" * 80)

            return {
                "answer": answer,
                "agent_mode": True
            }
        except Exception as e:
            logger.error(f"Agent 执行失败 >: {e}")
            return {
                "answer": f"Agent 执行遇到问题: {str(e)}",
                "error": str(e)
            }

    async def aexecute_stream(
            self,
            question: str,
            history: list[dict] = [],
            context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步版本：流式执行 Agent 任务。

        Args:
            question: 用户问题
            history: 历史消息列表
            context: 附加上下文参数（可选）

        Yields:
            流式输出的内容片段
        """
        logger.info(f"执行 Agent (异步流式)，问题: {question}")

        # 构建用户消息内容
        user_message_content = self._build_user_message(question)

        # 处理历史记录，从 content1 中提取 content2
        processed_history = _process_history(history)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息 (异步流式):")
        logger.debug(user_message_content)
        logger.debug(f"📜 历史消息数量: {len(processed_history)}")
        logger.debug("=" * 80)

        # 流式运行 Agent（异步）
        logger.info("正在启动 Agent 流 >...")
        try:
            # 构建完整的消息列表
            messages = processed_history.copy()
            messages.append(HumanMessage(content=user_message_content))

            input_dict = {
                "messages": messages
            }

            stream_context = context if context is not None else {}

            async for chunk in self.agent.astream(input_dict, stream_mode="values", context=stream_context):
                last_message = chunk["messages"][-1]
                yield message_to_dict(last_message)

            logger.info("Agent 流完成 >")

        except Exception as e:
            logger.error(f"Agent 流执行失败 >: {e}")
            error_msg = f"Agent 流式执行遇到问题：{str(e)}"
            yield {"type": "error", "data": {"content": error_msg}}

