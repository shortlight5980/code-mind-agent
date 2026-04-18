"""
Agent 核心模块

负责创建和运行 CodeMind Agent，集成工具调用和总结模块。
支持流式输出和非流式输出两种模式。
"""
import json
from typing import List, Any, Dict, Generator, Optional, AsyncGenerator
from langchain.agents import create_agent
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.tools import Tool
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from utils.config import Config
from utils.summarizer import build_context, summarize_context, asummarize_context, create_summarizer
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

    def _build_user_message(self, question: str, summarized_context: str) -> str:
        """
        构建用户消息内容，将上下文和问题组合。

        Args:
            question: 用户问题
            summarized_context: 总结后的上下文

        Returns:
            组合后的用户消息
        """
        return f"""## 上下文信息
{summarized_context}

## 用户问题
{question}"""

    def execute(
        self,
        question: str,
        raw_docs: Optional[List[Any]] = None,
        summarizer_llm: Optional[ChatTongyi] = None
    ) -> Dict[str, Any]:
        """
        非流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）
            summarizer_llm: 总结模型实例（可选，提供 raw_docs 时必须提供）

        Returns:
            包含回答和来源的字典
        """
        logger.info(f"Executing agent (non-streaming) for question: {question}")

        summarized_context = ""
        if raw_docs is not None and summarizer_llm is not None:
            # 步骤 1：从检索文档构建原始上下文
            raw_context = build_context(raw_docs)
            logger.debug("原始上下文已构建")

            # 步骤 2：使用总结模块进行总结
            logger.info("Summarizing retrieved context...")
            summarized_context = summarize_context(question, raw_context, summarizer_llm)
            logger.debug("上下文总结完成")

        # 步骤 3：构建用户消息内容
        user_message_content = self._build_user_message(question, summarized_context)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息:")
        logger.debug(user_message_content)
        logger.debug("=" * 80)

        # 步骤 4：运行 Agent
        logger.info("Invoking agent...")
        try:
            response = self.agent.invoke({
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
            logger.error(f"Agent execution failed: {e}")
            # 降级方案：如果 Agent 失败，使用总结后的上下文直接回答
            logger.info("Falling back to summarized context...")

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

    def execute_stream(
        self,
        question: str,
        raw_docs: Optional[List[Any]] = None,
        summarizer_llm: Optional[ChatTongyi] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Generator[str, None, None]:
        """
        流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）
            summarizer_llm: 总结模型实例（可选，提供 raw_docs 时必须提供）
            context: 附加上下文参数（可选）

        Yields:
            流式输出的内容片段
        """
        logger.info(f"Executing agent (streaming) for question: {question}")

        summarized_context = ""
        if raw_docs is not None and summarizer_llm is not None:
            # 步骤 1：从检索文档构建原始上下文
            raw_context = build_context(raw_docs)
            logger.debug("原始上下文已构建")

            # 步骤 2：使用总结模块进行总结
            logger.info("Summarizing retrieved context...")
            summarized_context = summarize_context(question, raw_context, summarizer_llm)
            logger.debug("上下文总结完成")

        # 步骤 3：构建用户消息内容
        user_message_content = self._build_user_message(question, summarized_context)

        # Debug: 输出发送给 Agent 的提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给 Agent 的用户消息 (streaming):")
        logger.debug(user_message_content)
        logger.debug("=" * 80)

        # 步骤 4：流式运行 Agent
        logger.info("Starting agent stream...")
        try:
            input_dict = {
                "messages": [
                    {"role": "user", "content": user_message_content}
                ]
            }

            stream_context = context if context is not None else {}





            # for chunk in self.agent.stream(input_dict, stream_mode="values", context=stream_context):
            #     last_message = chunk["messages"][-1]
            #     if last_message.content:
            #         content = last_message.content.strip()
            #         if content:
            #             logger.debug(f"Stream chunk: {content[:50]}...")
            #             yield content + "\n"



            for chunk in self.agent.stream(input_dict, stream_mode="values", context=stream_context):
                last_message = chunk["messages"][-1]

                yield message_to_dict(last_message)





            logger.info("Agent stream completed")

        except Exception as e:
            logger.error(f"Agent stream execution failed: {e}")
            # 降级方案：如果流式执行失败，返回错误信息
            error_msg = f"Agent 流式执行遇到问题：{str(e)}"
            if summarized_context:
                error_msg += f"\n\n以下是基于检索结果的总结：\n\n{summarized_context}"
            yield error_msg + "\n"

    async def aexecute(
        self,
        question: str,
        raw_docs: Optional[List[Any]] = None,
        summarizer_llm: Optional[ChatTongyi] = None
    ) -> Dict[str, Any]:
        """
        异步版本：非流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）
            summarizer_llm: 总结模型实例（可选，提供 raw_docs 时必须提供）

        Returns:
            包含回答和来源的字典
        """
        logger.info(f"执行 Agent (异步非流式)，问题: {question}")

        summarized_context = ""
        if raw_docs is not None and summarizer_llm is not None:
            # 步骤 1：从检索文档构建原始上下文
            raw_context = build_context(raw_docs)
            logger.debug("原始上下文已构建")

            # 步骤 2：使用总结模块进行总结（异步）
            logger.info("正在总结检索到的上下文 (异步)...")
            summarized_context = await asummarize_context(question, raw_context, summarizer_llm)
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
                logger.debug(f"  [{i+1}] 角色: {role}")
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
        summarizer_llm: Optional[ChatTongyi] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步版本：流式执行 Agent 任务。

        Args:
            question: 用户问题
            raw_docs: 向量检索返回的原始文档列表（可选）
            summarizer_llm: 总结模型实例（可选，提供 raw_docs 时必须提供）
            context: 附加上下文参数（可选）

        Yields:
            流式输出的内容片段
        """
        logger.info(f"执行 Agent (异步流式)，问题: {question}")

        summarized_context = ""
        if raw_docs is not None and summarizer_llm is not None:
            # 步骤 1：从检索文档构建原始上下文
            raw_context = build_context(raw_docs)
            logger.debug("原始上下文已构建")

            # 步骤 2：使用总结模块进行总结（异步）
            logger.info("正在总结检索到的上下文 (异步)...")
            summarized_context = await asummarize_context(question, raw_context, summarizer_llm)
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


# 向后兼容的函数
def create_codemind_agent(
    model: str = None,
    temperature: float = None
):
    """
    创建并配置 CodeMind Agent（向后兼容）。

    Args:
        model: 模型名称，默认从配置读取
        temperature: 温度参数，默认从配置读取

    Returns:
        配置好的 Agent 实例（可直接调用 invoke/stream）
    """
    agent_instance = CodeMindAgent(model=model, temperature=temperature)
    return agent_instance.agent


def run_agent_with_summary(
    question: str,
    agent,
    raw_docs: List[Any],
    summarizer_llm: ChatTongyi
) -> Dict[str, Any]:
    """
    运行 Agent，先对检索结果进行总结，再执行 Agent（向后兼容）。

    注意：此函数保留向后兼容性，新代码建议使用 CodeMindAgent 类。

    Args:
        question: 用户问题
        agent: Agent 实例（来自 create_codemind_agent）
        raw_docs: 向量检索返回的原始文档列表
        summarizer_llm: 总结模型实例

    Returns:
        包含回答和来源的字典
    """
    # 创建 CodeMindAgent 实例并复用传入的 agent 对象
    # 注意：这里我们创建一个临时实例来使用 execute 方法
    temp_agent = CodeMindAgent()
    # 替换内部的 agent 为传入的实例（保持向后兼容）
    temp_agent.agent = agent

    return temp_agent.execute(
        question=question,
        raw_docs=raw_docs,
        summarizer_llm=summarizer_llm
    )


if __name__ == "__main__":
    agent = CodeMindAgent()

    question = "介绍一下本项目，调用一些可用的工具"

    row_docs = Chroma(
        persist_directory="./chroma_db",
        embedding_function=DashScopeEmbeddings(model="text-embedding-v3")
    ).similarity_search(question, k=7)

    summarizer = create_summarizer(
        model="qwen-max",
        temperature=0.1
    )

    for chunk in agent.execute_stream(question,row_docs,summarizer):
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

        print("*"*30)
        print(json.dumps(message, ensure_ascii=False), end="", flush=True)
        print("*"*30)
