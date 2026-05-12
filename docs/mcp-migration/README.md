# 混合式MCP架构迁移 - 设计文档

## 概述

本文档描述了将 CodeMind Agent 迁移到混合式 MCP 架构的详细设计和执行计划。

## 文档导航

| 文档 | 说明 |
|------|------|
| [00-overview.md](./00-overview.md) | 方案概述、设计目标、职责边界 |
| [01-architecture.md](./01-architecture.md) | 系统架构、目录结构、共享模块方案 |
| [02-mcp-server-design.md](./02-mcp-server-design.md) | MCP服务器设计、工具基类、工具实现 |
| [03-phased-migration.md](./03-phased-migration.md) | 分阶段迁移计划、验收标准、回滚方案 |
| [04-risk-assessment.md](./04-risk-assessment.md) | 风险评估、回滚策略、监控要点 |
| [05-implementation-checklist.md](./05-implementation-checklist.md) | 实施检查清单 |
| [06-claude-desktop-validation.md](./06-claude-desktop-validation.md) | Claude Desktop 手工联调步骤与验收清单 |

## 快速开始

### 了解方案

先阅读 [00-overview.md](./00-overview.md) 了解整体设计理念。

### 架构设计

然后阅读 [01-architecture.md](./01-architecture.md) 了解系统架构和目录结构。

### 详细设计

接着阅读 [02-mcp-server-design.md](./02-mcp-server-design.md) 了解 MCP 服务器的具体实现细节。

### 执行计划

最后按照 [03-phased-migration.md](./03-phased-migration.md) 的分阶段计划开始实施。

## 核心原则

1. **性能优先** - 核心检索保留在原 FastAPI 应用
2. **生态复用** - 工具类迁移到 MCP 服务
3. **渐进迁移** - 分 6 个阶段，可独立验证
4. **降级保护** - 保留原工具副本作为降级路径

## 核心决策

| 决策 | 说明 |
|------|------|
| 保留模块 | RetrieveAndSummarize、Chroma、BM25、ServiceManager |
| 迁移模块 | ReadFile、SearchCode、RunCommand、索引脚本 |
| 共享模块 | security.py、config.py、logger.py、tool_paths.py |
| 共享方式 | 符号链接 + 直接导入 |

## 联系方式

如有问题，请参考各文档中的详细说明。
