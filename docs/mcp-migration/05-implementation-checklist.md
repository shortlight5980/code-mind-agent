# 实施检查清单

## 阶段一检查清单

- [ ] 创建了 `mcp/` 目录
- [ ] 创建了 `mcp/tools/` 子目录
- [ ] 创建了 `mcp/tools/base.py` 基类
- [ ] 创建了 `mcp/server.py` 入口文件
- [ ] 添加了符号链接 `mcp/security.py` -> `../agent/security.py`
- [ ] 添加了符号链接 `mcp/tool_paths.py` -> `../agent/tool_paths.py`
- [ ] 更新了 `requirements.txt` 添加 `mcp>=1.0.0`
- [ ] 创建了 `mcp/tools/__init__.py`
- [ ] 创建了 `tests/test_mcp/` 目录结构
- [ ] 测试 MCP 服务器能正常启动
- [ ] 测试 `list_tools` 正常工作
- [ ] 配置加载正常
- [ ] 日志输出正常

## 阶段二检查清单

- [ ] 创建了 `mcp/tools/read_file.py`
- [ ] 实现了 ReadFileTool 类
- [ ] 在 server.py 中注册了 ReadFileTool
- [ ] 编写了 `tests/test_mcp/tools/test_read_file.py`
- [ ] 创建了 `claude_desktop_config.json`
- [ ] 在 Claude Desktop 中测试 ReadFile 成功
- [ ] 验证了安全限制（敏感文件、目录白名单）
- [ ] 验证了按行号读取
- [ ] 验证了文件名搜索功能
- [ ] 验证了原应用的 ReadFile 依然正常工作

## 阶段三检查清单

- [ ] 创建了 `mcp/tools/search_code.py`
- [ ] 实现了 SearchCodeTool 类
- [ ] 在 server.py 中注册了 SearchCodeTool
- [ ] 编写了 `tests/test_mcp/tools/test_search_code.py`
- [ ] 在 Claude Desktop 中测试 SearchCode 成功
- [ ] 验证了关键词搜索
- [ ] 验证了正则表达式搜索
- [ ] 验证了目录限制
- [ ] 验证了原应用的 SearchCode 依然正常工作

## 阶段四检查清单

- [ ] 创建了 `mcp/tools/run_command.py`
- [ ] 实现了 RunCommandTool 类
- [ ] 在 server.py 中注册了 RunCommandTool
- [ ] 编写了 `tests/test_mcp/tools/test_run_command.py`
- [ ] 在 Claude Desktop 中测试 RunCommand 成功
- [ ] 验证了命令白名单
- [ ] 验证了禁止的参数（如 ls -R）
- [ ] 验证了超时机制
- [ ] 验证了 Windows 命令适配（如适用）
- [ ] 验证了原应用的 RunCommand 依然正常工作

## 阶段五检查清单

- [ ] 创建了 `mcp/tools/index_manager/` 目录
- [ ] 创建了 `mcp/tools/index_manager/__init__.py`
- [ ] 实现了 IndexRepoTool
- [ ] 实现了 AddByFilePathTool
- [ ] 实现了 DeleteByFilePathTool
- [ ] 在 server.py 中注册了索引管理工具
- [ ] 编写了相应测试
- [ ] 在 Claude Desktop 中测试索引功能成功
- [ ] 验证了索引写入正确位置

## 阶段六检查清单

- [ ] 完成了完整端到端测试
- [ ] 完成了性能基准测试
- [ ] 核心检索性能无明显下降
- [ ] 编写了部署文档
- [ ] 编写了用户使用指南
- [ ] 编写了开发者维护文档
- [ ] 更新了 README.md
- [ ] 最终代码审查通过
- [ ] 所有原应用测试通过
- [ ] 所有 MCP 服务测试通过

## 发布前检查清单

- [ ] docker-compose.yml 已更新（如适用）
- [ ] 所有文档已同步更新
- [ ] 已通知相关团队
- [ ] 回滚方案已准备就绪
- [ ] 监控告警已配置（如适用）
