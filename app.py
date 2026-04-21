
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from utils.logger import get_logger
from services.service_manager import ServiceManager
from agent.streaming import agenerate_agent_stream

logger = get_logger("app")

# 全局服务管理器实例
service_manager: ServiceManager


class Query(BaseModel):
    question: str
    history: list[dict]


async def single_result_generator(text: str) -> AsyncGenerator[str, None]:
    """异步生成单个结果的生成器，用于非流式回退场景"""
    yield text


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan事件处理器，用于服务初始化和清理"""
    global service_manager
    try:
        service_manager = ServiceManager.get_instance()
        # 使用 asyncio.to_thread() 包装同步初始化，避免阻塞事件循环
        await asyncio.to_thread(service_manager.initialize)
    except Exception as e:
        logger.error(f"初始化失败: {e}")
    yield
    # 关闭时清理
    # 使用 asyncio.to_thread() 包装同步清理，避免阻塞事件循环
    await asyncio.to_thread(service_manager.cleanup)
    logger.info("服务已清理")


app = FastAPI(title="CodeMind Agent API", lifespan=lifespan)


@app.post("/chat")
async def chat(query: Query):
    """问答接口，使用Agent模式（非流式，真正异步）"""
    agent = service_manager.agent

    if agent is None:
        return {"answer": "服务未初始化，请检查Agent配置"}

    logger.info(f"收到问题: {query.question}")
    logger.debug(f"具体请求为：{query}")
    logger.info(f"历史消息数量: {len(query.history)}")

    # 使用Agent处理（Agent会自主决定何时使用检索工具）
    logger.info("使用Agent模式（异步非流式）...")
    result = await agent.aexecute(
        question=query.question,
        history=query.history
    )

    return {
        "answer": result.get("answer", ""),
        "agent_mode": True,
        "error": result.get("error")
    }


@app.post("/chat/stream")
async def chat_stream(query: Query):
    """问答接口，使用Agent模式（流式，真正异步）"""
    agent = service_manager.agent

    if agent is None:
        return StreamingResponse(
            single_result_generator("服务未初始化\n"),
            media_type="text/plain"
        )

    logger.info(f"收到问题: {query.question}")
    logger.debug(f"具体请求为：{query}")
    logger.info(f"历史消息数量: {len(query.history)}")

    # 使用Agent处理（Agent会自主决定何时使用检索工具）
    logger.info("使用Agent模式（异步流式）...")
    return StreamingResponse(
        agenerate_agent_stream(agent, query.question, query.history),
        media_type="text/plain"
    )


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "vectordb_initialized": service_manager.vectordb is not None,
        "agent_initialized": service_manager.agent is not None
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

