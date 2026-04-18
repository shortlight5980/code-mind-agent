# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## 注意事项

LangChain版本为1.x以上，注意使用新版本的api

每次修改、添加或删除文件后，你都需要思考本次修改会对该项目带来什么影响，应该如何处理这种影响，比如需要增加gitignore还是需要其他动作之类的

每次修改、添加或删除文件后，你都需要询问我是否需要同步修改相关文档，如果我回答是，你应该进行如下动作：

- 同步修改项目根目录下learn_docs/phase03/下的所有教学文件（如果没有就创建，撰写教学文档时使用md格式，将phase01、phase02已经教学过的内容排除），且应注意不要描述为：修改了/新增了/删除了等等，而是将修改后的项目看作完整项目而修改教学文档

- 在项目根目录下docs/文件夹中创建本次修改总结，以时间（精确到分）+修改总结命名。如果两次修改时间很接近（15min之内）就合并两次修改到一个文件中（这里的合并不是单纯的add,而是融合，也就是说，相对于第一次修改之前的版本，直到第二次修改修改了什么）

- CLAUDE.md

所有注释一律用中文！


## 项目概述

CodeMind Agent 是一个基于 RAG (检索增强生成) 和 LangChain Agent 的代码仓库智能问答系统。用户可以用自然语言提问关于代码库的问题，系统会检索相关代码片段并通过 Agent 调用工具进行深度分析，最终生成回答。

## 常用命令

### 环境设置
```bash
conda activate AI
pip install -r requirements.txt
```

### 索引代码仓库
```bash
python scripts/index_repo.py /path/to/repo
```

### 启动服务
```bash
python app.py
# 或
uvicorn app:app --reload
```

### 服务访问
- Swagger UI: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- 问答接口: POST http://localhost:8000/chat

## 架构概览

### 核心文件

| 文件/目录 | 职责 |
|----------|------|
| `app.py` | FastAPI 主应用，提供 /chat 和 /health 接口 |
| `scripts/index_repo.py` | 索引脚本，将代码库向量化并存入 Chroma |
| `utils/logger.py` | 单例日志工具 |
| `utils/config.py` | 配置加载工具（config.yml + .env） |
| `utils/summarizer.py` | 总结层模块，对检索结果进行总结提炼 |
| `prompts/` | 提示词管理目录 |
| `prompts/prompt_manager.py` | 提示词管理器，统一管理所有提示词 |
| `agent/` | Agent 核心模块目录 |
| `agent/agent.py` | Agent 创建与执行逻辑 |
| `agent/security.py` | 安全检查模块（路径、文件、命令验证） |
| `agent/tools/` | Agent 工具目录（ReadFile、SearchCode、RunCommand） |
| `config.yml` | 应用配置（模型、参数、Agent 配置等） |
| `.env` | 环境变量（仅 DASHSCOPE_API_KEY） |

### 数据流向

#### 索引阶段:
```
代码文件 → 智能切分（保留完整类）→ Embedding → Chroma DB
```

#### 查询阶段（Agent 模式）:
```
用户问题 → Chroma 检索 → 总结模块（summarizer）→ Agent 初始化 → 工具调用循环 → 最终回答
                ↓
            相关文档
```

#### Agent 执行流程:
1. **接收任务**：Agent 获得用户自然语言指令
2. **推理与规划**：LLM 生成 Thought，决定调用哪个工具
3. **工具执行**：LangChain 自动解析并调用工具函数（含安全检查）
4. **观察结果**：工具返回结果追加到对话上下文
5. **循环直至完成**：重复上述步骤，直至输出 Final Answer

### Agent 工具列表

| 工具名称 | 功能描述 | 安全限制 |
|---------|---------|---------|
| `ReadFile` | 读取指定仓库文件内容（支持行号范围） | 仅允许白名单目录；禁止读取敏感文件（.env、*.key 等） |
| `SearchCode` | 基于关键词或正则表达式在代码库中搜索 | 搜索范围限定于授权仓库；结果上限 50 条 |
| `RunCommand` | 执行只读 shell 命令（ls、cat、grep、git 等） | 命令白名单；超时 5 秒；禁用 shell=True |

### 关键技术决策

1. **Chroma 导入**: 使用 `langchain_chroma` 而非 `langchain_community`
2. **FastAPI Lifespan**: 使用 `@asynccontextmanager` 替代已弃用的 `@app.on_event`
3. **代码切分**: Python 代码优先保留完整类（<3000 字符），超长类才按方法切分
4. **配置分离**: `config.yml` 存公开配置，`.env` 存敏感信息
5. **单例日志**: `utils.logger.get_logger()` 防止重复初始化
6. **LangChain @tool**: 使用 `@tool` 装饰器定义工具，通过 AgentExecutor 统一管理
7. **安全检查**: 工具调用前进行路径、文件、命令三重安全验证
8. **总结前置**: 总结模块在 Agent 执行前运行，减少 token 消耗
9. **提示词统一管理**: 通过 `PromptManager` 单例统一管理所有提示词，支持版本控制和多语言

## 学习文档

项目包含详细的学习文档，位于 `learn_docs/` 目录：

**Phase 01：基础架构**
- `learn_docs/phase01/01-项目总览.md`
- `learn_docs/phase01/02-技术栈详解.md`
- `learn_docs/phase01/03-RAG原理入门.md`
- `learn_docs/phase01/04-代码结构解析.md`
- `learn_docs/phase01/05-快速上手指南.md`

**Phase 02：Agent与高级功能**
- `learn_docs/phase02/01-Agent原理入门.md`
- `learn_docs/phase02/02-安全模块详解.md`
- `learn_docs/phase02/03-Agent工具实现.md`
- `learn_docs/phase02/04-Agent核心逻辑.md`
- `learn_docs/phase02/05-完整集成与测试.md`
- `learn_docs/phase02/06-架构优化进阶.md`

**Phase 03：最新更新**
- `learn_docs/phase03/`（包含最新的架构更新内容）
