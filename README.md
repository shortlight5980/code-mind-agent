# CodeMind Agent

基于 RAG (检索增强生成) 的代码仓库智能问答系统，帮助开发者快速理解和查询代码库。

## 功能特性

### 🤖 智能 Agent 模式
- 自主决定何时使用检索工具
- 支持流式和非流式输出
- 集成多种代码分析工具

### 🔍 智能代码检索
- **混合检索**: 语义向量检索 + BM25 关键词检索双路并行
- **RRF 融合**: 使用 Reciprocal Rank Fusion 算法智能融合两路结果
- **标识符增强**: 可选对查询中的代码标识符进行匹配增强
- **三种模式**: 支持纯向量、纯 BM25、混合检索三种模式可配置
- **支持代码和文档分开检索**: 使用阿里云 `text-embedding-v4` 模型

### ✂️ 智能代码切分
- **Python**: 基于 AST 的类/函数级别切分
- **多语言 AST 支持**: 基于 Tree-sitter 的语法感知切分
  - 支持: JavaScript, TypeScript, JSX, TSX, Java, Go, Rust, C, C++
  - 按类/函数结构切分，保留完整语法单元
  - 自动降级到正则模式切分（Tree-sitter 不可用时）
- 保留完整语法结构，避免破坏代码语义

### 🔄 查询改写 (Query Rewriting)
- **关键词提取**: 从用户问题中提取核心关键词
- **回答推测**: 基于问题推测可能的答案方向
- **混合检索增强**: 将推测答案+关键词用于检索，提高命中率
- **可配置模型**: 使用独立的 query_rewriting 模型

### 📝 上下文总结层
- 检索结果智能总结
- 减少 Token 消耗
- 聚焦相关信息

### 🛡️ 安全机制
- 路径白名单验证
- 敏感文件保护
- 命令白名单控制

## 快速开始

### 环境准备

```bash
# 安装依赖
pip install -r requirements.txt
```

### 配置

1. **环境变量**：复制示例文件并填入 API Key
```bash
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

2. **仓库配置**：在 `config.yml` 中设置要索引的仓库路径
```yaml
repo:
  path: "/path/to/your/git/repo"
```

### 索引代码库

```bash
python scripts/index_repo.py
```

### 启动服务

```bash
python app.py
# 或使用 uvicorn
uvicorn app:app --reload
```

### API 使用

服务默认运行在 `http://localhost:8000`

#### 方式一：Swagger UI (推荐)

打开浏览器访问 `http://localhost:8000/docs` 直接在页面上测试接口。

#### 方式二：Python Requests

```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "question": "这个项目的主要功能是什么？",
        "history": []
    }
)
result = response.json()
print(result["answer"])
```

#### 方式三：流式接口

```python
import requests

response = requests.post(
    "http://localhost:8000/chat/stream",
    json={
        "question": "解释一下项目架构",
        "history": []
    },
    stream=True
)

for chunk in response.iter_content(chunk_size=None):
    if chunk:
        print(chunk.decode(), end='')
```

## 项目结构

```
CodeMindAgent/
├── agent/                    # Agent 核心模块
│   ├── agent.py             # CodeMind Agent 主类
│   ├── security.py          # 安全检查模块
│   ├── streaming.py         # 流式输出处理
│   └── tools/               # Agent 工具集
│       ├── read_file.py     # 读取文件工具
│       ├── search_code.py   # 代码搜索工具
│       ├── run_command.py   # 命令执行工具
│       └── retrieve_and_summarize.py  # 检索总结工具
├── prompts/                 # 提示词管理
│   └── prompt_manager.py    # 提示词管理器
├── rag/                     # RAG 相关模块
│   └── context_builder.py   # 上下文构建器
├── scripts/                 # 脚本工具
│   ├── index_repo.py        # 仓库索引脚本
│   └── delete_by_file_path.py  # 删除索引脚本
├── services/                # 服务管理
│   └── service_manager.py   # 单例服务管理器
├── utils/                   # 工具模块
│   ├── config.py            # 配置管理
│   ├── logger.py            # 日志工具
│   ├── summarizer.py        # 总结模块
│   ├── query_rewriting.py   # 查询改写模块
│   ├── bm25_index.py        # BM25 关键词索引
│   └── fusion.py            # 结果融合模块 (RRF)
├── app.py                   # FastAPI 主应用
├── config.yml               # 配置文件
└── requirements.txt         # 依赖列表
```

## 配置说明

### config.yml 配置项

```yaml
chroma:
  persist_dir: "./chroma_db"          # 向量数据库存储位置
  chunk_size:
    doc: 800                          # 文档切分大小 (字符)
    code: 2000                        # 代码切分大小 (字符)
  chunk_overlap: 100                  # 切分重叠大小
  retrieval_k:
    docs: 5                           # 向量检索文档数量
    codes: 10                         # 向量检索代码数量

bm25:
  persist_path: "./bm25_index/index.pkl"  # BM25 索引存储位置
  retrieval_k:
    docs: 10                          # BM25 检索文档数量
    codes: 20                         # BM25 检索代码数量

retrieval:
  mode: "hybrid"                      # 检索模式: vector / bm25 / hybrid
  fusion: "rrf"                       # 融合算法: rrf (当前仅支持 RRF)
  rrf_k: 60                           # RRF 算法 k 参数 (默认 60)
  identifier_boost: 0.01              # 标识符匹配增强权重 (0 表示禁用)

repo:
  path: "/path/to/repo"               # 被索引仓库路径

embeddings:
  model: "text-embedding-v4"          # 嵌入模型

llm:
  model: "qwen-max"                   # 主 LLM 模型
  temperature: 0.1

summarizer:
  model: "qwen-turbo"                 # 总结模型
  temperature: 0.1

query_rewriting:
  model: "qwen-turbo"                 # 查询改写模型
  temperature: 0.1

splitting:
  max_class_length: 3000              # Python 类最大长度 (超过会拆分)

agent:
  enabled: true
  model: "qwen-max"
  allowed_dirs: ["."]                 # 允许访问的目录
  blocked_files:                      # 禁止访问的文件模式
    - ".env"
    - "*.key"
  allowed_commands:                   # 允许执行的命令
    - "ls"
    - "cat"
    - "grep"
    - "git"
```

## Agent 可用工具

### 1. RetrieveAndSummarize
根据用户问题从代码库中检索相关文档并进行总结提炼。这是获取代码库上下文的首选工具。

### 2. ReadFile
读取指定文件内容，支持按行号范围读取。

### 3. SearchCode
在代码库中搜索关键词或正则表达式。

### 4. RunCommand
执行只读 shell 命令（如 ls, cat, grep, git 等）。

## 核心技术

### RAG 流程
```
用户问题 → 查询改写 → 混合检索 → 结果融合 → 结果总结 → Agent 回答
           ↑    ↓          ↓
    关键词提取 + 回答推测  ├─ 向量检索 (Chroma)
           ↑                └─ BM25 关键词检索
      代码/文档切分 → ├─ 向量化 → Chroma 存储
                      └─ 构建 BM25 索引
```

### 混合检索策略
- **双路检索**: 向量检索 + BM25 关键词检索并行执行
- **RRF 融合**: 使用 Reciprocal Rank Fusion 算法融合两路结果
- **分开处理**: doc 和 code 两类文档分开检索、分开融合，保证比例
- **可配置**: 支持 `vector` / `bm25` / `hybrid` 三种模式切换

#### RRF (Reciprocal Rank Fusion) 算法
- 对每个结果列表，按排名计算分数: `score = 1 / (k + rank)`
- 同一文档在多个列表中的分数累加
- 按最终分数重新排序
- 默认 `k=60` (经验值)

### 查询改写流程
```
用户问题
   ↓
┌─────────────────────────────────┐
│  1. 关键词提取                  │
│     aget_query_key_words()     │
│     提取核心技术术语           │
└─────────────────────────────────┘
   ↓
┌─────────────────────────────────┐
│  2. 回答推测                    │
│     aget_query_answer_guess()   │
│     基于问题推测可能的答案      │
└─────────────────────────────────┘
   ↓
┌─────────────────────────────────┐
│  3. 检索文本构建                │
│     temp_question =             │
│       answer_guess +            │
│       "关键词: " + (kw * 3)    │
└─────────────────────────────────┘
   ↓
使用增强文本进行向量检索
```

### 代码切分策略

#### Python (AST 模式)
1. 使用 `ast.parse()` 解析代码
2. 提取顶级类、函数定义
3. 按类/函数边界切分
4. 超大类按方法进一步拆分
5. AST 解析失败时回退到缩进扫描模式

#### 多语言 Tree-sitter AST 模式 (推荐)
- **支持语言**: JavaScript, TypeScript, JSX, TSX, Java, Go, Rust, C, C++
- **架构**: 统一 `CodeSplitter` 抽象，语言特定实现
- **切分策略**:
  - 按类/接口/结构体切分（语言特定节点类型）
  - 按函数/方法切分
  - 超大类按内部方法进一步拆分
  - 保留非结构代码片段
- **降级机制**: Tree-sitter 不可用时 → RegexCodeSplitter

#### 正则模式切分 (降级方案)
- **Java**: 在 `public`/`private`/`class`/`interface` 前切分
- **JS/TS/JSX/TSX**: 在 `function`/`class`/`const`/`export` 前切分
- **Go**: 在 `func`/`type`/`struct` 前切分
- **Rust**: 在 `fn`/`impl`/`struct`/`enum` 前切分
- **C/C++**: 在函数定义、类/结构体前切分

### 检索策略
- 代码和文档分别检索
- 可配置不同检索数量
- 使用元数据过滤器区分类型

## API 文档

### POST /chat
非流式问答接口

**请求体**:
```json
{
  "question": "用户问题",
  "history": []
}
```

**响应**:
```json
{
  "answer": "AI 回答",
  "agent_mode": true,
  "error": null
}
```

### POST /chat/stream
流式问答接口

**请求体**: 同 `/chat`

**响应**: Server-Sent Events 流

### GET /health
健康检查接口

**响应**:
```json
{
  "status": "ok",
  "vectordb_initialized": true,
  "agent_initialized": true
}
```

## 开发指南

### 本地开发

```bash
# 克隆项目
git clone <repo>
cd CodeMindAgent

# 安装依赖
pip install -r requirements.txt

# 配置
cp .env.example .env
# 编辑 .env 填入 API Key

# 索引当前目录
python scripts/index_repo.py .

# 启动服务
python app.py
```

### 扩展 Agent 工具

在 `agent/tools/` 目录下创建新文件，使用 `@tool` 装饰器定义工具：

```python
from langchain_core.tools import tool

@tool
def MyNewTool(param: str) -> str:
    """工具描述"""
    # 实现逻辑
    return result
```

然后在 `agent/tools/__init__.py` 中导出，并在 `agent/agent.py` 中添加到工具列表。

### 自定义提示词

通过 `PromptManager` 添加自定义提示词：

```python
from prompts.prompt_manager import PromptManager, PromptScenario, PromptLanguage

pm = PromptManager.get_instance()
pm.add_custom_prompt(
    scenario="my_scenario",
    language="zh-CN",
    version="1.0.0",
    template="你的提示词模板 {input}",
    input_variables=["input"],
    description="描述"
)
```

## 常见问题

### Q: 如何更换嵌入模型？
A: 在 `config.yml` 中修改 `embeddings.model` 配置，支持阿里云 DashScope 的所有嵌入模型。

### Q: 索引速度慢怎么办？
A: 可以通过调整 `chroma.chunk_size.code` 和 `splitting.max_class_length` 来改变切分粒度，或者排除不需要的目录/文件。

### Q: 如何支持更多编程语言？
A: 1. 在 `scripts/index_repo.py` 中:
   - 添加到 `LANGUAGE_MAP`、`CLASS_CHUNK_TYPES`、`FUNCTION_CHUNK_TYPES`
   - 或在 `RegexCodeSplitter` 中添加正则模式
2. 推荐使用 Tree-sitter 语法解析器，通过 `TreeSitterCodeSplitter` 实现

### Q: 向量数据库占用空间太大？
A: 可以使用 `scripts/delete_by_file_path.py` 删除不需要的文件索引（会同时删除 Chroma 和 BM25 索引），或者调整切分策略减少 chunk 数量。

### Q: 如何切换检索模式？
A: 在 `config.yml` 中修改 `retrieval.mode` 配置：
- `vector`: 纯向量检索
- `bm25`: 纯 BM25 关键词检索
- `hybrid`: 混合检索（默认）

### Q: BM25 索引是什么？需要手动构建吗？
A: BM25 是传统的关键词检索算法，用于补充语义检索的不足。
- 不需要手动构建：运行 `scripts/index_repo.py` 时会自动构建
- 索引存储在 `bm25.persist_path` 指定的路径
- 删除时会同步删除：`scripts/delete_by_file_path.py` 会同时删除两类索引

### Q: 什么是标识符增强？
A: 标识符增强是对代码标识符（变量名、函数名等）的额外匹配增强。
- 启用：设置 `retrieval.identifier_boost > 0` (如 0.01)
- 作用：如果文档包含查询中的标识符，会获得额外加分
- 适用场景：精确查找特定函数、类名时

## 许可证

MIT License
