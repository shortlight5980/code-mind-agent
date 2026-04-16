# 03. RAG 原理入门

RAG（Retrieval-Augmented Generation，检索增强生成）是本项目的核心技术。本文档将用通俗易懂的方式解释 RAG 的原理。

## 为什么需要 RAG？

### 大模型的局限性

大语言模型（LLM）虽然很强大，但它有两个关键问题：

1. **知识截止日期**：LLM 的训练数据有截止日期，不知道截止日期之后发生的事
2. **没有私有知识**：LLM 不知道你公司的代码库、你个人的文档等私有内容

### 传统做法的问题

如果直接把所有代码都发给 LLM，会遇到：

- ❌ **上下文长度限制**：LLM 能接收的文本长度有限（例如 Qwen-Max 是 8K）
- ❌ **成本高**：Token 是按长度计费的，长文本很贵
- ❌ **效率低**：无关代码会干扰 LLM，导致回答质量下降

### RAG 的解决方案

RAG 的核心思想：**不要把所有内容都给 LLM，只给它需要的那部分！**

---

## RAG 是什么？

RAG 由两个阶段组成：

| 阶段 | 英文 | 说明 |
|------|------|------|
| **检索** | Retrieval | 从知识库中找到与问题相关的内容 |
| **增强生成** | Augmented Generation | 把检索到的内容和问题一起发给 LLM，生成回答 |

---

## RAG 完整流程详解

### 阶段一：索引（离线阶段）

这一步只需要做一次，就是把代码库"存入"向量数据库。

```
代码文件
    ↓
按函数/类分割成小片段
    ↓
用 Embedding 模型把每个片段转换成向量
    ↓
存入向量数据库（Chroma）
```

#### 为什么要分割代码？

因为：
1. 整个文件太长，不适合转换成单个向量
2. 我们需要精确找到相关的代码片段，而不是整个文件

#### 如何分割？

我们的 `index_repo.py` 使用了**智能分割策略**：

1. **粗分割**：先按函数/类边界分割（防止把一个函数切两半）
2. **细分割**：再用 `RecursiveCharacterTextSplitter` 切分成合适大小

```python
# 伪代码示例
code = """
def func1():
    ...
    
class MyClass:
    ...
"""

# 粗分割结果:
# [ "def func1():...", "class MyClass:..." ]

# 再细分割成更小的块（如果有必要）
```

---

### 阶段二：检索（在线阶段）

用户提问时执行：

```
用户问题
    ↓
用同一个 Embedding 模型把问题转换成向量
    ↓
在向量数据库中搜索最相似的 Top-K 个代码片段
    ↓
得到相关代码片段
```

#### 相似度搜索是怎么工作的？

还记得向量是一组数字吗？我们可以用**余弦相似度**来衡量两个向量的相似程度：

```
相似度 = 1   → 完全相同
相似度 = 0.8 → 很相似
相似度 = 0   → 不相关
```

向量数据库会快速计算问题向量和所有代码片段向量的相似度，返回最相似的几个。

---

### 阶段三：生成（在线阶段）

```
用户问题 + 检索到的代码片段
    ↓
组装成 Prompt
    ↓
发给 LLM
    ↓
得到回答
```

#### Prompt 示例

```
你是一个代码助手，请根据以下上下文回答问题。

上下文:
来源: C:\project\app.py
内容:
def main():
    """项目入口函数"""
    init_db()
    start_server()

来源: C:\project\database.py
内容:
def init_db():
    """初始化数据库"""
    create_tables()

问题: 这个项目的启动流程是什么？

请给出详细的回答。
```

LLM 看到这个 Prompt 后，就会基于提供的代码片段来回答。

---

## RAG 的优势

| 优势 | 说明 |
|------|------|
| ✅ **减少幻觉** | LLM 基于提供的事实回答，不容易编造 |
| ✅ **可追溯** | 可以看到答案来自哪些文件 |
| ✅ **成本低** | 只发送相关片段，节省 Token |
| ✅ **知识更新** | 只需更新向量数据库，不用重新训练 LLM |

---

## 本项目中的 RAG 实现

让我们看看代码中哪里对应 RAG 的各个部分：

### 索引阶段 → `scripts/index_repo.py`

```python
# 1. 遍历代码文件
for root, _, files in os.walk(repo_path):
    for file in files:
        # 2. 按函数/类粗分割
        blocks = split_by_code_blocks(content, ext)
        # 3. 细分割
        chunks = splitter.create_documents([block], ...)
        # 4. 向量化并入库
        vectordb = Chroma.from_documents(all_chunks, embeddings, ...)
```

### 检索 + 生成阶段 → `app.py`

```python
@app.post("/chat")
async def chat(query: Query):
    # 1. 检索：找到相关代码片段
    docs = vectordb.similarity_search(query.question, k=3)
    
    # 2. 构建 Prompt
    context = "\n\n".join([f"来源: {doc.metadata['source']}\n内容:\n{doc.page_content}" for doc in docs])
    prompt = f"你是一个代码助手...\n上下文:\n{context}\n问题: {query.question}"
    
    # 3. 生成：调用 LLM
    response = llm.invoke(prompt)
    
    return {"answer": response.content, "sources": docs}
```

---

## 常见问题

### Q: 为什么不直接用 Fine-tuning（微调）？

A: 微调是用你的数据重新训练 LLM 的一部分。对比：

| | RAG | Fine-tuning |
|---|-----|-------------|
| 成本 | 低（只需向量化） | 高（需要 GPU、大量数据） |
| 更新 | 快（重新索引即可） | 慢（重新训练） |
| 可追溯 | ✅ 知道来源 | ❌ 不知道 |
| 适用场景 | 问答、知识库 | 风格迁移、特定任务 |

对于代码问答这种场景，RAG 更合适！

### Q: Top-K 选多少合适？

A: 这是个经验值：
- K=1~2：信息可能不够
- K=3~5：本项目用的是 3，平衡了信息量和上下文长度
- K>10：可能包含无关信息，且容易超过上下文限制

---

## 下一步

现在你理解了 RAG 原理，接下来阅读 [04-代码结构解析.md](./04-代码结构解析.md)，逐行理解我们的代码！
