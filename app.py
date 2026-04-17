import json
import queue
from contextlib import asynccontextmanager
from typing import Dict, Any, AsyncGenerator

import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from utils.logger import get_logger
from services.service_manager import ServiceManager
from rag.context_builder import RAGContextBuilder
from prompts.prompt_manager import PromptManager, PromptScenario, PromptLanguage
from agent.agent import CodeMindAgent

logger = get_logger("app")

# 全局服务管理器实例
service_manager: ServiceManager


class Query(BaseModel):
    question: str




@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan事件处理器，用于服务初始化和清理"""
    global service_manager
    try:
        service_manager = ServiceManager.get_instance()
        service_manager.initialize()
    except Exception as e:
        logger.error(f"初始化失败: {e}")
    yield
    # 关闭时清理
    service_manager.cleanup()
    logger.info("服务已清理")


app = FastAPI(title="CodeMind Agent API", lifespan=lifespan)


async def generate_stream(
    agent: CodeMindAgent,
    question: str,
    docs: list,
    summarizer_llm
) -> AsyncGenerator[str, None]:
    """
    生成流式响应内容

    Args:
        agent: CodeMindAgent实例
        question: 用户问题
        docs: 检索到的文档
        summarizer_llm: 摘要模型

    Yields:
        流式内容块
    """
    # 使用Agent的流式输出

    def process_chunk(chunk):
        message: Dict[str, Any] = {}

        if chunk["type"] == "human":
            return ""

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

        return message

    # 创建一个线程安全的队列，用于传递生成器产出的数据
    data_queue = queue.Queue()

    # 定义一个在独立线程中运行的函数
    def run_sync_generator():
        try:
            for chunk in agent.execute_stream(question, docs, summarizer_llm):
                # 将原始 chunk 放入队列
                data_queue.put(chunk)
        except Exception as e:
            data_queue.put(e)  # 传递异常
        finally:
            data_queue.put(None)  # 结束信号

    # 启动线程
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, run_sync_generator)

    # 异步从队列中拉取数据
    while True:
        # 使用 asyncio.to_thread 非阻塞地等待队列数据
        item = await asyncio.to_thread(data_queue.get)

        if item is None:
            # 发送结束标志，很多前端SSE库靠这个判断结束
            yield "data: [DONE]\n\n"
            break  # 生成器结束

        if isinstance(item, Exception):
            logger.error(f"流式生成失败: {item}")
            yield f"\n[Error] 流式生成失败: {str(item)}\n"
            break

        # 处理 chunk
        message = process_chunk(item)

        if message:
            logger.info("+" * 20)
            logger.info(f"[respons_message] {json.dumps(message, ensure_ascii=False)}")
            logger.info("+" * 20)

            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"



@app.post("/chat")
async def chat(query: Query):
    """问答接口，支持Agent模式（非流式）"""
    vectordb = service_manager.vectordb
    llm = service_manager.llm
    summarizer_llm = service_manager.summarizer_llm
    retrieval_k = service_manager.retrieval_k
    agent_enabled = service_manager.agent_enabled
    agent = service_manager.agent

    if vectordb is None or llm is None or summarizer_llm is None:
        return {"answer": "服务未初始化，请检查向量数据库是否存在"}

    logger.info(f"收到问题: {query.question}")
    logger.info(f"Agent启用: {agent_enabled}")

    # 1. 检索相关文档
    logger.info(f"开始向量数据库检索，数量: {retrieval_k}")
    docs = vectordb.similarity_search(query.question, k=retrieval_k)

    # 2. 检查是否使用Agent
    if agent_enabled and agent is not None:
        logger.info("使用Agent模式（非流式）...")
        result = agent.execute(
            question=query.question,
            raw_docs=docs,
            summarizer_llm=summarizer_llm
        )

        # 记录来源信息（INFO级别）
        context_builder = RAGContextBuilder(summarizer_llm)
        context_builder.log_sources_info(docs)

        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "agent_mode": True,
            "summarized_context": result.get("summarized_context", ""),
            "error": result.get("error")
        }
    else:
        # 回退到原始模式（非Agent）
        logger.info("使用原始模式（Agent禁用）...")

        # 使用RAGContextBuilder构建上下文
        context_builder = RAGContextBuilder(summarizer_llm)
        processed_context = context_builder.build_context(
            docs=docs,
            question=query.question,
            enable_summarization=True
        )

        # 记录调试信息
        context_builder.log_context_debug(docs, processed_context)

        # 使用提示词管理器获取提示词
        prompt_manager = PromptManager.get_instance()
        prompt_template = prompt_manager.get_prompt(
            scenario=PromptScenario.GENERAL_QA,
            language=PromptLanguage.ZH_CN
        )
        prompt = prompt_template.format(
            context=processed_context.summarized_context,
            question=query.question
        )

        # 调试：输出最终提示词
        logger.debug("=" * 80)
        logger.debug(" 发送给主模型的最终提示词:")
        logger.debug(prompt)
        logger.debug("=" * 80)

        # 调用主LLM
        logger.info("调用主LLM...")
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)

        # 调试：输出模型响应
        logger.debug("=" * 80)
        logger.debug(" 主模型响应:")
        logger.debug(answer)
        logger.debug("=" * 80)

        # 记录来源信息（INFO级别）
        context_builder.log_sources_info(docs)

        return {
            "answer": answer,
            "sources": processed_context.sources,
            "agent_mode": False,
            "summarized_context": processed_context.summarized_context
        }


@app.post("/chat/stream")
async def chat_stream(query: Query):
    """问答接口，支持Agent模式（流式）"""
    vectordb = service_manager.vectordb
    llm = service_manager.llm
    summarizer_llm = service_manager.summarizer_llm
    retrieval_k = service_manager.retrieval_k
    agent_enabled = service_manager.agent_enabled
    agent = service_manager.agent

    if vectordb is None or summarizer_llm is None:
        return StreamingResponse(
            iter(["服务未初始化\n"]),
            media_type="text/plain"
        )

    logger.info(f"收到流式问题: {query.question}")
    logger.info(f"Agent启用: {agent_enabled}")

    # 1. 检索相关文档
    logger.info(f"开始向量数据库检索，数量: {retrieval_k}")
    docs = vectordb.similarity_search(query.question, k=retrieval_k)

    # 使用RAGContextBuilder记录调试信息
    context_builder = RAGContextBuilder(summarizer_llm)

    # 记录来源信息（INFO级别）
    context_builder.log_sources_info(docs)

    # 2. 检查是否使用Agent
    if agent_enabled and agent is not None:
        logger.info("使用Agent模式（流式）...")
        return StreamingResponse(
            generate_stream(agent, query.question, docs, summarizer_llm),
            media_type="text/plain"
        )
    else:
        # 回退到原始模式（非Agent，为简单起见使用非流式）
        logger.info("Agent不可用，使用非流式回退...")

        # 使用RAGContextBuilder构建上下文
        processed_context = context_builder.build_context(
            docs=docs,
            question=query.question,
            enable_summarization=True
        )

        # 使用提示词管理器获取提示词
        prompt_manager = PromptManager.get_instance()
        prompt_template = prompt_manager.get_prompt(
            scenario=PromptScenario.GENERAL_QA,
            language=PromptLanguage.ZH_CN
        )
        prompt = prompt_template.format(
            context=processed_context.summarized_context,
            question=query.question
        )

        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)

        return StreamingResponse(
            iter([answer]),
            media_type="text/plain"
        )


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "vectordb_initialized": service_manager.vectordb is not None,
        "agent_enabled": service_manager.agent_enabled,
        "agent_initialized": service_manager.agent is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
