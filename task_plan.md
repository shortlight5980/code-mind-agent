# MCP Extraction Plan

## Goal
为 `code-mind-agent` 设计一套重构方案：将 `read_file`、`run_command`、`search_code` 完全抽取到 MCP 服务侧；Agent 原服务不得再直接暴露或本地回退这三个工具；其他原计划迁移到 MCP 的工具暂不迁移，保留原有本地实现。

## Scope
- 仅关注 `code-mind-agent`
- 当前阶段仅做方案设计，不修改业务代码

## Constraints
- Agent 对外仍保持相同的三个工具语义能力，但调用路径必须是 MCP-only
- 原服务内不允许再存在这三个工具的可选本地注册路径
- MCP 侧承载唯一运行实现，避免与 Agent 本地实现形成双份事实来源
- 其他工具，尤其 `RetrieveAndSummarize`，本阶段保留原有本地实现

## Phases
- [x] Phase 1: 盘点当前 Agent/MCP 工具注册与调用链
- [x] Phase 2: 识别与目标架构冲突的设计点
- [x] Phase 3: 输出重构方案、模块边界、迁移步骤与测试策略

## Open Questions
- 是否还需要继续清理历史迁移文档中关于 `mcp.enabled` 与 fallback 的描述

## Risks
- 当前 `mcp/tools/*` 只是对 `agent/tools/*` 的薄包装，直接删除本地工具会导致 MCP 侧失效
- 当前 `get_agent_toolset()` 与 `mcp.fallback_to_local` 都内建了本地回退分支，和目标架构冲突
