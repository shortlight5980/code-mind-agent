# Claude Desktop 联调清单

本文档用于手工验证 CodeMind MCP server 能被 Claude Desktop 正常发现和调用。

## 前置条件

- 已安装 Claude Desktop
- 本机可用 `conda run --no-capture-output -n AIP312 python`
- 仓库依赖已安装完成
- `config.yml` 中的 `repo.path` 指向一个你有权限访问且内容可验证的仓库

## 1. 准备配置文件

仓库根目录已有示例文件：

- [mcp_client_config.json](/home/ljw/桌面/CodeMind/code-mind-agent/mcp_client_config.json)

当前示例内容会启动：

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

如果你的仓库路径不同，只需要把最后一个参数改成你本机上的绝对路径。

## 2. 导入到 Claude Desktop

把上述 `mcpServers` 配置合并到 Claude Desktop 的 MCP 配置文件中。

如果你还需要让 MCP server 读取一个非默认配置文件，可以把 `env` 一并加上：

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
      ],
      "env": {
        "CODEMIND_CONFIG_PATH": "/abs/path/to/config.yml"
      }
    }
  }
}
```

## 3. 重启 Claude Desktop

- 完全退出 Claude Desktop
- 重新打开 Claude Desktop
- 确认 MCP server 没有启动报错

## 4. 预期看到的工具

Claude Desktop 应该能发现以下 6 个工具：

- `codemind_read_file`
- `codemind_search_code`
- `codemind_run_command`
- `codemind_index_repo`
- `codemind_add_by_file_path`
- `codemind_delete_by_file_path`

## 5. 最小验证步骤

建议按下面顺序验证：

1. 读文件
   使用 `codemind_read_file` 读取一个你确认存在的文件，例如 `README.md`
2. 搜代码
   使用 `codemind_search_code` 搜一个该仓库里确定存在的关键词
3. 跑只读命令
   使用 `codemind_run_command` 执行 `git status`

## 6. 验收标准

- Claude Desktop 能发现全部 6 个工具
- `codemind_read_file` 能返回正确文件内容
- `codemind_search_code` 能返回匹配结果
- `codemind_run_command` 能返回只读命令结果
- 不出现 JSON-RPC 解析错误
- 不出现工具 schema 校验错误

## 7. 常见问题

### 启动后看不到工具

先在终端单独运行：

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 conda run --no-capture-output -n AIP312 python mcp/server.py
```

如果这里启动失败，先修复本地环境问题。

### 读到的不是目标仓库内容

检查：

- `config.yml` 的 `repo.path`
- 是否通过 `CODEMIND_CONFIG_PATH` 指向了正确配置文件

### 命令执行失败

检查 `config.yml` 中的 `agent.allowed_commands` 是否包含目标命令。
