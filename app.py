from contextlib import asynccontextmanager
from typing import Dict, Any, AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import PromptTemplate

from utils.logger import get_logger
from utils.config import Config
from utils.summarizer import build_context, summarize_context, create_summarizer
from agent.agent import CodeMindAgent

logger = get_logger("app")

# Global state
services: Dict[str, Any] = {}


class Query(BaseModel):
    question: str


# Optimized prompt template
PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are a professional code assistant, proficient in software engineering and code anal
         ysis. Please answer the user's questions accurately and in detail based on the provided code context.

 ## Context Information
      {context}
      
      ## User Question
      {question}
      
      ## Answer Requirements
      1. If the answer is in the context, please directly quote the relevant code snippets and provide detail
      ed explanations
      2. If the context is insufficient, please provide reasonable analysis and suggestions based on existing
       information
      3. The answer should be well-organized and explained in points
      4. For code-related questions, provide specific code examples or modification suggestions
      5. Please answer in Chinese
      
      Now begin answering:"""
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
            agent = CodeMindAgent()
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


async def generate_stream(
    agent: CodeMindAgent,
    question: str,
    docs: list,
    summarizer_llm: ChatTongyi
) -> AsyncGenerator[str, None]:
    """
    Generate streaming response content.

    Args:
        agent: CodeMindAgent instance
        question: User question
        docs: Retrieved documents
        summarizer_llm: Summarizer model

    Yields:
        Streaming content chunks
    """
    try:
        # Use Agent's streaming output
        for chunk in agent.execute_stream(
            question=question,
            raw_docs=docs,
            summarizer_llm=summarizer_llm
        ):
            yield chunk
    except Exception as e:
        logger.error(f"Stream generation failed: {e}")
        yield f"\n[Error] Streaming failed: {str(e)}\n"


@app.post("/chat")
async def chat(query: Query):
    """Q&A endpoint with Agent support (non-streaming)."""
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
    logger.info(f"Starting vector DB retrieval, count: {retrieval_k}")
    docs = vectordb.similarity_search(query.question, k=retrieval_k)

    # Debug: Output complete vector DB retrieval results
    logger.debug("=" * 80)
    logger.debug(" Vector DB complete results:")
    for i, doc in enumerate(docs):
        src = doc.metadata.get("source", "unknown")
        logger.debug(f"  [{i+1}] Source: {src}")
        logger.debug(f"  Content:\n{doc.page_content}")
        logger.debug("-" * 60)
    logger.debug("=" * 80)

    # 2. Check if Agent should be used
    if agent_enabled and agent is not None:
        logger.info("Using Agent mode (non-streaming)...")
        result = agent.execute(
            question=query.question,
            raw_docs=docs,
            summarizer_llm=summarizer_llm
        )

        # Log sources (INFO level)
        logger.info("=" * 60)
        logger.info(" References (Agent mode):")
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
        logger.debug(" Full reference material (raw_context):")
        logger.debug(raw_context)
        logger.debug("=" * 80)

        # 3. Summarize the raw context (using summarizer module)
        logger.info("Summarizing retrieved documents...")
        summarized_context = summarize_context(query.question, raw_context, summarizer_llm)

        # Debug: Log summarized context
        logger.debug("=" * 80)
        logger.debug(" Summarized context:")
        logger.debug(summarized_context)
        logger.debug("=" * 80)

        # 4. Build final prompt with summarized context
        prompt = PROMPT_TEMPLATE.format(context=summarized_context, question=query.question)

        # Debug: Output final prompt
        logger.debug("=" * 80)
        logger.debug(" Final prompt sent to main model:")
        logger.debug(prompt)
        logger.debug("=" * 80)

        # 5. Call main LLM
        logger.info("Calling main LLM...")
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)

        # Debug: Output model response
        logger.debug("=" * 80)
        logger.debug(" Main model response:")
        logger.debug(answer)
        logger.debug("=" * 80)

        # Log sources (INFO level)
        logger.info("=" * 60)
        logger.info(" References:")
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


@app.post("/chat/stream")
async def chat_stream(query: Query):
    """Q&A endpoint with Agent support (streaming)."""
    vectordb = services.get("vectordb")
    summarizer_llm = services.get("summarizer_llm")
    retrieval_k = services.get("retrieval_k", 7)
    agent_enabled = services.get("agent_enabled", False)
    agent = services.get("agent")

    if vectordb is None or summarizer_llm is None:
        return StreamingResponse(
            iter(["Service not initialized\n"]),
            media_type="text/plain"
        )

    logger.info(f"Received streaming question: {query.question}")
    logger.info(f"Agent enabled: {agent_enabled}")

    # 1. Retrieve relevant documents
    logger.info(f"Starting vector DB retrieval, count: {retrieval_k}")
    docs = vectordb.similarity_search(query.question, k=retrieval_k)

    # Debug: Output complete vector DB retrieval results
    logger.debug("=" * 80)
    logger.debug(" Vector DB complete results:")
    for i, doc in enumerate(docs):
        src = doc.metadata.get("source", "unknown")
        logger.debug(f"  [{i+1}] Source: {src}")
        logger.debug(f"  Content:\n{doc.page_content}")
        logger.debug("-" * 60)
    logger.debug("=" * 80)

    # Log sources (INFO level)
    logger.info("=" * 60)
    logger.info(" References (streaming):")
    for i, doc in enumerate(docs):
        src = doc.metadata.get("source", "unknown")
        snippet = doc.page_content[:150].replace("\n", " ")
        logger.info(f"  [{i+1}] {src}")
        logger.info(f"       Snippet: {snippet}...")
    logger.info("=" * 60)

    # 2. Check if Agent should be used
    if agent_enabled and agent is not None:
        logger.info("Using Agent mode (streaming)...")
        return StreamingResponse(
            generate_stream(agent, query.question, docs, summarizer_llm),
            media_type="text/plain"
        )
    else:
        # Fallback to original mode (non-Agent, non-streaming for simplicity)
        logger.info("Agent not available, using non-streaming fallback...")

        # Build context and get answer
        raw_context = build_context(docs)
        summarized_context = summarize_context(query.question, raw_context, summarizer_llm)
        prompt = PROMPT_TEMPLATE.format(context=summarized_context, question=query.question)

        from langchain_community.chat_models import ChatTongyi
        llm = ChatTongyi(
            model=Config.get("llm.model", "qwen-max"),
            temperature=Config.get("llm.temperature", 0.1),
        )
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)

        return StreamingResponse(
            iter([answer]),
            media_type="text/plain"
        )


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
