# CodeMind MCP

`codemind_mcp/` 目录提供 CodeMind 的 MCP 服务层，把原本适合独立暴露的工具封装成 MCP tools，同时保留原 `agent/tools/*` 作为降级路径。

## 目标

- 对外暴露文件读取、代码搜索、命令执行、索引管理能力
- 复用现有安全、路径、配置和日志逻辑
- 尽量包装现有实现，避免和原工具逻辑漂移

## 目录结构

```text
codemind_mcp/
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

- [server.py](/home/ljw/桌面/CodeMind/code-mind-agent/codemind_mcp/server.py): MCP 服务入口，负责工具注册与调用分发。
- [sdk.py](/home/ljw/桌面/CodeMind/code-mind-agent/codemind_mcp/sdk.py): 第三方 MCP SDK 兼容加载层。
- [tools/base.py](/home/ljw/桌面/CodeMind/code-mind-agent/codemind_mcp/tools/base.py): 统一的工具基类。
- [security.py](/home/ljw/桌面/CodeMind/code-mind-agent/codemind_mcp/security.py): 复用 `agent.security`。
- [tool_paths.py](/home/ljw/桌面/CodeMind/code-mind-agent/codemind_mcp/tool_paths.py): 复用 `agent.tool_paths`。

## 可用工具

当前服务注册了 6 个工具：

- `codemind_read_file`: 读取仓库文件，支持按行号范围读取
- `codemind_search_code`: 在仓库内做关键词或正则搜索
- `codemind_run_command`: 执行白名单内的只读命令
- `codemind_index_repo`: 重建整个仓库索引
- `codemind_add_by_file_path`: 增量添加指定文件或目录到索引
- `codemind_delete_by_file_path`: 从索引中删除指定文件或目录

## 实现方式

`codemind_mcp/tools/*` 当前分为两类：

- `ReadFileTool`、`SearchCodeTool`、`RunCommandTool` 调用 `codemind_mcp/tool_impl.py` 中的 MCP 自有实现
- 索引管理工具复用 `scripts/` 下的索引脚本入口函数

这样做的目的是让 `read_file`、`search_code`、`run_command` 彻底归 MCP 持有，同时保留可复用的底层逻辑。

Agent 侧不再保留这三个工具的本地实现，也不再支持本地 fallback。

## 关于包名

仓库内的服务包已重命名为 `codemind_mcp/`，第三方 SDK 继续使用其原始包名 `mcp`。

这样处理后：

- 本地服务代码统一从 `codemind_mcp.*` 导入
- 外部 SDK 统一从 `mcp.*` 导入
- 不再需要通过修改 `sys.path` 或清理 `sys.modules` 来规避同名冲突

## 启动方式

### 依赖

`requirements.txt` 已加入：

```txt
mcp>=1.0.0
```

### 本地启动

按仓库约定，推荐在 `AIP312` 环境中运行：

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 conda run --no-capture-output -n AIP312 python codemind_mcp/server.py
```

如果你已经激活了 `AIP312`，也可以直接运行：

```bash
python codemind_mcp/server.py
```

当前版本已经修复了这条命令的启动问题。

如果外部 MCP SDK 未正确安装，启动时会在进入 stdio 传输层前失败；这种情况先检查当前环境里的第三方 `mcp` 依赖是否可用。

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
        "/home/ljw/桌面/CodeMind/code-mind-agent/codemind_mcp/server.py"
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
- `python codemind_mcp/server.py` 直接启动支持
- MCP 单元测试
- 原工具降级路径保留

未完成：

- Claude Desktop 端到端手工联调
- 性能基准与更完整的部署说明
