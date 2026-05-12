# 系统架构设计

## 整体架构图

```mermaid
graph TB
    subgraph "客户端层"
        mcp_client[MCP Client]
        custom[自定义客户端]
    end

    subgraph "MCP服务层"
        mcp_server[MCP Server]
        mcp_tools[MCP Tools]
        read_file[ReadFile]
        search_code[SearchCode]
        run_command[RunCommand]
        index_mgr[Index Manager]
    end

    subgraph "FastAPI应用层（保留）"
        fastapi[FastAPI]
        agent[CodeMind Agent]
        rag_tool[RetrieveAndSummarize]
        prompts[Prompt Manager]
    end

    subgraph "核心服务层（保留）"
        service_mgr[Service Manager]
        chroma[Chroma DB]
        bm25[BM25 Index]
        llm[Query Rewrite & Summarizer LLM]
    end

    subgraph "共享模块层"
        security[Security]
        config[Config]
        logger[Logger]
        tool_paths[Tool Paths]
    end

    mcp_client -->|MCP Protocol| mcp_server
    custom -->|HTTP| fastapi

    mcp_server -->|使用| mcp_tools
    mcp_tools -->|调用| read_file
    mcp_tools -->|调用| search_code
    mcp_tools -->|调用| run_command
    mcp_tools -->|调用| index_mgr

    fastapi -->|使用| agent
    agent -->|使用| rag_tool
    agent -->|使用| prompts
    rag_tool -->|调用| service_mgr

    service_mgr -->|管理| chroma
    service_mgr -->|管理| bm25
    service_mgr -->|调用| llm

    mcp_tools -->|使用| security
    mcp_tools -->|使用| config
    mcp_tools -->|使用| logger
    mcp_tools -->|使用| tool_paths

    agent -->|使用| security
    agent -->|使用| config
    agent -->|使用| logger
    agent -->|使用| tool_paths
```

## 新目录结构

```
code-mind-agent/
├── app.py                          # 原FastAPI应用（保留）
├── agent/
│   ├── agent.py                    # Agent核心（保留）
│   ├── security.py                 # 安全模块（共享）
│   ├── tool_paths.py               # 路径工具（共享）
│   └── tools/
│       ├── __init__.py
│       ├── retrieve_and_summarize.py  # ⭐ 保留在原应用
│       ├── output_truncation.py
│       ├── read_file.py            # 保留副本作为降级
│       ├── search_code.py          # 保留副本作为降级
│       └── run_command.py          # 保留副本作为降级
├── mcp/                            # ⭐ 新增：MCP服务
│   ├── __init__.py
│   ├── server.py                   # MCP服务器入口
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                 # MCP工具基类
│   │   ├── read_file.py            # 从agent/tools/迁移
│   │   ├── search_code.py          # 从agent/tools/迁移
│   │   ├── run_command.py          # 从agent/tools/迁移
│   │   └── index_manager/
│   │       ├── __init__.py
│   │       ├── index_repo.py
│   │       ├── add_by_file_path.py
│   │       └── delete_by_file_path.py
│   ├── security.py -> ../agent/security.py  # 符号链接共享
│   ├── tool_paths.py -> ../agent/tool_paths.py
│   └── config.py                   # MCP配置（复用utils/config）
├── scripts/                        # 保留（可被MCP包装调用）
│   ├── index_repo.py
│   ├── add_by_file_path.py
│   └── delete_by_file_path.py
├── services/
│   └── service_manager.py          # ⭐ 保留在原应用
├── utils/
│   ├── config.py                   # 共享配置
│   ├── logger.py                   # 共享日志
│   ├── bm25_index.py               # ⭐ 保留在原应用
│   ├── summarizer.py               # ⭐ 保留在原应用
│   └── fusion.py                   # ⭐ 保留在原应用
├── prompts/                        # 保留在原应用
├── tests/
│   ├── test_fastapi.py             # 原应用测试
│   └── test_mcp/                  # ⭐ 新增：MCP服务测试
│       ├── __init__.py
│       ├── test_server.py
│       └── tools/
│           ├── test_read_file.py
│           ├── test_search_code.py
│           └── test_run_command.py
├── config.yml                      # 共享配置
├── requirements.txt                # 添加MCP依赖
└── mcp_client_config.json          # ⭐ 新增：MCP客户端配置示例
```

## 依赖关系

```mermaid
graph LR
    mcp_server[MCP Server]
    mcp_read[ReadFile]
    mcp_search[SearchCode]
    mcp_run[RunCommand]
    mcp_index[Index Manager]
    security[Security]
    config[Config]
    logger[Logger]
    tool_paths[Tool Paths]

    mcp_server -->|uses| mcp_read
    mcp_server -->|uses| mcp_search
    mcp_server -->|uses| mcp_run
    mcp_server -->|uses| mcp_index

    mcp_read -->|imports| security
    mcp_read -->|imports| config
    mcp_read -->|imports| logger
    mcp_read -->|imports| tool_paths

    mcp_search -->|imports| security
    mcp_search -->|imports| config
    mcp_search -->|imports| logger
    mcp_search -->|imports| tool_paths

    mcp_run -->|imports| security
    mcp_run -->|imports| config
    mcp_run -->|imports| logger
    mcp_run -->|imports| tool_paths

    mcp_index -->|imports| config
    mcp_index -->|imports| logger
    mcp_index -->|imports| tool_paths
```

## 共享模块方案

为了避免代码重复，采用以下共享策略：

1. **符号链接** - `mcp/security.py` -> `agent/security.py`，`mcp/tool_paths.py` -> `agent/tool_paths.py`
2. **直接复用** - `utils/config.py`、`utils/logger.py` 两个服务都通过相同路径导入
3. **复制副本** - 原应用的 `agent/tools/read_file.py`、`search_code.py`、`run_command.py` 保留作为降级路径

### 符号链接的注意事项

- Windows环境下创建符号链接需要管理员权限
- Git会保留符号链接信息，跨平台协作时需注意
- 提供复制脚本作为备选方案
