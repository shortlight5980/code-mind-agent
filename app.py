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
    """Q&A endpoint."""
    vectordb = services.get("vectordb")
    llm = services.get("llm")
    summarizer_llm = services.get("summarizer_llm")
    retrieval_k = services.get("retrieval_k", 7)

    if vectordb is None or llm is None or summarizer_llm is None:
        return {"answer": "Service not initialized, please check if vector database exists"}

    logger.info(f"Received question: {query.question}")

    # 1. Retrieve relevant documents (10 docs)
    docs = vectordb.similarity_search(query.question, k=retrieval_k)

    # 2. Build raw context from retrieved docs (using summarizer module)
    raw_context = build_context(docs)

    # Debug: Log full raw context
    logger.debug("=" * 80)
    logger.debug("📚 Full reference materials (7 docs):")
    logger.debug(raw_context)
    logger.debug("=" * 80)

    # 3. Summarize the raw context (using summarizer module)
    logger.info("Summarizing retrieved documents...")
    summarized_context = summarize_context(query.question, raw_context, summarizer_llm)

    # Debug: Log summarized context
    logger.debug("=" * 80)
    logger.debug("📝 Summarized context:")
    logger.debug(summarized_context)
    logger.debug("=" * 80)

    # 4. Build final prompt with summarized context
    prompt = PROMPT_TEMPLATE.format(context=summarized_context, question=query.question)

    # 5. Call main LLM
    response = llm.invoke(prompt)
    answer = response.content if hasattr(response, 'content') else str(response)

    # Debug: Log model response
    logger.debug("=" * 80)
    logger.debug("🤖 Final model response:")
    logger.debug(answer)
    logger.debug("=" * 80)

    # Log sources (INFO level)
    logger.info("=" * 60)
    logger.info("📎 References (7 docs):")
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
        ]
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "vectordb_initialized": services.get("vectordb") is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
