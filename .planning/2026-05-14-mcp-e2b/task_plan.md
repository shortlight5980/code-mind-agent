# Task Plan: MCP工具E2B沙箱重构

## Goal
将代码库中的MCP工具迁移到E2B沙箱环境中执行，提高系统安全性。

## Current Phase
Phase 4

## Phases

### Phase 1: 代码结构研究
- [x] 探索当前项目结构
- [x] 定位MCP工具相关代码
- [x] 分析工具调用机制
- [x] 研究E2B沙箱的集成方式
- [x] 文档发现到findings.md
- **Status:** complete

### Phase 2: 架构设计
- [x] 定义沙箱集成方案
- [x] 设计工具沙箱化接口
- [x] 确定配置管理方式
- [x] 文档设计决策
- **Status:** complete

### Phase 3: 实现规划
- [x] 列出需要修改的文件
- [x] 定义实现步骤
- [x] 确定测试策略
- **Status:** complete

### Phase 4: 交付重构计划
- [x] 整理完整的重构计划文档
- [x] 确保计划可执行
- [x] 交付给用户
- **Status:** complete

## Key Questions
1. 项目中有哪些MCP工具？ - ReadFile, SearchCode, RunCommand, Index管理工具
2. 当前工具是如何调用的？ - 通过MCP服务器，本地直接执行
3. E2B沙箱的API是什么？ - 需要使用E2B Python SDK
4. 如何最小化对现有代码的改动？ - 通过适配器模式

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 采用适配器模式集成E2B | 最小化对现有代码的改动，保持API兼容性 |
| 创建`E2BSandbox`类封装E2B SDK | 统一管理沙箱生命周期和操作 |
| 创建`SandboxedToolExecutor`类 | 在沙箱中执行工具逻辑，保持工具接口不变 |
| 支持配置切换本地/沙箱模式 | 通过`config.yml`配置使用哪种模式 |
| 保持现有安全检查作为第一道防线 | 安全检查仍在本地执行，沙箱作为第二道防线 |
| 索引管理工具继续在本地执行 | 索引操作需要访问本地向量数据库，不适合沙箱化 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       |         |            |

## Notes
- Update phase status as you progress: pending → in_progress → complete
- Re-read this plan before major decisions
- Log ALL errors - they help avoid repetition
