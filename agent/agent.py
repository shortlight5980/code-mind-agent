"""
Agent 核心模块

负责创建和运行 CodeMind Agent，集成工具调用和总结模块。
支持流式输出和非流式输出两种模式。
"""
import json
from typing import List, Any, Dict, Optional, AsyncGenerator
from langchain.agents import create_agent
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.tools import Tool
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from utils.config import Config
from utils.summarizer import asummarize_context
from prompts.prompt_manager import PromptManager, PromptScenario, PromptLanguage
from .tools import ReadFile, SearchCode, RunCommand

from langchain_chroma import Chroma

from langchain_core.messages import message_to_dict

logger = get_logger("agent.core")


def get_tools() -> List[Tool]:
    """
    获取所有可用的 Agent 工具列表。

    Returns:
        工具对象列表
    """
    return [ReadFile, SearchCode, RunCommand]


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
    """

    def __init__(
            self,
            model: Optional[str] = None,
            temperature: Optional[float] = None,
            summarizer_model: Optional[str] = None,
            summarizer_temperature: Optional[float] = None
    ):
        """
        初始化 CodeMind Agent。

        Args:
            model: 模型名称，默认从配置读取
            temperature: 温度参数，默认从配置读取
            summarizer_model: 总结模型名称，默认从配置读取
            summarizer_temperature: 总结模型温度参数，默认从配置读取
        """
        if model is None:
            model = Config.get("agent.model", "qwen-max")
        if temperature is None:
            temperature = Config.get("agent.temperature", 0.1)
        if summarizer_model is None:
            summarizer_model = Config.get("summarizer.model", "qwen-max")
        if summarizer_temperature is None:
            summarizer_temperature = Config.get("summarizer.temperature", 0.1)

        logger.info(f"Initializing CodeMindAgent: model={model}, temperature={temperature}")
        logger.info(f"Summarizer model: {summarizer_model}, temperature={summarizer_temperature}")

        # 初始化 LLM
        self.chat_model = ChatTongyi(
            model=model,
            temperature=temperature,
        )

        # 初始化总结模型（内部管理）
        self.summarizer_llm = ChatTongyi(
            model=summarizer_model,
            temperature=summarizer_temperature,
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

    def _build_user_message(self, question: str, summarized_context: str) -> str:
        """
        构建用户消息内容，将上下文和问题组合。

        Args:
            question: 用户问题
            summarized_context: 总结后的上下文

        Returns:
            组合后的用户消息
        """
        return f"""## 上下文信息\n{summarized_context}\n\n## 用户问题\n{question}\n\n"""

    async def aexecute(
            self,
            question: str,
            raw_docs: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        异步版本：非流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）

        Returns:
            包含回答和来源的字典
        """
        logger.info(f"执行 Agent (异步非流式)，问题: {question}")

        summarized_context = ""
        if raw_docs is not None:
            # 使用总结模块进行总结（异步，内部完成上下文构建）
            logger.info("正在总结检索到的上下文 (异步)...")
            summarized_context = await asummarize_context(question, raw_docs, self.summarizer_llm)
            logger.debug("上下文总结完成")

        # 步骤 3：构建用户消息内容
        user_message_content = self._build_user_message(question, summarized_context)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息 (异步):")
        logger.debug(user_message_content)
        logger.debug("=" * 80)

        # 步骤 4：运行 Agent（异步）
        logger.info("正在调用 Agent (异步)...")
        try:
            response = await self.agent.ainvoke({
                "messages": [
                    {"role": "user", "content": user_message_content}
                ]
            })

            logger.info("Agent 执行完成 (异步)")

            # Debug: 输出 Agent 的完整返回结果
            logger.debug("=" * 80)
            logger.debug("🤖 Agent 完整返回结果 (异步):")
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
            logger.info("✅ Agent 最终答案 (异步):")
            logger.info(answer)
            logger.info("=" * 80)

            result = {
                "answer": answer,
                "summarized_context": summarized_context
            }

            if raw_docs is not None:
                result["sources"] = [
                    {
                        "source": doc.metadata.get("source", "unknown"),
                        "content": doc.page_content
                    }
                    for doc in raw_docs
                ]

            return result
        except Exception as e:
            logger.error(f"Agent 执行失败 (异步): {e}")
            # 降级方案：如果 Agent 失败，使用总结后的上下文直接回答
            logger.info("正在回退到总结上下文...")

            result = {
                "answer": f"Agent 执行遇到问题，以下是基于检索结果的总结：\n\n{summarized_context}",
                "summarized_context": summarized_context,
                "error": str(e)
            }

            if raw_docs is not None:
                result["sources"] = [
                    {
                        "source": doc.metadata.get("source", "unknown"),
                        "content": doc.page_content
                    }
                    for doc in raw_docs
                ]

            return result

    async def aexecute_stream(
            self,
            question: str,
            raw_docs: Optional[List[Any]] = None,
            context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步版本：流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）
            context: 附加上下文参数（可选）

        Yields:
            流式输出的内容片段
        """
        logger.info(f"执行 Agent (异步流式)，问题: {question}")

        summarized_context = ""
        if raw_docs is not None:
            # 使用总结模块进行总结（异步，内部完成上下文构建）
            logger.info("正在总结检索到的上下文 (异步)...")
            summarized_context = await asummarize_context(question, raw_docs, self.summarizer_llm)
            logger.debug("上下文总结完成")

        # 步骤 3：构建用户消息内容
        user_message_content = self._build_user_message(question, summarized_context)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息 (异步流式):")
        logger.debug(user_message_content)
        logger.debug("=" * 80)

        # 步骤 4：流式运行 Agent（异步）
        logger.info("正在启动 Agent 流 (异步)...")
        try:
            input_dict = {
                "messages": [
                    {"role": "user", "content": user_message_content}
                ]
            }

            stream_context = context if context is not None else {}

            async for chunk in self.agent.astream(input_dict, stream_mode="values", context=stream_context):
                last_message = chunk["messages"][-1]
                yield message_to_dict(last_message)

            logger.info("Agent 流完成 (异步)")

        except Exception as e:
            logger.error(f"Agent 流执行失败 (异步): {e}")
            # 降级方案：如果流式执行失败，返回错误信息
            error_msg = f"Agent 流式执行遇到问题：{str(e)}"
            if summarized_context:
                error_msg += f"\n\n以下是基于检索结果的总结：\n\n{summarized_context}"
            yield {"type": "error", "data": {"content": error_msg}}


if __name__ == "__main__":
    agent = CodeMindAgent()

    question = "介绍一下本项目，调用一些可用的工具"

    row_docs = Chroma(
        persist_directory="./chroma_db",
        embedding_function=DashScopeEmbeddings(model="text-embedding-v3")
    ).similarity_search(question, k=7)

    for chunk in agent.execute_stream(question, row_docs):
        message: Dict[str, Any] = {}

        # 跳过human信息
        if chunk["type"] == "human":
            continue

        elif chunk["type"] == "ai":

            message["type"] = "ai"
            message["id"] = chunk["data"]["id"]
            message["content"] = chunk["data"]["content"]

            # 提取并简化 tool_calls
            raw_tool_calls = chunk["data"].get("tool_calls", [])

            simplified_tool_calls = []
            for tc in raw_tool_calls:
                simplified_tool_calls.append({
                    "id": tc["id"],
                    "name": tc["name"],
                    "args": tc["args"]
                })

            message["tool_calls"] = simplified_tool_calls

        elif chunk["type"] == "tool":
            message["type"] = "tool"
            message["content"] = chunk["data"]["content"]
            message["tool_call_id"] = chunk["data"]["tool_call_id"]
            message["name"] = chunk["data"]["name"]

        if not message:
            continue

        print("*" * 30)
        print(json.dumps(message, ensure_ascii=False), end="", flush=True)
        print("*" * 30)
