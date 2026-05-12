# CodeMind Agent 项目文档

## 目录

1. [项目概述](#项目概述)
2. [系统架构](#系统架构)
3. [核心模块详解](#核心模块详解)
4. [RAG 技术深度解析](#rag-技术深度解析)
5. [Agent 工具系统](#agent-工具系统)
6. [安全机制](#安全机制)
7. [配置管理](#配置管理)
8. [部署指南](#部署指南)
9. [开发扩展指南](#开发扩展指南)

---

## 项目概述

### 项目简介

CodeMind Agent 是一个基于 RAG (检索增强生成) 的代码仓库智能问答系统，旨在帮助开发者快速理解和查询代码库。系统通过将代码仓库向量化存储，结合 LLM 的理解能力，提供智能代码问答、架构分析、Bug 定位等功能。

### 核心特性

1. **智能 Agent 模式**：自主决定何时使用检索工具，无需手动触发
2. **结构化代码切分**：基于 AST 和语法模式的智能切分，保留代码语义
3. **混合检索策略**：向量检索 + BM25 关键词检索双路并行，RRF 融合
4. **双层检索策略**：代码和文档分开检索，可配置不同数量
5. **总结层优化**：检索结果先经过 LLM 总结，减少 Token 消耗
6. **流式输出**：支持流式和非流式两种输出模式
7. **安全防护**：完善的路径、文件、命令安全检查机制

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web 框架 | FastAPI | 高性能异步 Web 框架 |
| LLM | 阿里云 Qwen | qwen-max / qwen-turbo |
| Embedding | 阿里云 DashScope | text-embedding-v4 |
| Vector DB | Chroma | 轻量级向量数据库 |
| Orchestration | LangChain | LLM 应用开发框架 |
| 配置管理 | YAML + python-dotenv | 支持环境变量和配置文件 |

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         API 层 (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  /chat       │  │/chat/stream  │  │  /health     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Manager (单例)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │   Agent      │  │  Summarizer  │  │ Query Rewriter  │  │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  |
│  │  │              检索层 (Retrieval Layer)                 │ │  |
│  │  │  ┌───────────────────────────────────────────────┐   │ │  |
│  │  │  │  向量检索         │      BM25 检索              │   │ │  |
│  │  │  └───────────────────────────────────────────────┘   │ │  |
│  │  │              ↓  RRF 融合  ↓                           | │  │
│  │  └──────────────────────────────────────────────────────┘ │  |
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌───────────────────┐
│  Agent 层       │  │  Prompt 层       │  │  RAG 层           │
│  - agent.py     │  │  - prompt_mgr   │  │  - indexer        │
│  - security.py  │  │                 │  │  - context_builder│
│  - streaming.py │  │                 │  │  - summarizer     │
│  - tools/*      │  │                 │  │  - fusion         │
└─────────────────┘  └─────────────────┘  └───────────────────┘
                              │
              ┌───────────────┼─────────────────┐
              ▼               ▼                 ▼
      ┌─────────────┐   ┌─────────────┐  ┌─────────────┐
      │ Chroma DB   │   │ BM25 Index  │  │  (待续...)  │
      └─────────────┘   └─────────────┘  └─────────────┘
```

### 请求处理流程

#### 非流式请求

```
1. 用户 POST /chat
   ↓
2. FastAPI 接收请求，获取 ServiceManager 中的 Agent
   ↓
3. Agent.aexecute() 执行
   ↓
4. Agent 根据问题决定使用工具（可能调用 RetrieveAndSummarize）
   ↓
5. 工具执行（向量检索 → 总结）
   ↓
6. Agent 基于工具返回结果生成最终回答
   ↓
7. 返回 JSON 响应
```

#### 流式请求

```
1. 用户 POST /chat/stream
   ↓
2. FastAPI 返回 StreamingResponse
   ↓
3. Agent.aexecute_stream() 开始流式执行
   ↓
4. 逐步生成并 yield 消息片段
   ↓
5. 客户端逐块接收并显示
```

---

## 核心模块详解

### 1. Service Manager (服务管理器)

**文件**: `services/service_manager.py`

**职责**:
- 单例模式管理所有核心服务
- 统一服务初始化和清理
- 提供服务访问接口

**核心代码结构**:

```python
class ServiceManager:
    _instance: Optional['ServiceManager'] = None
    _services: Dict[str, Any] = {}
    _initialized: bool = False

    def initialize(self) -> None:
        # 1. 初始化向量数据库
        self._init_vectordb()
        # 2. 初始化主 LLM
        self._init_llm()
        # 3. 初始化总结 LLM
        self._init_summarizer_llm()
        # 4. 初始化查询改写 LLM
        self._init_query_rewriting_llm()
        # 5. 初始化 Agent
        self._init_agent()
        # 6. 初始化工具的服务引用
        initialize_tool_service_manager(self)
```

**服务访问方式**:

```python
# 方式一：属性访问
vectordb = service_manager.vectordb
agent = service_manager.agent

# 方式二：字典式访问
llm = service_manager.get("llm")
```

**设计要点**:
- **单例模式**: 确保全局只有一个 ServiceManager 实例
- **延迟初始化**: 首次调用 `initialize()` 时才创建服务
- **线程安全**: FastAPI lifespan 中使用 `asyncio.to_thread()` 包装同步初始化

### 2. Agent 核心模块

**文件**: `agent/agent.py`

**职责**:
- 创建和运行 LangChain Agent
- 管理工具集
- 处理对话历史
- 支持流式/非流式两种执行模式

**核心类**: `CodeMindAgent`

```python
class CodeMindAgent:
    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None):
        # 1. 初始化 ChatTongyi LLM
        # 2. 获取工具列表
        self.tools = get_tools()
        # 3. 加载系统提示词
        self.system_prompt = load_system_prompts()
        # 4. 创建 LangChain Agent
        self.agent = create_agent(...)

    async def aexecute(self, question: str, history: list[dict] = None) -> Dict:
        """非流式执行"""
        # 处理历史消息
        # 构建消息列表
        # 调用 Agent
        # 返回结果

    async def aexecute_stream(self, question: str, history: list[dict] = None) -> AsyncGenerator:
        """流式执行"""
        # 流式生成消息
```

**工具列表**:
- `ReadFile`: 读取文件
- `SearchCode`: 搜索代码
- `RunCommand`: 执行命令
- `RetrieveAndSummarize`: 检索并总结

### 3. 流式输出处理

**文件**: `agent/streaming.py`

**职责**:
- 处理 Agent 流式输出
- 格式化流式响应
- 管理异步生成器

### 4. MCP Host 客户端

**文件**: `agent/mcp_host.py`

**职责**:
- Agent 作为 MCP Host，管理与 MCP Server 的通信
- 支持两种 transport 模式: stdio 和 local
- 工具发现和调用
- 健康检查

**核心类**: `MCPClient`

```python
class MCPClient:
    def __init__(
        self,
        *,
        transport: str | None = None,
        server_command: list[str] | None = None,
        call_timeout: float | None = None,
        startup_timeout: float | None = None,
    )

    def initialize(self) -> None
        """初始化 MCP 客户端"""

    def close(self) -> None
        """关闭 MCP 客户端，清理资源"""

    def list_tools(self) -> list[dict[str, Any]]
        """列出 MCP Server 提供的所有工具"""

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str
        """调用 MCP Server 工具"""

    def health_check(self) -> bool
        """检查 MCP Server 健康状态"""

    @property
    def is_initialized(self) -> bool
        """是否已初始化"""
```

**Transport 模式**:

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `stdio` | MCP Server 作为独立子进程运行，通过 stdio 通信 | 生产环境，完全隔离 |
| `local` | MCP Server 在同一进程内直接调用 | 测试/调试，无进程开销 |

**Stdio 模式工作流**:

```
1. 初始化阶段:
   - 启动独立线程管理 asyncio 事件循环
   - 通过 subprocess 启动 MCP Server 子进程
   - ClientSession 初始化握手
   - startup_timeout 内完成初始化

2. 工具调用阶段:
   - 调用线程通过队列向 worker 发送请求
   - worker 通过 stdio 与 Server 通信
   - call_timeout 控制超时
   - 返回内容扁平化处理为字符串

3. 关闭阶段:
   - 发送停止信号
   - 等待 worker 结束
   - 关闭子进程
   - 停止事件循环线程
```

**Local 模式工作流**:

```
1. 直接导入 codemind_mcp.server
2. 调用 list_registered_tools() / call_registered_tool()
3. 无进程间通信开销
4. 无超时控制
```

**LangChain 工具适配**:

```python
def build_langchain_mcp_tools(mcp_client: MCPClient) -> list[StructuredTool]
    """
    将 MCP 工具动态转换为 LangChain StructuredTool:
    - 自动从 inputSchema 生成 Pydantic 模型
    - 支持必填/可选参数
    - 类型映射: integer→int, number→float, boolean→bool, array→list, object→dict
    """
```

---

## MCP 架构详解

### 为什么需要 MCP 架构？

**之前的问题**:
- 所有工具都在 Agent 进程内执行
- 工具代码与 Agent 代码耦合
- 难以独立测试和复用工具
- 无法与其他 MCP 客户端（如 Claude Desktop）集成

**MCP 架构解决的问题**:
- ✅ 工具与 Agent 解耦，工具在独立进程中运行
- ✅ 工具可复用，支持被其他 MCP 客户端调用
- ✅ 更好的隔离性，工具崩溃不影响主进程
- ✅ 标准化接口，便于扩展新工具

### MCP Server 核心设计

**文件**: `codemind_mcp/server.py`

**设计要点**:
- 支持两种运行模式: 作为独立脚本运行 / 作为包导入
- 动态包引导机制: 直接运行时创建临时包别名
- SDK 适配层: 支持不同版本的 MCP SDK

**核心功能**:

```python
async def list_registered_tools() -> list[Any]
    """列出所有注册的 MCP 工具（local 模式用）"""

async def call_registered_tool(name: str, arguments: dict[str, Any]) -> str
    """调用注册的 MCP 工具（local 模式用）"""
```

**环境变量配置**:
- `CODEMIND_LOG_STDERR=1`: 日志输出到 stderr（默认开启）

### SDK 适配层

**文件**: `codemind_mcp/sdk.py`

**职责**:
- 封装 MCP SDK 的差异
- 提供统一的接口给 Server
- 支持不同的 transport 实现

**核心组件**:

```python
class LocalServerShim:
    """本地 Server 垫片，支持 local 模式"""

def load_sdk_modules() -> tuple[Any, Any, Any, Any]:
    """动态加载 SDK 模块: Server 类型, stdio_server, 忽略项, types 模块"""

@asynccontextmanager
async def local_stdio_server(stdin, stdout, server):
    """本地 stdio server 上下文管理器"""
```

### 工具实现层

**文件**: `codemind_mcp/tool_impl.py`

**设计要点**:
- 所有工具的实际实现代码在这里
- 复用原有的安全检查模块 (`agent/security.py`)
- 复用原有的工具路径模块 (`agent/tool_paths.py`)
- 提供统一的输出截断机制

**核心功能**:

| 功能 | 说明 |
|------|------|
| `resolve_file_path()` | 解析文件路径，支持相对路径/绝对路径/仓库内搜索 |
| `search_file_by_name()` | 在允许的目录中按文件名搜索 |
| `search_content_in_files()` | 在文件内容中搜索关键词/正则 |
| `execute_shell_command()` | 执行安全的 shell 命令，白名单验证 |
| `truncate_tool_output()` | 截断工具输出，避免超过上下文限制 |

**安全检查复用**:
- 所有文件操作通过 `validate_file_access()` 验证
- 所有命令操作通过 `is_command_allowed()` 验证
- 路径白名单、敏感文件规则与原架构一致

### 工具定义层

**目录**: `codemind_mcp/tools/`

**基类**: `MCPTool`

```python
class MCPTool:
    name: str
    description: str
    inputSchema: dict[str, Any]

    async def call(self, arguments: dict[str, Any]) -> Any:
        """调用工具，子类实现"""
```

**现有工具**:

| 工具 | 文件 | 说明 |
|------|------|------|
| ReadFile | `read_file.py` | 读取文件内容，支持行号范围 |
| SearchCode | `search_code.py` | 代码搜索，支持关键词/正则/文件名过滤 |
| RunCommand | `run_command.py` | 执行 shell 命令，白名单验证 |
| IndexRepo | `index_manager/index_repo.py` | 索引整个仓库 |
| AddByFilePath | `index_manager/add_by_file_path.py` | 增量追加文件/目录到索引 |
| DeleteByFilePath | `index_manager/delete_by_file_path.py` | 从索引中删除文件/目录 |

### 安全模块代理

**文件**: `codemind_mcp/security.py`

**设计**:
- 直接从 `agent.security` 导入所有函数
- 保持与本地工具一致的安全策略

### 配置项

**config.yml 新增**:

```yaml
mcp:
  transport: "stdio"                    # stdio / local
  server_command:                       # stdio 模式下的 MCP Server 启动命令
    - "conda"
    - "run"
    - "--no-capture-output"
    - "-n"
    - "AIP312"
    - "python"
    - "/abs/path/to/codemind_mcp/server.py"
  server_env: {}                        # 可选: 传给 Server 的环境变量
  call_timeout: 10                      # 工具调用超时（秒）
  startup_timeout: 15                   # Server 启动超时（秒）
```

### Agent 工具集成

**文件**: `agent/agent.py`

```python
def get_tools(mcp_client: MCPClient | None = None) -> List[Tool]:
    """
    获取 Agent 工具列表:
    1. 先获取本地工具 (仅 RetrieveAndSummarize)
    2. 如果提供了 mcp_client，添加 MCP 工具
    """
    tools = list(get_agent_toolset())
    if mcp_client is not None:
        tools.extend(build_langchain_mcp_tools(mcp_client))
    return tools
```

**工具执行策略**:

| 工具 | 执行位置 | 原因 |
|------|---------|------|
| RetrieveAndSummarize | 本地 | 需要访问 Vector DB / BM25，低延迟 |
| ReadFile | MCP Server | 文件操作可复用，隔离 |
| SearchCode | MCP Server | 搜索操作可复用，隔离 |
| RunCommand | MCP Server | 命令操作可复用，隔离 |
| IndexRepo | MCP Server | 索引操作可复用，隔离 |
| AddByFilePath | MCP Server | 索引操作可复用，隔离 |
| DeleteByFilePath | MCP Server | 索引操作可复用，隔离 |

### Service Manager 集成

**文件**: `services/service_manager.py`

```python
def _init_mcp_client(self) -> None:
    """初始化 MCP 客户端"""
    logger.info("初始化 MCP client...")
    client = MCPClient()
    client.initialize()
    self._services["mcp_client"] = client
    logger.info("MCP client 初始化完成")

def _init_agent(self) -> None:
    """初始化 Agent，传入 MCP 客户端"""
    logger.info("初始化 CodeMind Agent...")
    agent = CodeMindAgent(mcp_client=self.mcp_client)
    self._services["agent"] = agent

def cleanup(self) -> None:
    """清理时关闭 MCP 客户端"""
    mcp_client = self._services.get("mcp_client")
    if mcp_client is not None:
        try:
            mcp_client.close()
        except Exception as e:
            logger.warning(f"MCP client 关闭失败: {e}")
```

### /health 端点更新

**新增字段**:

```json
{
  "status": "ok",
  "vectordb_initialized": true,
  "agent_initialized": true,
  "mcp_host_initialized": true,
  "mcp_client_initialized": true,
  "mcp_client_healthy": true
}
```

### 独立使用 MCP Server

**启动 MCP Server**:

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 conda run --no-capture-output -n AIP312 python codemind_mcp/server.py
```

**与 Claude Desktop 集成**:

在 Claude Desktop 配置文件中添加:

```json
{
  "mcpServers": {
    "codemind": {
      "command": "conda",
      "args": [
        "run",
        "--no-capture-output",
        "-n",
        "AIP312",
        "python",
        "/path/to/codemind_mcp/server.py"
      ],
      "env": {
        "CODEMIND_CONFIG_PATH": "/path/to/config.yml"
      }
    }
  }
}
```

### 基准测试

**工具调用延迟**:

```bash
# 测试本地工具 vs MCP local vs MCP stdio
python scripts/benchmark_mcp_tools.py --iterations 5
python scripts/benchmark_mcp_tools.py --iterations 5 --stdio
```

**内存占用**:

```bash
# 测试内存占用
python scripts/benchmark_mcp_memory.py
python scripts/benchmark_mcp_memory.py --stdio
```

**测试结果说明**:
- `local` 模式: 无进程间通信开销，延迟最低
- `stdio` 模式: 有进程间通信开销，但提供完全隔离
- 内存占用: `stdio` 模式会有两个 Python 进程（主进程 + Server）

---

## RAG 技术深度解析

### 1. 代码切分策略 (Splitting)

切分是 RAG 系统中最关键的环节之一，直接影响检索质量。CodeMind Agent 采用**语言感知的智能切分策略**，支持多种编程语言的 AST 解析。

#### 切分架构设计

```
CodeSplitter (抽象基类)
    ├─ PythonCodeSplitter (Python AST)
    ├─ TreeSitterCodeSplitter (多语言 Tree-sitter AST)
    └─ RegexCodeSplitter (正则模式，降级方案)

get_code_splitter(file_ext) → 返回适合的切分器
```

**核心接口**:
```python
class CodeSplitter(ABC):
    @abstractmethod
    def split(self, content: str, max_class_length: int = 3000) -> list[str]:
        pass
```

#### Python: AST 模式切分

**实现**: `PythonCodeSplitter`

**流程**:

```
1. 尝试用 ast.parse() 解析代码
   ├─ 成功 → AST 模式
   └─ 失败 → 回退到缩进扫描模式

2. AST 模式:
   ├─ 遍历 AST，提取顶级 ClassDef/FunctionDef/AsyncFunctionDef
   ├─ 按节点起始/结束行号从原文切分
   ├─ 类超过 max_class_length → 按方法进一步拆分
   └─ 保留结构间的普通代码

3. 回退模式:
   ├─ 用正则匹配 ^\s*class\s 和 ^\s*def\s
   ├─ 基于缩进级别判断块边界
   └─ 处理超大类的方法拆分
```

**关键辅助函数**:

| 函数 | 作用 |
|------|------|
| `_node_start_lineno()` | 获取节点真实起始行（考虑装饰器） |
| `_node_end_lineno()` | 获取节点结束行 |
| `_source_block()` | 按行号切分原文，去除首尾空行 |
| `_split_class_by_ast_methods()` | 对超大类按方法拆分 |

**为什么用 AST 而不是直接切分？**

| 对比项 | AST 模式 | 普通字符切分 |
|--------|----------|-------------|
| 语义完整性 | ✅ 保留完整类/函数 | ❌ 可能从中间切断 |
| 装饰器处理 | ✅ 装饰器属于类/函数 | ❌ 可能分开 |
| 嵌套结构 | ✅ 正确处理内部类/函数 | ❌ 容易切错边界 |
| 容错性 | ✅ 有回退机制 | ❌ 无 |

#### 多语言 Tree-sitter AST 切分 (推荐)

**实现**: `TreeSitterCodeSplitter`

**支持语言**:

| 语言 | 文件扩展名 | 类/接口节点类型 | 函数/方法节点类型 |
|------|----------|----------------|------------------|
| JavaScript | `.js`, `.jsx` | `class_declaration` | `function_declaration`, `generator_function_declaration`, `arrow_function`, `method_definition` |
| TypeScript | `.ts`, `.tsx` | `class_declaration` | `function_declaration`, `generator_function_declaration`, `arrow_function`, `method_definition` |
| Go | `.go` | - | `function_declaration`, `method_declaration` |
| Rust | `.rs` | `impl_item`, `struct_item` | `function_item` |
| Java | `.java` | `class_declaration` | `method_declaration` |
| C | `.c` | - | `function_definition` |
| C++ | `.cpp` | `class_specifier` | `function_definition` |

**切分流程**:

```
1. 检查依赖: tree-sitter-languages 是否安装？
   ├─ 否 → 降级到 RegexCodeSplitter
   └─ 是 → 继续

2. 构建 Parser: 获取对应语言的 tree-sitter 语言

3. 解析代码: parser.parse(content) → 语法树

4. 提取主要块:
   ├─ 遍历树收集类/接口节点 (CLASS_CHUNK_TYPES)
   ├─ 类大小 ≤ max_class_length → 保留完整类
   ├─ 类大小 > max_class_length → 按方法拆分
   ├─ 收集独立函数/方法节点 (FUNCTION_CHUNK_TYPES)
   └─ 跳过已被类包含的函数

5. 合并结果:
   ├─ 合并类块 + 函数块 + 剩余代码片段
   ├─ 按字节位置排序
   └─ 合并相邻片段，去除重复覆盖

6. 降级处理: 如果 Tree-sitter 失败 → RegexCodeSplitter
```

**Tree-sitter 关键特性**:
- **语句扩展**: 自动扩展到包含变量声明、export 语句等父节点
- **片段合并**: 智能合并非结构代码片段，避免碎片化
- **范围去重**: 精确处理字节范围，避免重复或遗漏

#### 正则模式切分 (降级方案)

**实现**: `RegexCodeSplitter`

| 语言 | 切分模式 (在匹配前切分) |
|------|----------------------|
| Java | `public` \| `private` \| `protected` \| `class` \| `interface` |
| JS/TS/JSX/TSX | `function` \| `class` \| `const` \| `let` \| `var` \| `export` \| `interface` |
| Go | `func` \| `type` \| `struct` |
| Rust | `fn` \| `impl` \| `struct` \| `enum` \| `trait` |
| C/C++ | 函数定义、类/结构体等 |

#### 普通文档: RecursiveCharacterTextSplitter

- 文档: `chunk_size=800`, `chunk_overlap=100`
- 代码: 先按语义块切分，再按 `chunk_size.code` 截断单个代码块；不再对代码块做二次递归切分

### 2. 索引构建 (Indexing)

**文件**: `scripts/index_repo.py`

**完整流程**:

```
1. 配置加载
   ├─ 仓库路径
   ├─ 向量数据库路径
   ├─ 切分参数
   └─ 嵌入模型

2. 遍历文件 (os.walk)
   ├─ 原地过滤排除目录 (.git, node_modules, __pycache__, cache, ...)
   ├─ 检查文件扩展名
   └─ 对每个文件:

3. 文件加载和切分
   ├─ 获取切分器: get_code_splitter(file_ext)
   │   ├─ .py → PythonCodeSplitter
   │   ├─ 其他支持语言 → TreeSitterCodeSplitter (降级到 RegexCodeSplitter)
   │   └─ 不支持的代码扩展名 → 不索引
   ├─ 调用 splitter.split(content, max_class_length)
   ├─ 每个代码块直接构建 Document，并按 chunk_size.code 截断
   ├─ 其他文件: 必须是支持的文档扩展名且未命中 should_exclude_file()
   └─ 构建 Document 对象 (page_content + metadata)

4. 分块去重
   ├─ 为每个 Document 写入基于内容 SHA-256 的 chunk_hash
   ├─ 先对本次构建产生的重复 chunk 去重
   ├─ 加载已有 BM25 metadata，跳过已存在 hash
   └─ 如可连接 Chroma，则读取已有 Chroma metadata，继续跳过已存在 hash

5. 构建/更新 BM25 索引
   ├─ 加载已有 BM25 文档和 metadata
   ├─ 合并新增分块
   ├─ BM25Index.fit() 重建索引
   └─ 保存到 bm25.persist_path

6. 分批向量化
   ├─ DashScopeEmbeddings.embed_documents()
   ├─ 每批 1024 条写入 Chroma DB
   └─ 持久化到磁盘
```

`index_repo.py` 将流程拆成 `collect_repo_files()`、`build_chunks()` 和 `save_indexes()`。增量追加脚本会复用后两者，保证全量索引和增量索引使用一致的文件切分、metadata 和写入规则。

**支持的代码文件扩展名**:
`.py`, `.java`, `.js`, `.jsx`, `.ts`, `.tsx`, `.go`, `.rs`, `.c`, `.cpp`

**排除规则**:

**目录排除** (exclude_dirs):

- VCS: `.git`, `.svn`, `.hg`, `.bzr`
- Python: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `venv`, `.venv`, `dist`, `build`
- Node: `node_modules`, `.npm`, `.parcel-cache`
- IDE: `.idea`, `.vscode`
- 其他: `chroma_db`, `logs`, `tmp`, `cache`

**文件排除** (exclude_files):
- 依赖锁定: `package-lock.json`, `yarn.lock`, `poetry.lock`, `go.sum`, `Cargo.lock`
- 环境配置: `.env`, `.env.*`, `.gitignore`
- 文档: `LICENSE`, `README.md`, `CHANGELOG.md`

**模式排除** (exclude_file_patterns):
- 图片/媒体: `*.jpg`, `*.png`, `*.mp3`, `*.mp4`, ...
- 二进制: `*.exe`, `*.dll`, `*.so`, `*.bin`, ...
- 敏感文件: `*.key`, `*.pem`, `*.p12`, `*.pfx`, ...
- 压缩包: `*.zip`, `*.tar`, `*.rar`, ...

### 3. 查询改写 (Query Rewriting)

**文件**: `utils/query_rewriting.py`

**为什么需要查询改写？**

| 问题 | 解决方案 |
|------|---------|
| 用户问题表述口语化，不匹配代码术语 | 关键词提取+同义转换 |
| 问题模糊，缺乏检索指向性 | 回答推测提供可能的答案方向 |
| 直接检索命中率低 | 增强检索文本，提高召回率 |

**查询改写流程**:

```
用户问题
   ↓
┌─────────────────────────────────────────┐
│  步骤 1: 关键词提取                       │
│  aget_query_key_words(question, llm)    │
├─────────────────────────────────────────┤
│  提示词: "将用户问题转化为几个核心关键词"     │
│  约束: 同义转换、仅中文、逗号分隔            │
│  输出: ["关键词1", "关键词2", ...]         │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  步骤 2: 回答推测                         │
│  aget_query_answer_guess(question, llm) │
├─────────────────────────────────────────┤
│  提示词: "基于问题推测可能的答案"            │
│  约束: 代码开发领域、模糊问题返回空格         │
│  输出: "可能的答案内容..."                 │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  步骤 3: 检索文本构建                      │
├─────────────────────────────────────────┤
│  temp_question =                        │
│    answer_guess +                       │
│    " 关键词: " + (", ".join(kw) * 3)     │
│                                         │
│  * 关键词重复 3 次是为了增加权重            │
└─────────────────────────────────────────┘
   ↓
使用 temp_question 进行向量检索
```

**核心函数**:

```python
async def aget_query_key_words(question: str, query_rewriting_llm: ChatTongyi) -> list:
    """异步获取用户问题的关键词列表"""
    prompt_template = get_query_rewriting_prompt_template(type="key_words")
    prompt = prompt_template.format(input=question)
    response = await query_rewriting_llm.ainvoke(prompt)
    key_words_str = response.content if hasattr(response, 'content') else str(response)
    key_words = [kw.strip() for kw in key_words_str.split(",") if kw.strip()]
    return key_words

async def aget_query_answer_guess(question: str, query_rewriting_llm: ChatTongyi) -> str:
    """异步获取对用户问题的可能回答推测"""
    prompt_template = get_query_rewriting_prompt_template(type="answer_guess")
    prompt = prompt_template.format(input=question)
    response = await query_rewriting_llm.ainvoke(prompt)
    answer_guess_str = response.content if hasattr(response, 'content') else str(response)
    return answer_guess_str.strip()

def create_query_rewriter(model: str = "qwen-max") -> ChatTongyi:
    """创建查询改写模型实例"""
    return ChatTongyi(model=model)
```

**提示词场景** (`prompts/prompt_manager.py`):

| 场景枚举 | 说明 |
|---------|------|
| `PromptScenario.QUERY_KEY_WORDS` | 关键词提取提示词 |
| `PromptScenario.QUERY_ANSWER_GUESS` | 回答推测提示词 |

**关键词提取提示词要点**:
- 将非常不专业且模糊的词汇转化为开发者领域的相关同义词汇
- 仅用中文回答
- 以纯文本字符串形式呈现，关键词仅以英文逗号分隔

**回答推测提示词要点**:
- 答案必须基于代码开发领域，不做过多发散
- 如果问题实在模糊无法推测答案，则仅仅返回空格
- 对于具体的查询问题，不要给出名词解释，而是返回空格
- 只有用户的问题明确让你解释名词才解释

**配置项**:
```yaml
query_rewriting:
  model: "qwen-turbo"    # 查询改写模型（推荐使用轻量模型）
```

### 4. 检索策略 (Retrieval)

**文件**: `agent/tools/retrieve_and_summarize.py`

**检索流程**:

```
用户问题
   ↓
┌─────────────────────────────────────────┐
│  查询改写增强 (已实现)                  │
├─────────────────────────────────────────┤
│  1. 提取关键词                          │
│  2. 推测答案方向                        │
│  3. 构建增强检索文本                    │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  双层检索 (分开检索，可配置数量)        │
├─────────────────────────────────────────┤
│                                         │
│  1. 文档检索 (type="doc")               │
│     asimilarity_search(k=5)             │
│                                         │
│  2. 代码检索 (type="code")              │
│     asimilarity_search(k=10)            │
│                                         │
└─────────────────────────────────────────┘
   ↓
合并结果
   ↓
记录来源信息
   ↓
传递给总结模块
```

**RetrieveAndSummarize 工具核心代码**:

```python
@tool
async def RetrieveAndSummarize(question: str) -> str:
    # 1. 获取服务
    vectordb = _service_manager.vectordb
    summarizer_llm = _service_manager.summarizer_llm
    query_rewriting_llm = _service_manager.query_rewriting_llm
    retrieval_k = _service_manager.retrieval_k

    # 2. 查询改写
    key_words = await aget_query_key_words(question, query_rewriting_llm)
    answer_guess = await aget_query_answer_guess(question, query_rewriting_llm)
    
    # 3. 构建增强检索文本
    temp_question = answer_guess + " 关键词: " + (", ".join(key_words) * 3)
    
    logger.info("=" * 80)
    logger.info(f"最终用于检索的文本: {temp_question}")
    logger.info("=" * 80)

    # 4. 双层检索
    docs = await vectordb.asimilarity_search(
        temp_question, k=retrieval_k.get("doc", 5), filter={"type": "doc"}
    )
    docs.extend(await vectordb.asimilarity_search(
        temp_question, k=retrieval_k.get("code", 10), filter={"type": "code"}
    ))

    # 5. 记录来源信息
    log_sources_info(docs)

    # 6. 调用总结模块
    summarized_context = await asummarize_context(question, docs, summarizer_llm)

    return summarized_context
```

**配置项**:
```yaml
chroma:
  retrieval_k:
    docs: 5      # 文档检索数量
    codes: 10    # 代码检索数量
```

**元数据过滤**:
```python
metadata_filter_doc = {"type": "doc"}
metadata_filter_code = {"type": "code"}
```

**TODO 规划** (代码中已标注):
- Query 优化: Query Decomposition / HyDE (已实现 Query Rewriting)
- 混合检索: 向量检索 + BM25 检索

### 4. 总结层 (Summarization)

**文件**: `utils/summarizer.py`

**为什么需要总结层？**

| 问题 | 解决方案 |
|------|---------|
| 检索结果过多，超出 LLM 上下文窗口 | 先总结压缩 |
| 检索结果有不相关信息 | 基于问题筛选提炼 |
| Token 消耗大 | 减少传递给主 LLM 的 Token |

**总结流程**:

```
检索结果 (多个 Document)
   ↓
build_context(): 格式化为带来源的字符串
   ↓
提示词: {input}=用户问题, {context}=原始检索结果
   ↓
调用 summarizer_llm (qwen-turbo)
   ↓
返回精炼总结
```

**总结提示词** (prompts/prompt_manager.py):

```
你是专注于"基于参考资料总结"的AI助手，需结合用户提问和向量检索到的参考资料，生成简洁准确的概括回答。

### 严格约束
1. 内容合规：禁止包含违法、侵权、攻击性信息
2. 事实准确：回答必须完全基于参考资料，不编造
3. 语言要求：仅用中文回答，简洁客观
4. 聚焦提问：严格围绕用户原始提问，不扩展
5. 格式要求：仅输出概括内容本身，纯文本
6. 排除干扰：问题是总结性质且某资料和其他资料相差甚远，降低该资料比重
7. 代码为准：文档和代码不一致时，以实际代码为准
8. 文件提示：总结末尾追加与问题相关的材料文件路径，便于定位来源
```

### 5. 上下文构建 (Context Building)

**文件**: `rag/context_builder.py`

**ProcessedContext 数据类**:

```python
@dataclass
class ProcessedContext:
    raw_context: str           # 原始拼接的检索结果
    summarized_context: str    # 总结后的精炼上下文
    sources: List[Dict]       # 来源信息列表
```

---

## Agent 工具系统

### 工具架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Tool System                        │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  工具定义 (@tool 装饰器)                                  │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  ReadFile         │  读取文件，支持行号范围                 │  │
│  │  SearchCode       │  搜索代码，支持关键词/正则              │  │
│  │  RunCommand       │  执行只读 shell 命令                   │  │
│  │  RetrieveAndSummarize │  检索并总结代码库                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  服务注入机制                                             │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  initialize_tool_service_manager(service_manager)         │  │
│  │  ↓                                                        │  │
│  │  全局变量 _service_manager = service_manager              │  │
│  │  ↓                                                        │  │
│  │  工具可访问 vectordb, summarizer_llm, retrieval_k         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1. RetrieveAndSummarize 工具（本地执行）

**文件**: `agent/tools/retrieve_and_summarize.py`

**核心代码**:

```python
_service_manager: Optional[Any] = None  # 全局服务引用

@tool
async def RetrieveAndSummarize(question: str) -> str:
    """根据用户问题从代码库中检索相关文档并进行总结提炼"""

    # 1. 获取服务
    vectordb = _service_manager.vectordb
    summarizer_llm = _service_manager.summarizer_llm
    retrieval_k = _service_manager.retrieval_k

    # 2. 双层检索
    docs = await vectordb.asimilarity_search(
        question, k=retrieval_k.get("doc", 5), filter={"type": "doc"}
    )
    docs.extend(await vectordb.asimilarity_search(
        question, k=retrieval_k.get("code", 10), filter={"type": "code"}
    ))

    # 3. 记录来源信息
    log_sources_info(docs)

    # 4. 调用总结模块
    summarized_context = await asummarize_context(question, docs, summarizer_llm)

    return summarized_context
```

### 2. ReadFile 工具

**文件**: `agent/tools/read_file.py`

**功能**:
- 支持相对仓库根目录的路径
- 自动搜索同名文件
- 支持行号范围
- UTF-8/GBK 双编码支持
- 带行号显示

**路径解析策略**:

```
用户传入 file_path
   ↓
1. 尝试直接原始路径 → 存在？返回
   ↓
2. 在 repo_path 下查找 → 存在？返回
   ↓
3. 如果是绝对路径，提取文件名在 repo_path 下查找 → 存在？返回
   ↓
4. 搜索整个仓库中的同名文件 → 0个？报错
                          → 1个？读取
                          → 多个？返回列表让用户选择
```

### 3. SearchCode 工具

**文件**: `agent/tools/search_code.py`

**功能**:
- 关键词搜索
- 正则表达式搜索
- 文件名过滤
- 结果数量限制

### 2. ReadFile 工具（已迁移到 MCP Server）

**注意**: 原 `agent/tools/read_file.py` 已移除，工具实现已迁移到 MCP Server

**MCP Server 位置**:
- 定义: `codemind_mcp/tools/read_file.py`
- 实现: `codemind_mcp/tool_impl.py`

**功能**:
- 支持相对仓库根目录的路径
- 自动搜索同名文件
- 支持行号范围
- UTF-8/GBK 双编码支持
- 带行号显示

### 3. SearchCode 工具（已迁移到 MCP Server）

**注意**: 原 `agent/tools/search_code.py` 已移除，工具实现已迁移到 MCP Server

**MCP Server 位置**:
- 定义: `codemind_mcp/tools/search_code.py`
- 实现: `codemind_mcp/tool_impl.py`

**功能**:
- 关键词搜索
- 正则表达式搜索
- 文件名过滤
- 结果数量限制

### 4. RunCommand 工具（已迁移到 MCP Server）

**注意**: 原 `agent/tools/run_command.py` 已移除，工具实现已迁移到 MCP Server

**MCP Server 位置**:
- 定义: `codemind_mcp/tools/run_command.py`
- 实现: `codemind_mcp/tool_impl.py`

**功能**:
- 执行只读命令
- 命令白名单验证
- 参数过滤 (如禁止 ls -R)
- 超时控制

### 5. IndexManager 工具集（新增，MCP Server）

**MCP Server 位置**: `codemind_mcp/tools/index_manager/`

| 工具 | 文件 | 说明 |
|------|------|------|
| IndexRepo | `index_repo.py` | 索引整个代码仓库 |
| AddByFilePath | `add_by_file_path.py` | 增量追加文件/目录到索引 |
| DeleteByFilePath | `delete_by_file_path.py` | 从索引中删除文件/目录 |

---

## 安全机制

**文件**: `agent/security.py`

### 1. 路径安全检查

**函数**: `is_path_allowed()`

```
检查逻辑:
1. normalize_path(): 展开 ~, 环境变量, 相对路径 (../, ./)
2. 转换为绝对路径
3. 检查是否以 allowed_dir 中的某个目录开头
   (精确等于 或 前缀匹配+路径分隔符)
```

**示例**:
```python
allowed_dirs = ["/home/user/repo"]

is_path_allowed("/home/user/repo/file.py", allowed_dirs)      # ✅
is_path_allowed("/home/user/repo/sub/file.py", allowed_dirs)  # ✅
is_path_allowed("/home/other/file.py", allowed_dirs)          # ❌
is_path_allowed("/home/user/repo/../secret", allowed_dirs)    # ❌ (规范化后是 /home/user/secret)
```

### 2. 敏感文件检查

**函数**: `is_sensitive_file()`

**敏感文件模式**:
- 环境变量: `.env`, `.env.*`
- 密钥文件: `*.key`, `*.pem`, `*.p12`, `*.pfx`, `*.cer`, `*.crt`
- SSH 密钥: `id_rsa`, `id_dsa`, `id_ed25519`, `*.p8`
- 其他: `secrets.yml`, `*.secret`

**检查方式**: glob 模式匹配 (`fnmatch`)

### 3. 命令安全检查

**函数**: `is_command_allowed()`

**白名单命令** (config.yml):
```yaml
agent:
  allowed_commands: ["ls", "cat", "grep", "git", "find", "head", "tail", "wc"]
```

**禁止的参数**:
```python
BLOCKED_ARGS = {
    "ls": ["-R", "-r", "--recursive"],   # 禁止递归列出
    "dir": ["/S", "/s"],                  # Windows 对应
}
```

**Unix ↔ Windows 映射**:
- `ls` ↔ `dir`
- `cat` ↔ `type`
- `grep` ↔ `findstr`

### 4. 综合验证

**函数**: `validate_file_access()`

```
检查顺序:
1. 文件是否存在？
2. 是否是文件（不是目录）？
3. 路径是否在白名单内？
4. 是否是敏感文件？
```

---

## 配置管理

**文件**: `utils/config.py`, `config.yml`

### 配置加载流程

```
Config.load()
   ↓
1. 调用 dotenv.load_dotenv()
   ↓
2. 如果 config.yml 存在:
   yaml.safe_load() → _config 字典
   ↓
3. _loaded = True
```

### 配置访问

**方式一**: 点分隔键

```python
Config.get("chroma.persist_dir", "./chroma_db")
Config.get("agent.model", "qwen-max")
```

**内部实现**:

```python
@classmethod
def get(cls, key: str, default: Any = None) -> Any:
    parts = key.split('.')
    value = cls._config
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    return value
```

**方式二**: 环境变量

```python
Config.get_env("DASHSCOPE_API_KEY", "")
```

### 配置文件完整示例

```yaml
chroma:
  persist_dir: "./chroma_db"
  chunk_size:
    doc: 800
    code: 2000
  chunk_overlap: 100
  retrieval_k:
    docs: 5
    codes: 10

repo:
  path: "/path/to/your/repo"

embeddings:
  model: "text-embedding-v4"

llm:
  model: "qwen-max"
  temperature: 0.1

summarizer:
  model: "qwen-turbo"
  temperature: 0.1

query_rewriting:
  model: "qwen-turbo"

splitting:
  max_class_length: 3000

agent:
  enabled: true
  model: "qwen-max"
  temperature: 0.1
  allowed_dirs: ["."]
  blocked_files:
    - ".env"
    - "*.key"
    - "*.pem"
    - "*.p12"
    - "id_rsa"
  allowed_commands:
    - "ls"
    - "cat"
    - "grep"
    - "git"
    - "find"
    - "head"
    - "tail"
    - "wc"
  command_timeout: 5
  max_search_results: 50

mcp:
  transport: "stdio"                    # stdio / local
  server_command:                       # stdio 模式下的 MCP Server 启动命令
    - "conda"
    - "run"
    - "--no-capture-output"
    - "-n"
    - "AIP312"
    - "python"
    - "/abs/path/to/codemind_mcp/server.py"
  server_env: {}                        # 可选: 传给 Server 的环境变量
  call_timeout: 10                      # 工具调用超时（秒）
  startup_timeout: 15                   # Server 启动超时（秒）
```

---

## 部署指南

### Docker 部署

**创建 Dockerfile**:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 环境变量
ENV DASHSCOPE_API_KEY=""

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**构建和运行**:

```bash
# 先在本地索引（或者在容器启动时索引）
python scripts/index_repo.py /path/to/repo

# 构建镜像
docker build -t codemind-agent .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -e DASHSCOPE_API_KEY=sk-xxx \
  -v $(pwd)/chroma_db:/app/chroma_db \
  -v $(pwd)/config.yml:/app/config.yml \
  codemind-agent
```

### Systemd 服务部署

**创建 /etc/systemd/system/codemind-agent.service**:

```ini
[Unit]
Description=CodeMind Agent Service
After=network.target

[Service]
Type=notify
User=your-user
WorkingDirectory=/path/to/CodeMindAgent
Environment="DASHSCOPE_API_KEY=sk-xxx"
ExecStart=/path/to/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**启动服务**:

```bash
# 重载配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start codemind-agent

# 开机自启
sudo systemctl enable codemind-agent

# 查看日志
sudo journalctl -u codemind-agent -f
```

### Nginx 反向代理

**配置 /etc/nginx/sites-available/codemind**:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # 流式响应支持
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

---

## 开发扩展指南

### 添加新的 Agent 工具

**步骤**:

1. 在 `agent/tools/` 下创建新文件，例如 `my_tool.py`

```python
"""My New Tool"""
from langchain_core.tools import tool
from utils.logger import get_logger

logger = get_logger("agent.tools.my_tool")

# 如果需要访问服务，使用全局变量模式
_service_manager: Optional[Any] = None

def initialize_tool_service_manager(service_manager: Any) -> None:
    global _service_manager
    _service_manager = service_manager

@tool
def MyNewTool(param1: str, param2: Optional[int] = None) -> str:
    """工具描述（会被 Agent 看到）。

    Args:
        param1: 参数描述
        param2: 可选参数描述

    Returns:
        返回值描述
    """
    logger.info(f"MyNewTool called: param1={param1}, param2={param2}")

    try:
        # 实现逻辑
        result = do_something(param1, param2)
        return result
    except Exception as e:
        logger.error(f"MyNewTool failed: {e}")
        return f"[错误] {str(e)}"
```

2. 在 `agent/tools/__init__.py` 中导出

```python
from .my_tool import MyNewTool, initialize_tool_service_manager

__all__ = [
    # ... 现有工具
    "MyNewTool",
]

# 合并初始化函数（如果需要）
def initialize_all_tools(service_manager):
    from .retrieve_and_summarize import initialize_tool_service_manager as init_ras
    from .my_tool import initialize_tool_service_manager as init_my_tool
    init_ras(service_manager)
    init_my_tool(service_manager)
```

3. 在 `agent/agent.py` 的 `get_tools()` 中添加

```python
def get_tools() -> List[Tool]:
    return [
        ReadFile,
        SearchCode,
        RunCommand,
        RetrieveAndSummarize,
        MyNewTool,  # 添加这行
    ]
```

4. 在 `services/service_manager.py` 中初始化（如果需要服务注入）

```python
def initialize(self) -> None:
    # ... 现有代码
    from agent.tools import initialize_all_tools
    initialize_all_tools(self)
```

### 添加新的语言切分支持

**推荐方式: Tree-sitter AST (如果语言在 tree-sitter-languages 中支持)**:

1. 在 `LANGUAGE_MAP` 中添加文件扩展名映射

```python
LANGUAGE_MAP = {
    # 现有语言...
    ".py": "python",
    ".js": "javascript",
    # 添加新语言
    ".kt": "kotlin",
}
```

2. 在 `CLASS_CHUNK_TYPES` 和 `FUNCTION_CHUNK_TYPES` 中配置语法节点类型

```python
CLASS_CHUNK_TYPES = {
    # 现有语言...
    "javascript": ["class_declaration"],
    # 添加新语言
    "kotlin": ["class_declaration"],
}

FUNCTION_CHUNK_TYPES = {
    # 现有语言...
    "javascript": ["function_declaration", ...],
    # 添加新语言
    "kotlin": ["function_declaration", "property_declaration"],
}
```

3. 在 `supported_exts` 中添加扩展名（如果需要）

```python
supported_exts = ('.py', '.java', '.js', '.ts', '.go', '.md', '.txt', '.rs', '.kt')
```

**备选方式: 正则模式 (Tree-sitter 不支持时)**:

1. 在 `RegexCodeSplitter` 中添加正则模式

```python
class RegexCodeSplitter(CodeSplitter):
    def __init__(self, file_ext: str):
        self.file_ext = file_ext
        self.patterns = {
            # 现有语言...
            ".js": r"\n(?=function |class |...",
            # 添加新语言
            ".kt": r"\n(?=fun |class |interface |object |val |var )",
        }
        self.indexable_prefixes = {
            # 配置可索引的前缀
        }
```

**完全自定义: 继承 CodeSplitter (需要复杂处理)**:

```python
class MyLanguageCodeSplitter(CodeSplitter):
    def split(self, content: str, max_class_length: int = 3000) -> list[str]:
        # 自定义切分逻辑
        pass

# 在 get_code_splitter() 中注册
def get_code_splitter(file_ext: str) -> CodeSplitter:
    if file_ext == ".myext":
        return MyLanguageCodeSplitter()
    # ...
```

### 添加自定义提示词

**代码方式**:

```python
from prompts.prompt_manager import PromptManager, PromptScenario, PromptLanguage

pm = PromptManager.get_instance()
pm.add_custom_prompt(
    scenario="code_review",
    language="zh-CN",
    version="1.0.0",
    template="""你是一个代码审查专家... {context} {question}""",
    input_variables=["context", "question"],
    description="代码审查提示词"
)

# 使用
prompt = pm.get_prompt(
    scenario=PromptScenario("code_review"),
    language=PromptLanguage.ZH_CN
)
```

### 自定义检索策略

**修改位置**: `agent/tools/retrieve_and_summarize.py`

**示例**: 添加重排序

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainFilter

@tool
async def RetrieveAndSummarize(question: str) -> str:
    vectordb = _service_manager.vectordb

    # 基础检索
    docs = await vectordb.asimilarity_search(question, k=20)

    # 添加重排序过滤
    compressor = LLMChainFilter.from_llm(_service_manager.summarizer_llm)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=vectordb.as_retriever(k=20)
    )

    docs = await compression_retriever.aget_relevant_documents(question)
    # ...
```

### 添加新的配置项

**步骤**:

1. 在 `config.yml` 中添加

```yaml
my_feature:
  enabled: true
  option1: "value1"
  option2: 42
```

2. 在代码中使用

```python
from utils.config import Config

enabled = Config.get("my_feature.enabled", False)
option1 = Config.get("my_feature.option1", "default")
```

---

## 性能优化建议

### 1. 索引速度优化

- **调整 chunk_size**: 增大 chunk_size 减少 chunk 数量
- **排除不必要文件**: 在 exclude_dirs/exclude_files 中添加更多规则
- **批量索引**: `index_repo.py` 已按 1024 条文档分批写入 Chroma，超大仓库可继续配合排除规则减少输入量
- **使用当前默认嵌入模型**: 默认使用 `text-embedding-v4`

### 2. 检索速度优化

- **减少 retrieval_k**: 降低检索数量
- **使用 Chroma 的持久化模式**: 避免每次重新加载
- **考虑使用更轻量的向量数据库**: 如 Qdrant

### 3. 响应速度优化

- **使用 qwen-turbo 做总结**: 比 qwen-max 快很多
- **合理设置总结层**: 有时候直接使用检索结果可能更快
- **流式输出**: 让用户更快看到第一个字

### 4. 内存优化

- **定期清理日志**: `logs/` 目录可能会很大
- **限制向量数据库大小**: 考虑只索引部分重要目录

---

## 常见问题排查

### 问题: 索引时报 "No module named 'xxx'"

**解决方案**:
```bash
pip install -r requirements.txt
```

### 问题: 检索不到相关代码

**排查方向**:
1. 检查文件是否被正确索引（看日志中的 "Total X chunks"）
2. 检查文件是否在 exclude 列表中
3. 尝试调整 retrieval_k 的数量
4. 检查问题描述是否足够具体

### 问题: 敏感文件还是被读取了

**排查方向**:
1. 检查 `config.yml` 中的 `agent.blocked_files` 配置
2. 检查文件路径是否在 `agent.allowed_dirs` 内
3. 查看日志中的 "Sensitive file access blocked" 记录

### 问题: Agent 不调用检索工具

**排查方向**:
1. 检查 Agent 的系统提示词
2. 可能问题本身不需要检索（如 "你好" 这种问候）
3. 查看 Agent 的完整执行日志

---

## 附录

### A. 项目文件速查表

| 文件 | 说明 |
|------|------|
| `app.py` | FastAPI 主应用入口 |
| `config.yml` | 应用配置文件 |
| `mcp_client_config.json` | MCP 客户端配置示例（用于 Claude Desktop 等） |
| `requirements.txt` | Python 依赖列表 |
| `agent/agent.py` | CodeMind Agent 核心类（MCP Host） |
| `agent/mcp_host.py` | MCP 客户端封装 |
| `agent/security.py` | 安全检查模块 |
| `agent/streaming.py` | 流式输出处理 |
| `agent/tools/retrieve_and_summarize.py` | 检索总结工具（仅存的本地工具） |
| `codemind_mcp/server.py` | MCP Server 入口 |
| `codemind_mcp/sdk.py` | MCP SDK 适配层 |
| `codemind_mcp/tool_impl.py` | MCP 工具实现 |
| `codemind_mcp/security.py` | MCP 安全模块代理 |
| `codemind_mcp/tool_paths.py` | MCP 工具路径代理 |
| `codemind_mcp/tools/base.py` | MCP 工具基类 |
| `codemind_mcp/tools/read_file.py` | ReadFile 工具定义 |
| `codemind_mcp/tools/search_code.py` | SearchCode 工具定义 |
| `codemind_mcp/tools/run_command.py` | RunCommand 工具定义 |
| `codemind_mcp/tools/index_manager/` | IndexManager 工具集 |
| `prompts/prompt_manager.py` | 提示词管理器 |
| `scripts/index_repo.py` | 仓库索引脚本 |
| `scripts/add_by_file_path.py` | 增量追加文件/目录到索引 |
| `scripts/delete_by_file_path.py` | 删除索引脚本 |
| `scripts/benchmark_mcp_tools.py` | MCP 工具延迟基准测试 |
| `scripts/benchmark_mcp_memory.py` | MCP 工具内存基准测试 |
| `services/service_manager.py` | 单例服务管理器 |
| `tests/test_mcp/` | MCP 相关测试 |
| `utils/config.py` | 配置管理 |
| `utils/logger.py` | 日志工具 |
| `utils/summarizer.py` | 总结模块 |
| `utils/query_rewriting.py` | 查询改写模块 |

### B. API 完整示例

**Python Requests (非流式)**:

```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "question": "解释一下这个项目的架构",
        "history": [
            {
                "role": "user",
                "content": "你好"
            },
            {
                "role": "assistant",
                "content": "你好！有什么我可以帮助你的吗？"
            }
        ]
    }
)

data = response.json()
print(data["answer"])
```

**JavaScript Fetch (流式)**:

```javascript
async function chatStream(question) {
    const response = await fetch('http://localhost:8000/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history: [] })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let result = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        result += decoder.decode(value);
        console.log(result);
    }
}

chatStream("这个项目如何使用？");
```

### C. /health 端点说明

**响应示例**:

```json
{
  "status": "ok",
  "vectordb_initialized": true,
  "agent_initialized": true,
  "mcp_host_initialized": true,
  "mcp_client_initialized": true,
  "mcp_client_healthy": true
}
```

**字段说明**:
- `status`: 整体状态 ("ok" 或 "not_initialized")
- `vectordb_initialized`: 向量数据库是否初始化
- `agent_initialized`: Agent 是否初始化
- `mcp_host_initialized`: MCP Host (Agent) 是否初始化
- `mcp_client_initialized`: MCP 客户端是否初始化
- `mcp_client_healthy`: MCP 客户端健康检查是否通过

### D. 日志级别说明

在 `utils/logger.py` 中配置:

| 级别 | 说明 |
|------|------|
| DEBUG | 详细调试信息（提示词、完整结果等） |
| INFO | 关键流程信息（检索到的来源、执行步骤等） |
| WARNING | 警告信息（跳过文件、配置缺失等） |
| ERROR | 错误信息（工具执行失败、API 错误等） |

---

## 更新日志

### v0.4.0 (当前)
- ✅ 新增多语言 Tree-sitter AST 切分支持
- ✅ 支持 JavaScript, TypeScript, JSX, TSX, Java, Go, Rust, C, C++
- ✅ 新增统一 `CodeSplitter` 抽象架构
- ✅ 新增 `PythonCodeSplitter`、`TreeSitterCodeSplitter`、`RegexCodeSplitter`
- ✅ 新增语言配置: `LANGUAGE_MAP`、`CLASS_CHUNK_TYPES`、`FUNCTION_CHUNK_TYPES`
- ✅ 自动降级机制 (Tree-sitter → Regex)
- ✅ 扩展支持的文件扩展名列表

### 4. BM25 关键词索引 (BM25 Index)

**文件**: `utils/bm25_index.py`

**为什么需要 BM25 检索？**

| 问题 | 向量检索 | BM25 检索 |
|------|---------|----------|
| 精确标识符匹配 | ❌ 语义接近但不精确 | ✅ 精确匹配标识符 |
| 特定函数/类名查找 | ❌ 可能被相似语义淹没 | ✅ 关键词精确命中 |
| 索引新增/删除成本 | ⚠️ 需要重新向量化 | ✅ 快速更新 |

如果语料很小或查询词过于常见，BM25 的 IDF 可能让命中文档得分为 0。当前实现会在这种情况下使用查询 token 与文档 token 的词频重合作为兜底分数，避免精确命中的内容被过滤掉。

**BM25 算法原理**:

BM25 是一种基于概率的信息检索算法，核心公式：
```
score(D, Q) = Σ [ IDF(q) × ( f(q,D) × (k1 + 1) ) / ( f(q,D) + k1 × (1 - b + b × |D| / avgdl) ) ]
```

其中：
- `IDF(q)`: 查询词 q 的逆文档频率
- `f(q,D)`: 查询词 q 在文档 D 中的词频
- `|D|`: 文档 D 的长度
- `avgdl`: 平均文档长度
- `k1`, `b`: 可调参数 (默认 k1=1.5, b=0.75)

**分词策略**:

```
原始文本
   ↓
按正则提取 token: [A-Za-z0-9_]+ 或 [\u4e00-\u9fff]
   ↓
Token 小写化
   ↓
拆分下划线命名: user_id → user, id
   ↓
拆分驼峰命名: UserService → User, Service
   ↓
最终 token 列表
```

**核心类**: `BM25Index`

```python
class BM25Index:
    def fit(self, documents: list[str], metadatas: list[dict]) -> BM25Index
        """构建 BM25 索引"""
        
    def search(self, query: str, k: int = 10, filter_type: str | None = None) -> list[tuple]
        """检索，支持按 metadata.type 过滤"""
        
    def delete_by_sources(self, sources: list[str]) -> int
        """按 metadata.source 删除文档并重建索引"""

    def _lexical_overlap_score(self, query_tokens: list[str], index: int) -> float
        """BM25 得分为 0 时的词面命中兜底分数"""
        
    def save(self, path: str)
        """保存索引（仅保存原始文档和 metadata）"""
        
    @classmethod
    def load(cls, path: str) -> BM25Index
        """加载索引并重建 BM25 结构"""
```

**索引持久化设计**:

- 只保存原始文档和 metadata，不保存 BM25 中间计算结果
- 加载时自动重建 BM25 结构
- 优点: 向前兼容，节省磁盘，便于更新算法

**降级机制**:

```
BM25Index.fit()
   ↓
检查: rank_bm25 库是否可用？
   ├─ 是 → 使用 RankBM25Okapi
   └─ 否 → 使用 SimpleBM25Okapi (纯 Python 实现)
```

### 5. 混合检索与 RRF 融合 (Hybrid Retrieval)

**文件**: `utils/fusion.py`, `agent/tools/retrieve_and_summarize.py`

**混合检索架构**:

```
查询文本
   ↓
   ├─────────────────────┬─────────────────────┐
   ↓                     ↓                     ↓
向量检索            BM25 检索            (可选)
   ↓                     ↓                     ↓
vector_docs          bm25_docs          (其他检索...)
vector_codes         bm25_codes
   ↓                     ↓                     ↓
   └─────────────────────┴─────────────────────┘
                       ↓
              RRF 融合 (分开融合 doc/code)
                       ↓
              fused_docs + fused_codes
                       ↓
              截断到目标数量
```

**三种检索模式** (`retrieval.mode`):

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `vector` | 仅使用向量检索 | 语义理解为主，模糊查询 |
| `bm25` | 仅使用 BM25 检索 | 精确查找函数/类名 |
| `hybrid` | 混合检索 + RRF 融合 (默认) | 平衡语义和精确匹配 |

**RRF (Reciprocal Rank Fusion) 算法**:

**为什么 RRF？**
- 无需训练，超参数少 (仅 k)
- 对不同量级的分数不敏感
- 效果稳定，业界广泛使用

**算法流程**:
```
1. 对每个结果列表 S_i:
   - 对每个结果 item 在 S_i 中的排名 rank
   - 计算 score = 1 / (rrf_k + rank)
   - 累加相同 item 的分数

2. (可选) 标识符增强:
   - 如果 item 包含查询中的标识符
   - 额外加 identifier_boost 分

3. 按最终分数降序排序
```

**实现细节**:

```python
def rrf_fuse(
    ranked_lists: list[list[Any]],  # 多个结果列表
    rrf_k: int = 60,
    identifier_query: str | None = None,
    identifier_boost: float = 0.0
) -> list[dict[str, Any]]
```

**去重策略**:

使用 `(source_path, content_sha1)` 作为唯一键:
- `source_path`: metadata.source (文件路径)
- `content_sha1`: 内容的 SHA1 哈希

这样可以正确处理:
- 同一文件的同一内容 → 完全相同，合并
- 同一文件的不同版本 → 不同哈希，保留
- 不同文件的相同内容 → 不同路径，都保留

**混合检索流程** (`_retrieve_documents()`):

```
1. 读取配置:
   - retrieval.mode
   - retrieval_k (向量检索数量)
   - bm25_retrieval_k (BM25 检索数量)

2. 向量检索 (mode 为 vector/hybrid):
   - doc 检索: retrieval_k.docs
   - code 检索: retrieval_k.codes

3. BM25 检索 (mode 为 bm25/hybrid):
   - doc 检索: bm25_retrieval_k.docs
   - code 检索: bm25_retrieval_k.codes

4. 根据 mode 决定返回:
   - bm25: 仅返回 BM25 结果
   - vector: 仅返回向量结果
   - hybrid: RRF 融合后返回

5. 融合设计:
   - doc 和 code 分开融合
   - 融合后各自截断到目标数量
   - 保证 doc/code 比例
```

**Service Manager 集成**:

```python
class ServiceManager:
    @property
    def bm25_index(self) -> BM25Index | None
        """BM25 索引服务（索引不存在时为 None）"""
    
    @property
    def bm25_retrieval_k(self) -> dict
        """BM25 检索数量配置"""
    
    @property
    def retrieval_config(self) -> dict
        """检索策略配置 (mode, rrf_k, identifier_boost)"""
```

### 6. 索引追加 (Add Index)

**文件**: `scripts/add_by_file_path.py`

**功能**: 将指定文件或目录下的可索引文件增量追加到 Chroma 向量索引和 BM25 关键词索引。

**设计要点**:

- 只负责收集用户指定路径下的可索引文件，文件类型和排除规则复用 `index_repo.py`。
- 单个文件会先判断是否是支持的代码或文档文件；目录会递归遍历并原地跳过排除目录。
- 文件路径会标准化为绝对路径并使用正斜杠，保持与 `metadata.source` 的格式一致。
- 切分逻辑复用 `build_chunks()`，写入逻辑复用 `save_indexes()`，避免增量追加与全量重建的规则漂移。
- 写入前会基于 `chunk_hash` 去重；已有 BM25/Chroma 中存在的分块不会重复写入。

**追加流程**:

```
1. 读取 config.yml
   ├─ chroma.persist_dir
   ├─ bm25.persist_path
   └─ embeddings.model

2. 收集指定路径下的可索引文件
   ├─ 文件: 判断扩展名和排除规则
   └─ 目录: 递归扫描并跳过排除目录

3. 复用全量索引流程
   ├─ build_chunks(file_paths)
   ├─ deduplicate_chunks_by_hash(chunks)
   └─ save_indexes(chunks, persist_dir, embedding_model, bm25_persist_path)
```

**使用示例**:

```bash
# 追加单个文件
python scripts/add_by_file_path.py /path/to/file.py

# 追加整个目录
python scripts/add_by_file_path.py /path/to/directory

# 指定 Chroma 持久化目录
python scripts/add_by_file_path.py /path/to/file.py --persist-dir ./chroma_db
```

### 7. 索引删除 (Delete Index)

**文件**: `scripts/delete_by_file_path.py`

**功能**: 同时删除 Chroma 向量索引和 BM25 关键词索引

**删除流程**:

```
1. 收集目标文件路径:
   - 如果是文件: 标准化路径
   - 如果是目录: 递归遍历所有文件

2. 从 Chroma 中删除:
   - 批量查询: where {"$or": [{"source": src1}, {"source": src2}, ...]}
   - 批量删除: vectordb.delete(ids=...)

3. 从 BM25 中删除:
   - 加载 BM25 索引
   - 调用 bm25_index.delete_by_sources(sources)
   - 保存更新后的索引
```

**使用示例**:

```bash
# 删除单个文件
python scripts/delete_by_file_path.py /path/to/file.py

# 删除整个目录
python scripts/delete_by_file_path.py /path/to/directory
```

---

### v0.7.0 (当前)
- ✅ 新增 MCP (Model Context Protocol) 架构支持
- ✅ 新增 `codemind_mcp/` 目录，包含完整的 MCP Server 实现
- ✅ 新增 `agent/mcp_host.py`，Agent 作为 MCP Host 调用 MCP Server
- ✅ 迁移 ReadFile/SearchCode/RunCommand 工具到 MCP Server
- ✅ 新增 IndexManager 工具集（IndexRepo/AddByFilePath/DeleteByFilePath）到 MCP Server
- ✅ 支持两种 transport 模式: stdio（独立子进程）和 local（同一进程）
- ✅ 新增 MCP 工具动态加载和 LangChain StructuredTool 适配
- ✅ 新增 MCP 相关配置项到 `config.yml`
- ✅ 更新 `/health` 端点，新增 MCP 相关状态字段
- ✅ 新增基准测试脚本: `benchmark_mcp_tools.py` / `benchmark_mcp_memory.py`
- ✅ 新增完整的 MCP 测试套件: `tests/test_mcp/`
- ✅ 新增 `mcp_client_config.json` 示例配置，用于 Claude Desktop 等 MCP 客户端

### v0.6.0
- ✅ 新增 `scripts/add_by_file_path.py`，支持按文件或目录增量追加到 RAG 索引
- ✅ 重构 `scripts/index_repo.py`，将扫描、切分、写入拆为 `collect_repo_files()` / `build_chunks()` / `save_indexes()`
- ✅ 新增基于 SHA-256 内容的 `chunk_hash` metadata
- ✅ 新增索引写入前去重：本次分块去重、已有 BM25 metadata 去重、已有 Chroma metadata 去重
- ✅ 增量追加时会加载并合并已有 BM25 文档后重建保存，避免覆盖旧索引
- ✅ 默认嵌入模型调整为 `text-embedding-v4`

### v0.5.0
- ✅ 新增 BM25 关键词索引
- ✅ 新增混合检索模式 (vector + BM25)
- ✅ 新增 RRF (Reciprocal Rank Fusion) 结果融合算法
- ✅ 新增标识符匹配增强功能
- ✅ 新增 BM25 零 IDF 场景下的词面重合兜底得分
- ✅ 新增 `utils/bm25_index.py` 模块
- ✅ 新增 `utils/fusion.py` 模块
- ✅ 更新 `index_repo.py` 同时构建 BM25 索引，并按 1024 条文档分批写入 Chroma
- ✅ 更新 `index_repo.py` 遍历时原地过滤目录，只索引支持的代码和文档文件
- ✅ 更新代码索引策略：语义块直接生成 Document，按 `chunk_size.code` 截断，不再二次递归切分
- ✅ 更新 `delete_by_file_path.py` 同时删除两类索引
- ✅ 更新 `ServiceManager` 集成 BM25 服务
- ✅ 更新 `RetrieveAndSummarize` 工具支持混合检索
- ✅ 新增 `config.yml` 配置项: `bm25.*`, `retrieval.*`
- ✅ 默认嵌入模型调整为 `text-embedding-v1`
- ✅ 总结提示词要求追加相关文件路径
- ✅ 新增完整测试覆盖

### v0.4.0
- ✅ 新增 Query Rewriting 查询改写功能
- ✅ 新增关键词提取模块
- ✅ 新增回答推测模块
- ✅ 新增 PromptScenario 枚举值
- ✅ 新增 query_rewriting_llm 服务
- ✅ 优化检索策略，使用增强检索文本

### v0.2.0
- ✅ 新增 Agent 模式
- ✅ 新增安全检查模块
- ✅ 新增流式输出支持
- ✅ 优化 Python AST 切分
- ✅ 新增 ServiceManager 单例管理

### v0.1.0
- ✅ 基础 RAG 问答功能
- ✅ Python 代码智能切分
- ✅ Chroma 向量数据库集成
