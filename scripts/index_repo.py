import os
import re
import argparse
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import DashScopeEmbeddings


def split_by_code_blocks(content: str, file_ext: str):
    """按函数/类边界粗分割代码"""
    patterns = {
        ".py": r"\n(?=def |class )",
        ".java": r"\n(?=public |private |protected |class |interface )",
        ".js": r"\n(?=function |class |const |let |var )",
        ".ts": r"\n(?=function |class |interface |export )",
        ".go": r"\n(?=func |type |struct )",
    }
    pattern = patterns.get(file_ext)
    if pattern:
        return re.split(pattern, content)
    else:
        return [content]


def index_repo(repo_path: str, persist_dir: str = "./chroma_db"):
    """索引代码仓库到向量库"""
    load_dotenv()

    all_chunks = []
    supported_exts = ('.py', '.java', '.js', '.ts', '.go', '.md')

    # 要排除的目录列表
    exclude_dirs = {
        'node_modules',
        '__pycache__',
        '.git',
        '.svn',
        '.hg',
        'dist',
        'build',
        'target',
        'venv',
        '.venv',
        'env',
        '.env',
        'vendor',
        'bower_components'
    }

    print(f"🔍 开始扫描仓库: {repo_path}")

    for root, _, files in os.walk(repo_path):
        # 检查路径中是否包含要排除的目录
        path_parts = root.replace('\\', '/').split('/')
        if any(part in exclude_dirs for part in path_parts):
            continue

        for file in files:
            if file.endswith(supported_exts):
                file_path = os.path.join(root, file)
                print(f"  处理文件: {file_path}")

                try:
                    loader = TextLoader(file_path, encoding='utf-8')
                    docs = loader.load()

                    # 先按函数/类边界粗分
                    for doc in docs:
                        ext = os.path.splitext(file)[1]
                        blocks = split_by_code_blocks(doc.page_content, ext)
                        for block in blocks:
                            if block.strip():
                                # 细粒度切分（保持上下文重叠）
                                splitter = RecursiveCharacterTextSplitter(
                                    chunk_size=800,
                                    chunk_overlap=100
                                )
                                chunks = splitter.create_documents(
                                    [block],
                                    metadatas=[{"source": file_path}]
                                )
                                all_chunks.extend(chunks)
                except Exception as e:
                    print(f"⚠️  跳过文件 {file_path}: {e}")

    if not all_chunks:
        print("❌ 没有找到可索引的代码文件")
        return

    print(f"📦 共 {len(all_chunks)} 个代码片段，开始向量化...")

    # 使用阿里云百炼嵌入模型
    embeddings = DashScopeEmbeddings(
        model="text-embedding-v3",
    )

    vectordb = Chroma.from_documents(
        all_chunks,
        embeddings,
        persist_directory=persist_dir
    )
    vectordb.persist()

    print(f"✅ 索引完成！共 {len(all_chunks)} 个片段已保存到 {persist_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="索引 Git 仓库到向量库")
    parser.add_argument("repo_path", help="要索引的仓库路径")
    parser.add_argument("--persist-dir", default="./chroma_db", help="向量库保存目录")
    args = parser.parse_args()

    index_repo(args.repo_path, args.persist_dir)
