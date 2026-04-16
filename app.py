import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models import ChatTongyi

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CodeMind Agent API")

# 全局变量，延迟初始化
vectordb = None
llm = None


def init_services():
    """初始化向量库和 LLM 服务"""
    global vectordb, llm

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

    logger.info(f"正在加载向量库: {persist_dir}")

    # 初始化嵌入模型
    embeddings = DashScopeEmbeddings(
        model="text-embedding-v3",
    )

    # 加载向量库
    vectordb = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )

    # 初始化 LLM（阿里云百炼 qwen-max）
    llm = ChatTongyi(
        model="qwen-max",
        temperature=0.1,
    )

    logger.info("服务初始化完成")


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化服务"""
    try:
        init_services()
    except Exception as e:
        logger.error(f"初始化失败: {e}")


class Query(BaseModel):
    question: str


@app.post("/chat")
async def chat(query: Query):
    """问答接口"""
    if vectordb is None or llm is None:
        return {"answer": "服务未初始化，请检查向量库是否存在"}

    logger.info(f"收到问题: {query.question}")

    # 1. 检索相关文档
    docs = vectordb.similarity_search(query.question, k=3)

    # 2. 构建 prompt
    context = "\n\n".join([
        f"来源: {doc.metadata.get('source', 'unknown')}\n内容:\n{doc.page_content}"
        for doc in docs
    ])

    prompt = f"""你是一个代码助手，请根据以下上下文回答问题。

上下文:
{context}

问题: {query.question}

请给出详细的回答。"""

    # 3. 调用 LLM
    response = llm.invoke(prompt)
    answer = response.content if hasattr(response, 'content') else str(response)

    # 打印引用来源
    logger.info("=" * 60)
    logger.info("📎 引用来源:")
    for i, doc in enumerate(docs):
        src = doc.metadata.get("source", "unknown")
        snippet = doc.page_content[:150].replace("\n", " ")
        logger.info(f"  [{i+1}] {src}")
        logger.info(f"       片段: {snippet}...")
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
    """健康检查"""
    return {"status": "ok", "vectordb_initialized": vectordb is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
