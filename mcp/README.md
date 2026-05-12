# CodeMind MCP

`mcp/` 目录提供 CodeMind 的 MCP 服务层，把原本适合独立暴露的工具封装成 MCP tools，同时保留原 `agent/tools/*` 作为降级路径。

## 目标

- 对外暴露文件读取、代码搜索、命令执行、索引管理能力
- 复用现有安全、路径、配置和日志逻辑
- 尽量包装现有实现，避免和原工具逻辑漂移

## 目录结构

```text
mcp/
├── README.md
├── __init__.py
├── sdk.py
├── security.py
├── tool_paths.py
├── server.py
└── tools/
    ├── __init__.py
    ├── base.py
    ├── read_file.py
    ├── search_code.py
    ├── run_command.py
    └── index_manager/
        ├── __init__.py
        ├── index_repo.py
        ├── add_by_file_path.py
        └── delete_by_file_path.py
```

## 核心文件

- [server.py](/home/ljw/桌面/CodeMind/code-mind-agent/mcp/server.py): MCP 服务入口，负责工具注册与调用分发。
- [sdk.py](/home/ljw/桌面/CodeMind/code-mind-agent/mcp/sdk.py): 第三方 MCP SDK 兼容加载层。
- [tools/base.py](/home/ljw/桌面/CodeMind/code-mind-agent/mcp/tools/base.py): 统一的工具基类。
- [security.py](/home/ljw/桌面/CodeMind/code-mind-agent/mcp/security.py): 复用 `agent.security`。
- [tool_paths.py](/home/ljw/桌面/CodeMind/code-mind-agent/mcp/tool_paths.py): 复用 `agent.tool_paths`。

## 可用工具

当前服务注册了 6 个工具：

- `codemind_read_file`: 读取仓库文件，支持按行号范围读取
- `codemind_search_code`: 在仓库内做关键词或正则搜索
- `codemind_run_command`: 执行白名单内的只读命令
- `codemind_index_repo`: 重建整个仓库索引
- `codemind_add_by_file_path`: 增量添加指定文件或目录到索引
- `codemind_delete_by_file_path`: 从索引中删除指定文件或目录

## 实现方式

`mcp/tools/*` 目前主要是“包装层”：

- `ReadFileTool` 复用 `agent.tools.read_file.ReadFile`
- `SearchCodeTool` 复用 `agent.tools.search_code.SearchCode`
- `RunCommandTool` 复用 `agent.tools.run_command.RunCommand`
- 索引管理工具复用 `scripts/` 下的索引脚本入口函数

这样做的目的是保持 MCP 路径和原 Agent 路径的行为一致。

## 关于 `mcp` 包名冲突

仓库本地目录名也叫 `mcp`，而第三方 SDK 的包名同样是 `mcp`。这会带来导入冲突。

当前通过 [sdk.py](/home/ljw/桌面/CodeMind/code-mind-agent/mcp/sdk.py) 处理：

- 如果外部 MCP SDK 可正确加载，则使用真实 `Server`、`stdio_server`、`Tool`
- 如果当前环境无法拿到外部 SDK，则退回本地 shim，保证单元测试和本地分发逻辑仍可运行

这意味着当前实现已经支持本地测试和工具分发验证，但“真实 MCP stdio 联调”仍建议单独做一轮手工确认。

## 启动方式

### 依赖

`requirements.txt` 已加入：

```txt
mcp>=1.0.0
```

### 本地启动

```bash
python mcp/server.py
```

如果外部 MCP SDK 未正确安装或仍被包名冲突影响，启动时会在进入 stdio 传输层时报错；这种情况先检查 `mcp` 第三方依赖是否在当前环境可用。

## Claude Desktop 配置

仓库根目录提供了 [claude_desktop_config.json](/home/ljw/桌面/CodeMind/code-mind-agent/claude_desktop_config.json) 示例：

```json
{
  "mcpServers": {
    "codemind-agent": {
      "command": "conda",
      "args": [
        "run",
        "--no-capture-output",
        "-n",
        "AIP312",
        "python",
        "/home/ljw/桌面/CodeMind/code-mind-agent/mcp/server.py"
      ]
    }
  }
}
```

## 测试

当前已覆盖：

- 服务注册与分发
- `ReadFileTool`
- `SearchCodeTool`
- `RunCommandTool`
- 索引管理工具包装

运行命令：

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 conda run --no-capture-output -n AIP312 python -m unittest \
  tests.test_mcp.test_server \
  tests.test_mcp.tools.test_read_file \
  tests.test_mcp.tools.test_search_code \
  tests.test_mcp.tools.test_run_command \
  tests.test_mcp.tools.test_index_manager
```

## 当前状态

已完成：

- MCP 目录结构
- 服务入口与工具注册
- 6 个工具的包装
- MCP 单元测试
- 原工具降级路径保留

未完成：

- Claude Desktop 端到端手工联调
- 真实 stdio MCP 启动链路完整验证
- 性能基准与更完整的部署说明
