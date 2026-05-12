# 混合式MCP架构迁移 - 概述

## 设计目标

基于方案二（混合式MCP）的设计理念，实现以下目标：

1. **性能优先** - 核心检索功能（RetrieveAndSummarize、Chroma、BM25）保留在原FastAPI应用中，避免IPC开销
2. **生态复用** - 工具类功能（ReadFile、SearchCode、RunCommand、索引脚本）迁移到MCP服务，可被Claude Desktop等其他客户端使用
3. **渐进迁移** - 分6个阶段逐步迁移，每个阶段可独立验证、可回滚
4. **降级保护** - 原应用保留工具副本作为降级路径，迁移出现问题时可随时切换回原实现

## 职责边界划分

| 模块 | 部署位置 | 理由 |
|------|----------|------|
| RetrieveAndSummarize | 原FastAPI应用 | 需要频繁访问向量DB + BM25，性能敏感 |
| Chroma | 原FastAPI应用 | 检索性能关键，避免IPC开销 |
| BM25索引 | 原FastAPI应用 | 内存映射访问，性能敏感 |
| 查询改写 & 摘要LLM | 原FastAPI应用 | 与检索流程深度耦合 |
| ServiceManager | 原FastAPI应用 | 核心服务生命周期管理 |
| FastAPI端点 | 原FastAPI应用 | /chat, /chat/stream, /health |
| ReadFile | MCP服务 | 纯文件操作，可独立复用 |
| SearchCode | MCP服务 | 代码搜索（基于文件），可独立复用 |
| RunCommand | MCP服务 | 命令执行，需沙箱隔离 |
| 索引脚本 | MCP服务 | 索引操作是异步的，可独立运行 |

## 术语定义

| 术语 | 说明 |
|------|------|
| MCP | Model Context Protocol，模型上下文协议 |
| FastAPI应用 | 原有的CodeMind Agent后端服务 |
| MCP服务 | 新创建的独立MCP服务器进程 |
| 共享模块 | security.py、config.py、logger.py等可被两个服务共用的模块 |
| 工具 | LangChain Tool或MCP Tool的统称 |
