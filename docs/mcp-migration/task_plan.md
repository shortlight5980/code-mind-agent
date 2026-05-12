# Task Plan: 混合式MCP架构迁移执行计划
<!-- 
  WHAT: 这是混合式MCP架构迁移的完整路线图。
  WHY: 将方案二的6个阶段转化为可执行的计划文档。
-->

## Goal
根据方案二（混合式MCP）的设计，完成 MCP 服务、工具迁移、索引包装与验证。

## Current Phase
Phase 6: 集成测试与文档补完（进行中）

## Phases

### Phase 1: 项目现状调研 & 文档整理
- [x] 分析现有代码库结构
- [x] 确认待迁移模块清单
- [x] 记录关键文件路径与依赖关系
- **Status:** completed

### Phase 2: 详细设计文档撰写
- [x] 编写MCP服务器架构设计文档
- [x] 定义工具迁移接口规范
- [x] 设计配置共享方案
- [x] 绘制完整架构图（Mermaid）
- **Status:** completed

### Phase 3: MCP服务器框架搭建
- [x] 创建 `mcp/` 与 `mcp/tools/` 目录结构
- [x] 实现 `mcp/server.py`
- [x] 实现 `mcp/tools/base.py`
- [x] 复用共享模块入口 `mcp/security.py`、`mcp/tool_paths.py`
- [x] 更新 `requirements.txt`
- **Status:** completed

### Phase 4: 工具迁移
- [x] 迁移 `ReadFile`
- [x] 迁移 `SearchCode`
- [x] 迁移 `RunCommand`
- [x] 保留原 `agent/tools/*` 降级路径
- **Status:** completed

### Phase 5: 索引脚本包装与测试
- [x] 包装 `index_repo`
- [x] 包装 `add_by_file_path`
- [x] 包装 `delete_by_file_path`
- [x] 创建 `tests/test_mcp/` 测试集
- [x] 运行 MCP 测试与原工具回归测试
- **Status:** completed

### Phase 6: 集成测试与文档补完
- [ ] Claude Desktop 端到端联调
- [ ] MCP 服务器真实 stdio 启动验证
- [ ] 性能基准测试
- [ ] 更新 README / 部署与使用说明
- **Status:** in_progress

## Key Questions
1. 现有agent/tools/中哪些工具需要迁移，哪些需要保留？
2. 如何实现security.py等模块的共享而不重复代码？
3. 配置文件如何在FastAPI和MCP服务间共享？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 采用方案二：混合式MCP | 平衡性能与生态复用，核心检索保留在原应用，工具类迁移到MCP |
| 先完成文档撰写，再开始编码 | 确保设计清晰，减少返工 |
| 保留原应用工具副本作为降级路径 | 降低迁移风险，可随时切换回 |
| MCP 层优先包装现有实现 | 避免与原工具逻辑漂移，降低迁移回归风险 |
| 为本地 `mcp/` 包增加 SDK 兼容加载层 | 规避仓库目录名与第三方 `mcp` SDK 的命名冲突 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 暂无 | - | - |

## Notes
- Update phase status as you progress: pending → in_progress → complete
- Re-read this plan before major decisions
- Log ALL errors
