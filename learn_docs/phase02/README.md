# Phase02：Agent 智能体进阶

恭喜你完成了 Phase01 的学习！在 Phase01 中，我们构建了一个基础的 RAG 系统，能够检索代码并生成回答。

在 Phase02 中，我们将更进一步，引入 **Agent（智能体）** 概念，让系统能够主动调用工具来深入分析代码库！

## 本阶段新增内容

| 模块 | 文件 | 功能 |
|------|------|------|
| **Agent 核心** | `agent/agent.py` | Agent 创建与执行逻辑，集成 LangChain 1.0 新 API |
| **流式处理** | `agent/streaming.py` | Agent 流式输出格式化和异步/同步桥接 |
| **安全模块** | `agent/security.py` | 路径、文件、命令三重安全验证 |
| **工具集** | `agent/tools/*.py` | ReadFile、SearchCode、RunCommand 三个工具 |
| **服务管理** | `services/service_manager.py` | 服务单例管理，统一管理所有服务生命周期 |
| **RAG 上下文** | `rag/context_builder.py` | RAG 上下文构建、文档拼接、摘要压缩 |
| **提示词管理** | `prompts/prompt_manager.py` | 提示词版本管理、多语言、多场景支持 |

## 阅读顺序

1. **[01-Agent原理入门.md](./01-Agent原理入门.md)** - 理解 Agent 是什么，ReAct 模式如何工作
2. **[02-安全模块详解.md](./02-安全模块详解.md)** - 学习如何设计安全检查机制
3. **[03-Agent工具实现.md](./03-Agent工具实现.md)** - 逐个解析三个工具的实现
4. **[04-Agent核心逻辑.md](./04-Agent核心逻辑.md)** - 深入 Agent 核心代码，了解 LangChain 1.0 API 迁移
5. **[05-完整集成与测试.md](./05-完整集成与测试.md)** - 学习如何集成 Agent 并进行测试
6. **[06-架构优化进阶.md](./06-架构优化进阶.md)** - 了解服务管理、RAG 上下文、提示词管理等架构优化

## 学习目标

完成 Phase02 后，你将掌握：
- ✅ Agent 的基本概念和 ReAct 模式
- ✅ 如何使用 LangChain 1.0 的新 Agent API
- ✅ 如何设计和实现安全检查机制
- ✅ 如何使用 @tool 装饰器定义工具
- ✅ 如何将 Agent 集成到现有系统中
- ✅ 如何设计服务单例管理器
- ✅ 如何封装 RAG 上下文处理逻辑
- ✅ 如何管理提示词的版本和多场景

## 前置知识

在开始之前，确保你已经完成了 Phase01 的学习：
- 理解 RAG 原理
- 熟悉项目基础代码结构
- 了解 FastAPI、LangChain 等基础组件

准备好了吗？让我们开始吧！
