# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 注意事项

每次修改、添加或删除文件后，你都需要思考本次修改会对该项目带来什么影响，应该如何处理这种影响，比如需要增加gitignore还是需要其他动作之类的

每次修改、添加或删除文件后，你都需要询问我是否需要同步修改相关文档，如果我回答是，你应该进行如下动作：

- 同步修改项目根目录下learn_docs/phase01/下的所有教学文件，且应注意不要描述为：修改了/新增了/删除了等等，而是将将修改后的项目看作完整项目而修改教学文档

- 在项目根目录下docs/文件夹中创建本次修改总结，以时间（精确到分）+修改总结命名。如果两次修改时间很接近（15min之内）就合并两次修改到一个文件中（这里的合并不是单纯的add,而是融合，也就是说，相对于第一次修改之前的版本，直到第二次修改修改了什么）

所有注释一律用中文！


## 项目概述

CodeMind Agent 是一个基于 RAG (检索增强生成) 的代码仓库智能问答系统。用户可以用自然语言提问关于代码库的问题，系统会检索相关代码片段并调用 LLM 生成回答。

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
| `config.yml` | 应用配置（模型、参数等） |
| `.env` | 环境变量（仅 DASHSCOPE_API_KEY） |

### 数据流向

```
索引阶段:
代码文件 → 智能切分（保留完整类）→ Embedding → Chroma DB

查询阶段:
用户问题 → Embedding → Chroma 检索 → PromptTemplate → LLM → 回答 + 来源
```

### 关键技术决策

1. **Chroma 导入**: 使用 `langchain_chroma` 而非 `langchain_community`
2. **FastAPI Lifespan**: 使用 `@asynccontextmanager` 替代已弃用的 `@app.on_event`
3. **代码切分**: Python 代码优先保留完整类（<3000 字符），超长类才按方法切分
4. **配置分离**: `config.yml` 存公开配置，`.env` 存敏感信息
5. **单例日志**: `utils.logger.get_logger()` 防止重复初始化

## 学习文档

项目包含详细的学习文档，位于 `learn_docs/phase01/`：
- 01-项目总览.md
- 02-技术栈详解.md
- 03-RAG原理入门.md
- 04-代码结构解析.md
- 05-快速上手指南.md
