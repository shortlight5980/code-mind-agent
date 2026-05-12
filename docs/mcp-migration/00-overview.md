# 混合式MCP架构迁移 - 概述

## 设计目标

基于用户要求的混合式MCP架构设计，实现以下目标：

1. **性能优先** - 核心检索功能（RetrieveAndSummarize、Chroma、BM25）保留在原FastAPI应用中，避免IPC开销
2. **生态复用** - 工具类功能（ReadFile、SearchCode、RunCommand、索引脚本）迁移到MCP服务，可被Claude Desktop等其他客户端使用
3. **Agent作为MCP客户端** - 原FastAPI应用中的Agent通过MCP客户端调用独立的MCP服务，而不是直接使用本地工具
4. **渐进迁移** - 分8个阶段逐步迁移，每个阶段可独立验证、可回滚
5. **降级保护** - 原应用保留工具副本作为降级路径，迁移出现问题时可随时切换回原实现

## 架构总览

### 当前架构
```
FastAPI → ServiceManager → CodeMindAgent → 本地 LangChain Tools
```

### 目标架构
```
FastAPI → ServiceManager → CodeMindAgent → MCP代理工具 → MCP客户端 → MCP服务
                                                              ↓
                                                    RetrieveAndSummarize（本地）
```

## 职责边界划分

| 模块 | 部署位置 | 理由 |
|------|----------|------|
| RetrieveAndSummarize | 原FastAPI应用 | 需要频繁访问向量DB + BM25，性能敏感 |
| Chroma | 原FastAPI应用 | 检索性能关键，避免IPC开销 |
| BM25索引 | 原FastAPI应用 | 内存映射访问，性能敏感 |
| 查询改写 & 摘要LLM | 原FastAPI应用 | 与检索流程深度耦合 |
| ServiceManager | 原FastAPI应用 | 核心服务生命周期管理，新增MCP客户端管理 |
| FastAPI端点 | 原FastAPI应用 | /chat, /chat/stream, /health |
| **MCPClient** | **原FastAPI应用** | **新增：管理MCP服务连接，工具调用代理** |
| **MCP代理工具** | **原FastAPI应用** | **新增：对Agent透明的MCP工具包装** |
| ReadFile | MCP服务 | 纯文件操作，可独立复用 |
| SearchCode | MCP服务 | 代码搜索（基于文件），可独立复用 |
| RunCommand | MCP服务 | 命令执行，需沙箱隔离 |
| 索引脚本 | MCP服务 | 索引操作是异步的，可独立运行，暂不暴露给Agent |

## 术语定义

| 术语 | 说明 |
|------|------|
| MCP | Model Context Protocol，模型上下文协议 |
| FastAPI应用 | 原有的CodeMind Agent后端服务 |
| MCP服务 | 新创建的独立MCP服务器进程（mcp/server.py） |
| MCP客户端 | 新增的模块（agent/mcp_client.py），负责连接和调用MCP服务 |
| MCP代理工具 | 新增的Agent工具（agent/tools/mcp_*.py），内部调用MCP客户端 |
| 共享模块 | security.py、config.py、logger.py等可被两个服务共用的模块 |
| 工具 | LangChain Tool或MCP Tool的统称 |
| 降级 | MCP调用失败时，自动切回使用原本地工具 |

## 关键设计决策

### 1. RetrieveAndSummarize 保留本地
- 强依赖 ServiceManager、Chroma、BM25、Summarizer
- 改动风险大，暂不迁移
- 后续可考虑重构，但当前优先迁移工具类

### 2. Agent 侧工具名称保持不变
- 继续使用 ReadFile、SearchCode、RunCommand
- Agent prompt 无需修改
- 内部通过代理调用 MCP

### 3. 索引工具暂不暴露给 Agent
- 先给后台管理接口或脚本使用
- 降低初始迁移风险
- 稳定后再考虑是否暴露

### 4. 降级机制
- 配置 `mcp.fallback_to_local: true`
- MCP 调用失败时自动切回本地工具
- 对 Agent 透明
