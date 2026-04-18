"""
Agent 流式处理模块

负责 Agent 流式输出的消息格式化和异步/同步桥接逻辑
"""
import json
import queue
import asyncio
from typing import Dict, Any, AsyncGenerator, Generator, Optional
from langchain_community.chat_models import ChatTongyi

from utils.logger import get_logger
from .agent import CodeMindAgent

logger = get_logger("agent.streaming")


def process_chunk(chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    处理 Agent 流式输出的 chunk，进行消息格式化

    Args:
        chunk: Agent 输出的原始 chunk

    Returns:
        格式化后的消息，跳过的消息返回 None
    """
    message: Dict[str, Any] = {}

    if chunk["type"] == "human":
        return None

    elif chunk["type"] == "ai":
        message["type"] = "ai"
        message["content"] = chunk["data"]["content"]
        message["id"] = chunk["data"]["id"]

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

    return message if message else None


async def generate_agent_stream(
    agent: CodeMindAgent,
    question: str,
    docs: list,
    summarizer_llm: ChatTongyi
) -> AsyncGenerator[str, None]:
    """
    生成 Agent 流式响应（异步/同步桥接）

    封装 Agent 的同步流式生成器，提供异步接口

    Args:
        agent: CodeMindAgent 实例
        question: 用户问题
        docs: 检索到的文档
        summarizer_llm: 摘要模型

    Yields:
        SSE 格式的流式响应
    """
    # 创建线程安全的队列，用于传递生成器产出的数据
    data_queue = queue.Queue()

    # 在独立线程中运行同步生成器
    def run_sync_generator():
        try:
            for chunk in agent.execute_stream(question, docs, summarizer_llm):
                data_queue.put(chunk)
        except Exception as e:
            data_queue.put(e)
        finally:
            data_queue.put(None)

    # 启动线程
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, run_sync_generator)

    # 异步从队列中拉取数据
    while True:
        item = await asyncio.to_thread(data_queue.get)

        if item is None:
            # 发送结束标志
            yield "data: [DONE]\n\n"
            break

        if isinstance(item, Exception):
            logger.error(f"流式生成失败: {item}")
            yield f"\n[Error] 流式生成失败: {str(item)}\n"
            break

        # 处理 chunk
        message = process_chunk(item)

        if message:
            logger.info("+" * 20)
            logger.info(f"[response_message] {json.dumps(message, ensure_ascii=False)}")
            logger.info("+" * 20)

            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"


def process_sync_stream(
    agent: CodeMindAgent,
    question: str,
    docs: list,
    summarizer_llm: ChatTongyi
) -> Generator[Dict[str, Any], None, None]:
    """
    处理同步流式输出，返回格式化后的消息

    Args:
        agent: CodeMindAgent 实例
        question: 用户问题
        docs: 检索到的文档
        summarizer_llm: 摘要模型

    Yields:
        格式化后的消息字典
    """
    for chunk in agent.execute_stream(question, docs, summarizer_llm):
        message = process_chunk(chunk)
        if message:
            yield message
