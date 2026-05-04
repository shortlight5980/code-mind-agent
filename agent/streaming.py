
"""
Agent 流式处理模块

负责 Agent 流式输出的消息格式化和异步/同步桥接逻辑
"""
import asyncio
import json
from typing import Dict, Any, AsyncGenerator, Optional
from fastapi import Request

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
        message["type"] = "human"
        message["content"] = chunk["data"]["content"]
        return message

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
        message["tool_call_id"] = chunk["data"].get("tool_call_id", "")
        message["name"] = chunk["data"].get("name", "")

    return message if message else None


async def agenerate_agent_stream(
        agent: CodeMindAgent,
        question: str,
        request: Request,
        history: list[dict] = []
) -> AsyncGenerator[str, None]:
    """
    生成 Agent 流式响应（真正异步版本）

    使用 Agent 的异步流式接口，提供真正的异步性能

    Args:
        agent: CodeMindAgent 实例
        question: 用户问题

    Yields:
        SSE 格式的流式响应
    """
    logger.info("启动异步 Agent 流...")

    try:
        async for chunk in agent.aexecute_stream(question, history):
            # # 处理 chunk
            # message = process_chunk(chunk)
            message = chunk

            task = asyncio.current_task()
            if await request.is_disconnected():
                logger.info("客户端断开连接，停止生成")
                break

            if message:
                logger.info("+" * 20)
                logger.info(f"[response_message] {json.dumps(message, ensure_ascii=False)}")
                logger.info("+" * 20)

            # yield json.dumps(message, ensure_ascii=False)

                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

        # 发送结束标志
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"异步流式生成失败: {e}")
        yield f"\n[Error] 异步流式生成失败: {str(e)}\n"

