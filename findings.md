# Findings

## Current Wiring
- Agent 当前固定注册 `MCPReadFile`、`MCPSearchCode`、`MCPRunCommand`、`RetrieveAndSummarize`
- `read_file`、`search_code`、`run_command` 已无本地 fallback，也无本地 Agent 工具实现文件
- `codemind_mcp/tools/read_file.py`、`search_code.py`、`run_command.py` 当前调用 `codemind_mcp/tool_impl.py`
- 因此这三个工具已经完成“仅允许通过 MCP 调用”的主链切换

## Package Rename
- 本地服务包已从 `mcp/` 重命名为 `codemind_mcp/`
- `agent/mcp_client.py` 已切换为直接导入外部 `mcp` SDK，并在本地 transport 场景显式导入 `codemind_mcp.server`
- 这一步消除了项目内包与第三方 `mcp` SDK 的顶级命名冲突

## MCP-only Cutover
- `agent/tools/__init__.py` 已切换为固定注册 `MCPReadFile`、`MCPSearchCode`、`MCPRunCommand`、`RetrieveAndSummarize`
- `agent/tools/mcp_read_file.py`、`mcp_search_code.py`、`mcp_run_command.py` 已移除本地 fallback
- `codemind_mcp/tools/read_file.py`、`search_code.py`、`run_command.py` 已不再调用 `agent.tools.*`，而是改为调用 `codemind_mcp/tool_impl.py`
- `agent/tools/read_file.py`、`search_code.py`、`run_command.py` 仍存在，但已脱离 Agent 主工具链与 MCP 主执行链

## Non-MCP Tools
- `RetrieveAndSummarize` 依赖 `ServiceManager` 提供 `vectordb`、`summarizer_llm`、`query_rewriting_llm`
- 该工具不依赖 `read_file/run_command/search_code`，可以独立保留在本地

## Tests
- 旧的 `mcp.enabled=false` 切本地、MCP 失败本地 fallback 语义已废弃
- 当前测试验证的是 MCP-only 行为、MCP tool 自持实现、以及 ServiceManager 对 MCP client 的强依赖
