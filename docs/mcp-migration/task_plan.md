# Task Plan: Agent 作为 MCP 客户端的混合架构迁移执行计划
<!-- 
  WHAT: 这是完整的 MCP 架构迁移路线图，包括 MCP 服务端和客户端。
  WHY: 将 Agent 改造为通过 MCP 客户端调用独立 MCP 服务，同时保留核心检索在本地。
-->

## Goal
实现完整的 MCP 混合架构：
- MCP server 提供工具能力（ReadFile、SearchCode、RunCommand、索引管理）
- Agent 作为 MCP client，通过代理工具调用 MCP server
- RetrieveAndSummarize 继续保留在本地
- 支持降级机制，风险可控

## Current Phase
Phase 7: 集成测试与验证（进行中）

## Phases

### Phase 1: 项目现状调研 & 文档整理
- [x] 分析现有代码库结构
- [x] 确认待迁移模块清单
- [x] 记录关键文件路径与依赖关系
- **Status:** completed

### Phase 2: MCP服务器框架搭建
- [x] 创建 `mcp/` 与 `mcp/tools/` 目录结构
- [x] 实现 `mcp/server.py`
- [x] 实现 `mcp/tools/base.py`
- [x] 复用共享模块入口 `mcp/security.py`、`mcp/tool_paths.py`
- [x] 更新 `requirements.txt`
- **Status:** completed

### Phase 3: 工具迁移（MCP服务端）
- [x] 迁移 `ReadFile` → `codemind_read_file`
- [x] 迁移 `SearchCode` → `codemind_search_code`
- [x] 迁移 `RunCommand` → `codemind_run_command`
- [x] 保留原 `agent/tools/*` 降级路径
- **Status:** completed

### Phase 4: 索引脚本包装（MCP服务端）
- [x] 包装 `index_repo`
- [x] 包装 `add_by_file_path`
- [x] 包装 `delete_by_file_path`
- [x] 创建 `tests/test_mcp/` 测试集
- [x] 运行 MCP 测试与原工具回归测试
- **Status:** completed

### Phase 5: MCP客户端层实现（新增）
- [x] 创建 `agent/mcp_client.py`
  - [x] 实现 MCPClient 类，管理 MCP server 子进程
  - [x] 实现 list_tools()
  - [x] 实现 call_tool()
  - [x] 实现超时控制
  - [x] 实现健康检查
- [x] 更新 `services/service_manager.py`
  - [x] 集成 MCP client 生命周期
  - [x] 提供访问接口
- [x] 更新 `utils/config.py`
  - [x] 增加 MCP 配置段
- [x] 创建 `tests/test_mcp/test_client.py`
- **Status:** completed

### Phase 6: Agent侧MCP代理工具（新增）
- [x] 创建 `agent/tools/mcp_read_file.py`
- [x] 创建 `agent/tools/mcp_search_code.py`
- [x] 创建 `agent/tools/mcp_run_command.py`
- [x] 更新 `agent/tools/__init__.py`
- [x] 更新 `agent/agent.py` 的 `get_tools()` 返回混合工具集
  - [x] 本地：RetrieveAndSummarize
  - [x] MCP代理：ReadFile、SearchCode、RunCommand
- [x] 创建相应测试
- **Status:** completed

### Phase 7: 集成测试与验证
- [ ] 完整端到端测试：Agent → MCP代理工具 → MCP client → MCP server
- [ ] 降级机制测试（模拟 MCP 失败）
- [ ] 性能基准测试
- [ ] Claude Desktop 端到端联调（独立使用 MCP server）
- **Status:** pending

### Phase 8: 文档补完
- [ ] 更新 README / 部署与使用说明
- [ ] 编写开发者维护文档
- [ ] 更新架构图
- **Status:** pending

## Key Questions
1. 现有agent/tools/中哪些工具需要迁移，哪些需要保留？
   - 保留：RetrieveAndSummarize（依赖 ServiceManager）
   - 迁移：ReadFile、SearchCode、RunCommand（MCP server）
2. 如何实现security.py等模块的共享而不重复代码？
   - 符号链接方案已实现
3. 配置文件如何在FastAPI和MCP服务间共享？
   - 复用 utils/config.py
4. Agent 侧如何通过 MCP client 调用 MCP server？
   - 新增 MCP 代理工具层，对 Agent 透明

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 采用混合式MCP架构 | 平衡性能与生态复用，核心检索保留在原应用，工具类迁移到MCP |
| Agent 作为 MCP 客户端 | 工具调用通过 MCP 协议，保持降级路径 |
| RetrieveAndSummarize 保留本地 | 强依赖 ServiceManager/Chroma/BM25，改动风险大 |
| 索引工具暂不暴露给 Agent | 先稳定核心链路，降低风险 |
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
