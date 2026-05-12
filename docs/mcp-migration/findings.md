# Findings & Decisions
<!-- 
  WHAT: 项目现状调研发现和技术决策记录。
-->

## Requirements
<!-- 从用户请求和方案二提取 -->
- 采用混合式MCP架构，核心检索保留在原FastAPI应用
- 迁移ReadFile、SearchCode、RunCommand到MCP服务
- 包装索引脚本为MCP工具（index_repo、add_by_file_path、delete_by_file_path）
- 共享security.py、config.py、logger.py等模块
- 提供Claude Desktop配置文件
- 分6阶段渐进式迁移
- 仅完成文档撰写，先不编码

## Research Findings
<!-- 项目现状分析 -->
### 现有项目结构分析
- **agent/**: Agent核心实现
  - agent.py: CodeMindAgent (LangChain)
  - security.py: 路径安全验证（待共享）
  - tool_paths.py: 路径工具（待共享）
  - tools/: 工具实现
    - retrieve_and_summarize.py（⭐ 保留）
    - read_file.py（待迁移）
    - search_code.py（待迁移）
    - run_command.py（待迁移）
    - output_truncation.py
- **services/**: 服务管理
  - service_manager.py（⭐ 保留）
- **utils/**: 工具模块
  - config.py（共享）
  - logger.py（共享）
  - bm25_index.py（⭐ 保留）
  - summarizer.py（⭐ 保留）
  - fusion.py（⭐ 保留）
- **scripts/**: 索引脚本
  - index_repo.py（待包装）
  - add_by_file_path.py（待包装）
  - delete_by_file_path.py（待包装）
- **app.py**: FastAPI入口（保留）
- **config.yml**: 配置文件（共享）

### 待迁移工具清单
| 工具 | 原位置 | 目标位置 | 备注 |
|------|--------|----------|------|
| ReadFile | agent/tools/read_file.py | mcp/tools/read_file.py | 纯文件操作 |
| SearchCode | agent/tools/search_code.py | mcp/tools/search_code.py | 代码搜索 |
| RunCommand | agent/tools/run_command.py | mcp/tools/run_command.py | 命令执行 |
| index_repo | scripts/index_repo.py | mcp/tools/index_manager/ | 索引脚本 |
| add_by_file_path | scripts/add_by_file_path.py | mcp/tools/index_manager/ | 索引脚本 |
| delete_by_file_path | scripts/delete_by_file_path.py | mcp/tools/index_manager/ | 索引脚本 |

### 保留在原应用的核心模块
| 模块 | 位置 | 理由 |
|------|------|------|
| RetrieveAndSummarize | agent/tools/retrieve_and_summarize.py | 性能敏感，需频繁访问向量DB + BM25 |
| Chroma DB | services/service_manager.py | 检索性能关键，避免IPC开销 |
| BM25 Index | utils/bm25_index.py | 内存映射访问，性能敏感 |
| Query Rewriting & Summarizer LLM | utils/summarizer.py | 与检索流程深度耦合 |
| ServiceManager | services/service_manager.py | 核心服务生命周期管理 |
| FastAPI端点 | app.py | /chat、/chat/stream、/health |

## Technical Decisions
<!-- 技术决策与理由 -->
| Decision | Rationale |
|----------|-----------|
| 共享模块使用符号链接 | security.py、tool_paths.py等通过符号链接共享，避免代码重复 |
| 配置文件直接共享config.yml | 两个服务读取同一配置文件，确保一致性 |
| MCP工具命名使用codemind_前缀 | 避免与其他MCP服务工具冲突，如codemind_read_file |
| 原应用保留工具副本作为降级路径 | 迁移期间可切换回原实现，降低风险 |
| 使用Python MCP SDK | 官方推荐，生态完善 |
| Agent 侧 MCP client 采用“同步 facade + 后台事件循环线程” | 兼容同步 ServiceManager 初始化和 LangChain 同步工具入口 |
| MCP client 支持 `stdio` 与 `local` 两种 transport | `stdio` 用于真实运行，`local` 用于稳定单测与快速回归 |
| MCP 代理工具在失败时按配置回退到原本地工具 | 保持迁移风险可控，不阻断现有 Agent 使用链路 |
| MCP server 日志改走 stderr | 避免污染 stdio JSON-RPC 消息流 |
| MCP server `call_tool` 返回 `CallToolResult(TextContent[])` | 适配真实 MCP SDK 的结果模型，避免客户端解析失败 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| MCP server 日志写到 stdout，污染 JSON-RPC | logger 增加 `CODEMIND_LOG_STDERR` 开关，并在 `mcp/server.py` 启动前启用 |
| MCP server `call_tool` 返回裸字符串，不符合 MCP SDK `CallToolResult` 结构 | 在 server 侧包装为 `TextContent` 列表 |
| MCP client 关闭时跨 task 退出 anyio cancel scope | 改为单后台任务持有 stdio session，并通过请求队列串行执行操作 |

## Resources
- 方案二原始设计：用户提供的详细方案
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Claude Desktop MCP文档: https://modelcontextprotocol.io/

## Visual/Browser Findings
（暂无）

---
*Update this file after every 2 view/browser/search operations*
