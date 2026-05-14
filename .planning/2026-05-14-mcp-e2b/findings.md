# Findings & Decisions

## Requirements
- 将MCP工具放到沙箱中执行
- 使用E2B作为沙箱解决方案
- 保持现有功能不变
- 支持本地执行和沙箱执行两种模式切换

## Research Findings

### 当前MCP工具架构
1. **MCP服务器**: `codemind_mcp/server.py` - 工具注册和调用入口
2. **工具列表**:
   - `ReadFileTool` - 读取文件
   - `SearchCodeTool` - 搜索代码
   - `RunCommandTool` - 执行命令
   - `IndexRepoTool`, `AddByFilePathTool`, `DeleteByFilePathTool` - 索引管理工具
3. **工具基类**: `codemind_mcp/tools/base.py` - 定义了`BaseMCPTool`接口
4. **MCP客户端**: `agent/mcp_host.py` - `MCPClient`负责与MCP服务器通信，支持stdio和local两种传输模式
5. **安全机制**: `codemind_mcp/security.py` - 路径白名单、命令白名单等

### 当前工具执行方式
- 所有工具都在本地直接执行
- `RunCommandTool`使用`subprocess.run()`执行命令
- `ReadFileTool`直接使用`open()`读取文件
- 通过`security.py`进行安全校验

### E2B沙箱特点（基于已有知识）
- E2B提供云端沙箱环境用于安全执行代码
- Python SDK可用于创建和管理沙箱
- 支持文件上传/下载、命令执行
- 提供隔离环境防止恶意操作

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 采用适配器模式集成E2B | 最小化对现有代码的改动，保持API兼容性 |
| 创建`E2BSandbox`类封装E2B SDK | 统一管理沙箱生命周期和操作 |
| 创建`SandboxedToolExecutor`类 | 在沙箱中执行工具逻辑，保持工具接口不变 |
| 支持配置切换本地/沙箱模式 | 通过`config.yml`配置使用哪种模式 |
| 保持现有安全检查作为第一道防线 | 安全检查仍在本地执行，沙箱作为第二道防线 |
| 索引管理工具继续在本地执行 | 索引操作需要访问本地向量数据库，不适合沙箱化 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
|       |            |

## Resources
-

## Visual/Browser Findings

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*
