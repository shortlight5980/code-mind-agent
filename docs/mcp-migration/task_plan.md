# Task Plan: 混合式MCP架构迁移执行计划
<!-- 
  WHAT: 这是混合式MCP架构迁移的完整路线图。
  WHY: 将方案二的6个阶段转化为可执行的计划文档。
-->

## Goal
根据方案二（混合式MCP）的设计，完成详细执行计划的文档撰写，为后续代码实现提供清晰指导。

## Current Phase
(文档阶段已完成)

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

### Phase 3: 分阶段实施计划细化
- [x] 细化阶段一：MCP服务器框架搭建
- [x] 细化阶段二：ReadFile迁移
- [x] 细化阶段三：SearchCode迁移
- [x] 细化阶段四：RunCommand迁移
- [x] 细化阶段五：索引脚本包装
- [x] 细化阶段六：集成测试 & 文档
- **Status:** completed

### Phase 4: 风险评估与缓解方案
- [x] 识别技术风险点
- [x] 制定降级方案
- [x] 设计回滚策略
- **Status:** completed

### Phase 5: 交付物整理
- [x] 整理所有设计文档
- [x] 创建实施检查清单
- [x] 编写开发指南
- **Status:** completed

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

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 暂无 | - | - |

## Notes
- Update phase status as you progress: pending → in_progress → complete
- Re-read this plan before major decisions
- Log ALL errors
