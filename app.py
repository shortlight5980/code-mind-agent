import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from utils.logger import get_logger
from services.service_manager import ServiceManager
from rag.context_builder import RAGContextBuilder
from agent.streaming import agenerate_agent_stream

logger = get_logger("app")

# 全局服务管理器实例
service_manager: ServiceManager


class Query(BaseModel):
    question: str


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
    vectordb = service_manager.vectordb
    agent = service_manager.agent
    retrieval_k = service_manager.retrieval_k

    if vectordb is None or agent is None:
        return {"answer": "服务未初始化，请检查向量数据库是否存在"}

    logger.info(f"收到问题: {query.question}")

    # 1. 检索相关文档（异步）
    logger.info(f"开始向量数据库检索 (异步)，数量: {retrieval_k}")
    docs = await vectordb.asimilarity_search(query.question, k=retrieval_k)

    # 2. 使用Agent处理
    logger.info("使用Agent模式（异步非流式）...")
    result = await agent.aexecute(
        question=query.question,
        raw_docs=docs
    )

    # 记录来源信息（INFO级别）
    context_builder = RAGContextBuilder(service_manager.summarizer_llm)
    context_builder.log_sources_info(docs)

    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "agent_mode": True,
        "summarized_context": result.get("summarized_context", ""),
        "error": result.get("error")
    }


@app.post("/chat/stream")
async def chat_stream(query: Query):
    """问答接口，使用Agent模式（流式，真正异步）"""
    vectordb = service_manager.vectordb
    agent = service_manager.agent
    retrieval_k = service_manager.retrieval_k

    if vectordb is None or agent is None:
        return StreamingResponse(
            single_result_generator("服务未初始化\n"),
            media_type="text/plain"
        )

    logger.info(f"收到流式问题: {query.question}")

    # 1. 检索相关文档（异步）
    logger.info(f"开始向量数据库检索 (异步)，数量: {retrieval_k}")
    docs = await vectordb.asimilarity_search(query.question, k=retrieval_k)

    # 使用RAGContextBuilder记录调试信息
    context_builder = RAGContextBuilder(service_manager.summarizer_llm)

    # 记录来源信息（INFO级别）
    context_builder.log_sources_info(docs)

    # 2. 使用Agent处理
    logger.info("使用Agent模式（异步流式）...")
    return StreamingResponse(
        agenerate_agent_stream(agent, query.question, docs),
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
