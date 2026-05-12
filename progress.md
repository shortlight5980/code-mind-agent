# Progress

## 2026-05-12
- 建立本次 MCP 抽离方案设计的规划文件
- 已读取 `agent/agent.py`、`services/service_manager.py`、`agent/tools/*`、`agent/mcp_client.py`、`mcp/server.py`、`mcp/tools/*` 与关键测试
- 已确认当前系统仍存在本地注册与本地 fallback，不满足 MCP-only 目标
- 已完成方案收敛：明确推荐采用“共享核心逻辑下沉 + Agent 仅保留 MCP 代理工具 + MCP 强依赖”的重构路线
- 已开始实施 Phase 0：将本地包 `mcp/` 重命名为 `codemind_mcp/`，并同步修改运行配置、README、MCP client 本地导入路径与测试导入
- 已完成 Phase 1 主链切换：新增 `codemind_mcp/tool_impl.py` 承载三项 MCP-only 实现，移除 Agent 侧三项代理工具的本地 fallback，并固定 Agent toolset 为 MCP-only
- 已完成 Phase 2 清理：删除 `agent/tools/read_file.py`、`search_code.py`、`run_command.py`，并把旧本地测试与 benchmark 迁移到 `codemind_mcp.tool_impl`
- 已完成 Phase 3 收口：移除 `mcp.enabled` 与 `mcp.fallback_to_local` 的运行语义，并将 `ServiceManager` 调整为 MCP client 初始化失败即整体初始化失败
