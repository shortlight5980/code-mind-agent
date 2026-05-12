# 实施检查清单

## 阶段一检查清单 ✅

- [x] 创建了 `mcp/` 目录
- [x] 创建了 `mcp/tools/` 子目录
- [x] 创建了 `mcp/tools/base.py` 基类
- [x] 创建了 `mcp/server.py` 入口文件
- [x] 添加了符号链接 `mcp/security.py` -> `../agent/security.py`
- [x] 添加了符号链接 `mcp/tool_paths.py` -> `../agent/tool_paths.py`
- [x] 更新了 `requirements.txt` 添加 `mcp>=1.0.0`
- [x] 创建了 `mcp/tools/__init__.py`
- [x] 创建了 `tests/test_mcp/` 目录结构
- [x] 测试 MCP 服务器能正常启动
- [x] 测试 `list_tools` 正常工作
- [x] 配置加载正常
- [x] 日志输出正常

## 阶段二检查清单 ✅

- [x] 创建了 `mcp/tools/read_file.py`
- [x] 实现了 ReadFileTool 类
- [x] 在 server.py 中注册了 ReadFileTool
- [x] 编写了 `tests/test_mcp/tools/test_read_file.py`
- [x] 创建了 `mcp_client_config.json`
- [x] 在 MCP 客户端中测试 ReadFile 成功
- [x] 验证了安全限制（敏感文件、目录白名单）
- [x] 验证了按行号读取
- [x] 验证了文件名搜索功能
- [x] 验证了原应用的 ReadFile 依然正常工作

## 阶段三检查清单 ✅

- [x] 创建了 `mcp/tools/search_code.py`
- [x] 实现了 SearchCodeTool 类
- [x] 在 server.py 中注册了 SearchCodeTool
- [x] 编写了 `tests/test_mcp/tools/test_search_code.py`
- [x] 在 MCP 客户端中测试 SearchCode 成功
- [x] 验证了关键词搜索
- [x] 验证了正则表达式搜索
- [x] 验证了目录限制
- [x] 验证了原应用的 SearchCode 依然正常工作

## 阶段四检查清单 ✅

- [x] 创建了 `mcp/tools/run_command.py`
- [x] 实现了 RunCommandTool 类
- [x] 在 server.py 中注册了 RunCommandTool
- [x] 编写了 `tests/test_mcp/tools/test_run_command.py`
- [x] 在 MCP 客户端中测试 RunCommand 成功
- [x] 验证了命令白名单
- [x] 验证了禁止的参数（如 ls -R）
- [x] 验证了超时机制
- [x] 验证了 Windows 命令适配（如适用）
- [x] 验证了原应用的 RunCommand 依然正常工作

## 阶段五检查清单 ✅

- [x] 创建了 `mcp/tools/index_manager/` 目录
- [x] 创建了 `mcp/tools/index_manager/__init__.py`
- [x] 实现了 IndexRepoTool
- [x] 实现了 AddByFilePathTool
- [x] 实现了 DeleteByFilePathTool
- [x] 在 server.py 中注册了索引管理工具
- [x] 编写了相应测试
- [x] 在 MCP 客户端中测试索引功能成功
- [x] 验证了索引写入正确位置

## 阶段六检查清单：MCP客户端层实现（新增）

- [ ] 创建了 `agent/mcp_client.py`
- [ ] 实现了 `MCPClient` 类
- [ ] 实现了子进程启动和管理（启动 `python mcp/server.py`）
- [ ] 实现了 stdio 传输层
- [ ] 实现了 `list_tools()` 方法
- [ ] 实现了 `call_tool(name, arguments)` 方法
- [ ] 实现了超时控制
- [ ] 实现了健康检查
- [ ] 实现了错误处理
- [ ] 更新了 `services/service_manager.py`
  - [ ] 在 `initialize()` 中启动 MCP client
  - [ ] 在 `cleanup()` 中关闭 MCP client
  - [ ] 提供 `get_mcp_client()` 访问方法
- [ ] 更新了 `utils/config.py`
  - [ ] 增加 `mcp` 配置段
  - [ ] 支持 `enabled`、`transport`、`server_command`、`call_timeout`、`fallback_to_local`
- [ ] 创建了 `tests/test_mcp/test_client.py`
  - [ ] 测试 MCP client 启动
  - [ ] 测试 list_tools
  - [ ] 测试 call_tool
  - [ ] 测试超时
  - [ ] 测试降级机制
- [ ] 更新了 `config.yml` 增加 MCP 配置示例

## 阶段七检查清单：Agent侧MCP代理工具（新增）

- [ ] 创建了 `agent/tools/mcp_read_file.py`
  - [ ] 实现了 `MCPReadFile` tool（保持与 ReadFile 相同的签名）
  - [ ] 内部调用 MCP client 的 `call_tool("codemind_read_file", ...)`
  - [ ] 实现了降级逻辑（根据配置）
- [ ] 创建了 `agent/tools/mcp_search_code.py`
  - [ ] 实现了 `MCPSearchCode` tool
  - [ ] 内部调用 MCP client 的 `call_tool("codemind_search_code", ...)`
  - [ ] 实现了降级逻辑
- [ ] 创建了 `agent/tools/mcp_run_command.py`
  - [ ] 实现了 `MCPRunCommand` tool
  - [ ] 内部调用 MCP client 的 `call_tool("codemind_run_command", ...)`
  - [ ] 实现了降级逻辑
- [ ] 更新了 `agent/tools/__init__.py`
  - [ ] 根据配置决定导出 MCP 代理工具还是原工具
  - [ ] RetrieveAndSummarize 始终导出本地版本
- [ ] 更新了 `agent/agent.py`
  - [ ] 修改 `get_tools()` 返回混合工具集
  - [ ] 本地：RetrieveAndSummarize
  - [ ] MCP 代理：ReadFile、SearchCode、RunCommand
- [ ] 创建了相应测试
  - [ ] 测试 MCPReadFile 能正常工作
  - [ ] 测试 MCPSearchCode 能正常工作
  - [ ] 测试 MCPRunCommand 能正常工作
  - [ ] 测试降级机制（模拟 MCP 失败）
  - [ ] 端到端测试：Agent → MCP代理工具 → MCP client → MCP server
- [ ] 验证了工具接口保持不变，Agent prompt 无需修改
- [ ] 验证了错误语义与原工具保持一致

## 阶段八检查清单：集成测试 & 文档

- [ ] 完整端到端测试（所有工具一起测试）
  - [ ] Agent → RetrieveAndSummarize（本地）
  - [ ] Agent → MCPReadFile → MCP server
  - [ ] Agent → MCPSearchCode → MCP server
  - [ ] Agent → MCPRunCommand → MCP server
  - [ ] 降级场景测试
- [ ] 性能基准测试（对比迁移前后）
  - [ ] 工具调用延迟对比
  - [ ] 内存占用对比
- [ ] Claude Desktop 端到端联调
- [ ] MCP 服务器真实 stdio 启动验证
- [ ] 核心检索性能无明显下降
- [ ] 编写了部署文档
- [ ] 编写了用户使用指南
- [ ] 编写了开发者维护文档
- [ ] 更新了 README.md
- [ ] 更新了架构图
- [ ] 最终代码审查通过
- [ ] 所有原应用测试通过
- [ ] 所有 MCP 服务测试通过
- [ ] 所有 MCP 客户端测试通过

## 发布前检查清单

- [ ] 已验证降级机制完整可用
- [ ] 已通过配置开关验证能在 MCP 和本地工具之间切换
- [ ] docker-compose.yml 已更新（如适用）
- [ ] 所有文档已同步更新
- [ ] 已通知相关团队
- [ ] 回滚方案已准备就绪
- [ ] 监控告警已配置（如适用）
