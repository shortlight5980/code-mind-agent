from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import PromptTemplate

from utils.logger import get_logger
from utils.config import Config
from utils.summarizer import build_context, summarize_context, create_summarizer
from agent.agent import create_codemind_agent, run_agent_with_summary

logger = get_logger("app")

# Global state
services: Dict[str, Any] = {}


class Query(BaseModel):
    question: str


# Optimized prompt template
PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["context", "question"],
    template="""你是一个专业的代码助手，精通软件工程和代码分析。请根据提供的代码上下文，准确、详细地回答用户的问题。

## 上下文信息
{context}

## 用户问题
{question}

## 回答要求
1. 如果答案在上下文中，请直接引用相关代码片段并给出详细解释
2. 如果上下文不够充分，请基于已有信息给出合理的分析和建议
3. 回答要条理清晰，分点说明
4. 对于代码相关问题，给出具体的代码示例或修改建议
5. 请用中文回答

现在开始回答："""
)


def init_services():
    """Initialize vector database and LLM services."""
    Config.load()

    persist_dir = Config.get("chroma.persist_dir", "./chroma_db")
    retrieval_k = Config.get("chroma.retrieval_k", 7)
    embedding_model = Config.get("embeddings.model", "text-embedding-v3")
    llm_model = Config.get("llm.model", "qwen-max")
    llm_temperature = Config.get("llm.temperature", 0.1)
    summarizer_model = Config.get("summarizer.model", "qwen-max")
    summarizer_temperature = Config.get("summarizer.temperature", 0.1)
    agent_enabled = Config.get("agent.enabled", True)

    logger.info(f"Loading vector database: {persist_dir}")

    # Initialize embeddings
    embeddings = DashScopeEmbeddings(
        model=embedding_model,
    )

    # Load vector database
    vectordb = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )

    # Initialize main LLM (Alibaba Bailian qwen-max)
    llm = ChatTongyi(
        model=llm_model,
        temperature=llm_temperature,
    )

    # Use summarizer module to create summarizer LLM
    summarizer_llm = create_summarizer(
        model=summarizer_model,
        temperature=summarizer_temperature
    )

    services["vectordb"] = vectordb
    services["llm"] = llm
    services["summarizer_llm"] = summarizer_llm
    services["retrieval_k"] = retrieval_k

    # Initialize Agent if enabled
    if agent_enabled:
        logger.info("Initializing CodeMind Agent...")
        try:
            agent = create_codemind_agent()
            services["agent"] = agent
            services["agent_enabled"] = True
            logger.info("CodeMind Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Agent: {e}")
            services["agent_enabled"] = False
    else:
        services["agent_enabled"] = False
        logger.info("Agent is disabled in config")

    logger.info("Services initialized successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event handler for service initialization."""
    try:
        init_services()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
    yield
    # Cleanup on shutdown
    services.clear()
    logger.info("Services cleaned up")


app = FastAPI(title="CodeMind Agent API", lifespan=lifespan)


@app.post("/chat")
async def chat(query: Query):
    """Q&A endpoint with Agent support."""
    vectordb = services.get("vectordb")
    llm = services.get("llm")
    summarizer_llm = services.get("summarizer_llm")
    retrieval_k = services.get("retrieval_k", 7)
    agent_enabled = services.get("agent_enabled", False)
    agent = services.get("agent")

    if vectordb is None or llm is None or summarizer_llm is None:
        return {"answer": "Service not initialized, please check if vector database exists"}

    logger.info(f"Received question: {query.question}")
    logger.info(f"Agent enabled: {agent_enabled}")

    # 1. Retrieve relevant documents
    logger.info(f"开始检索向量库，检索数量: {retrieval_k}")
    docs = vectordb.similarity_search(query.question, k=retrieval_k)

    # Debug: 输出向量库检索完整结果
    logger.debug("=" * 80)
    logger.debug("📚 向量库检索完整结果:")
    for i, doc in enumerate(docs):
        src = doc.metadata.get("source", "unknown")
        logger.debug(f"  [{i+1}] 来源: {src}")
        logger.debug(f"  内容:\n{doc.page_content}")
        logger.debug("-" * 60)
    logger.debug("=" * 80)

    # 2. Check if Agent should be used
    if agent_enabled and agent is not None:
        logger.info("Using Agent mode...")
        result = run_agent_with_summary(
            question=query.question,
            agent=agent,
            raw_docs=docs,
            summarizer_llm=summarizer_llm
        )

        # Log sources (INFO level)
        logger.info("=" * 60)
        logger.info("📎 References (Agent mode):")
        for i, doc in enumerate(docs):
            src = doc.metadata.get("source", "unknown")
            snippet = doc.page_content[:150].replace("\n", " ")
            logger.info(f"  [{i+1}] {src}")
            logger.info(f"       Snippet: {snippet}...")
        logger.info("=" * 60)

        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "agent_mode": True,
            "summarized_context": result.get("summarized_context", ""),
            "error": result.get("error")
        }
    else:
        # Fallback to original mode (non-Agent)
        logger.info("Using original mode (Agent disabled)...")

        # 2. Build raw context from retrieved docs (using summarizer module)
        raw_context = build_context(docs)

        # Debug: Log full raw context
        logger.debug("=" * 80)
        logger.debug("📚 完整参考材料 (raw_context):")
        logger.debug(raw_context)
        logger.debug("=" * 80)

        # 3. Summarize the raw context (using summarizer module)
        logger.info("Summarizing retrieved documents...")
        summarized_context = summarize_context(query.question, raw_context, summarizer_llm)

        # Debug: Log summarized context
        logger.debug("=" * 80)
        logger.debug("📝 总结后的上下文 (summarized_context):")
        logger.debug(summarized_context)
        logger.debug("=" * 80)

        # 4. Build final prompt with summarized context
        prompt = PROMPT_TEMPLATE.format(context=summarized_context, question=query.question)

        # Debug: 输出最终提示词
        logger.debug("=" * 80)
        logger.debug("💬 发送给主模型的最终提示词:")
        logger.debug(prompt)
        logger.debug("=" * 80)

        # 5. Call main LLM
        logger.info("正在调用主 LLM...")
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)

        # Debug: 输出模型返回结果
        logger.debug("=" * 80)
        logger.debug("🤖 主模型返回结果:")
        logger.debug(answer)
        logger.debug("=" * 80)

        # Log sources (INFO level)
        logger.info("=" * 60)
        logger.info("📎 References:")
        for i, doc in enumerate(docs):
            src = doc.metadata.get("source", "unknown")
            snippet = doc.page_content[:150].replace("\n", " ")
            logger.info(f"  [{i+1}] {src}")
            logger.info(f"       Snippet: {snippet}...")
        logger.info("=" * 60)

        return {
            "answer": answer,
            "sources": [
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "content": doc.page_content
                }
                for doc in docs
            ],
            "agent_mode": False,
            "summarized_context": summarized_context
        }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "vectordb_initialized": services.get("vectordb") is not None,
        "agent_enabled": services.get("agent_enabled", False),
        "agent_initialized": services.get("agent") is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
