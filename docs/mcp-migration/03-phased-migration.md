# 分阶段迁移计划

## 概述

整个迁移分为6个阶段，每个阶段可独立验证、可回滚。

```mermaid
graph LR
    P1[阶段一：MCP服务器框架搭建]
    P2[阶段二：ReadFile迁移]
    P3[阶段三：SearchCode迁移]
    P4[阶段四：RunCommand迁移]
    P5[阶段五：索引脚本包装]
    P6[阶段六：集成测试 & 文档]

    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> P6
```

## 阶段一：MCP服务器框架搭建

### 目标
- 搭建MCP服务器基础框架
- 集成MCP Python SDK
- 实现工具注册机制
- 复用配置和日志模块

### 任务清单

- [ ] 创建 `mcp/` 目录结构
- [ ] 创建 `mcp/tools/` 子目录
- [ ] 创建 `mcp/tools/base.py` 基类
- [ ] 创建 `mcp/server.py` 入口文件
- [ ] 添加符号链接 `mcp/security.py` -> `../agent/security.py`
- [ ] 添加符号链接 `mcp/tool_paths.py` -> `../agent/tool_paths.py`
- [ ] 更新 `requirements.txt` 添加 `mcp>=1.0.0`
- [ ] 创建 `mcp/tools/__init__.py`
- [ ] 创建 `tests/test_mcp/` 目录结构
- [ ] 编写简单的测试工具验证框架
- [ ] 测试MCP服务器启动

### 验收标准

- MCP服务器能正常启动
- 能列出可用工具列表（即使是空的）
- 配置加载正常
- 日志输出正常
- 能响应 `initialize` 消息

### 回滚方案

- 删除 `mcp/` 目录
- 恢复 `requirements.txt`

---

## 阶段二：ReadFile迁移

### 目标
- 将 ReadFile 工具迁移到 MCP 服务
- 保持功能完全一致
- 验证安全性

### 任务清单

- [ ] 创建 `mcp/tools/read_file.py`
- [ ] 实现 ReadFileTool 类（复用原逻辑）
- [ ] 在 server.py 中注册 ReadFileTool
- [ ] 编写 `tests/test_mcp/tools/test_read_file.py`
- [ ] 创建 `claude_desktop_config.json`
- [ ] 在 Claude Desktop 中测试 ReadFile 功能
- [ ] 验证安全机制正常工作
- [ ] 验证路径解析正常工作

### 验收标准

- ReadFile 工具能正常列出
- 能成功读取仓库文件
- 能按行号范围读取
- 安全限制生效（不能访问敏感文件、不能访问白名单外目录）
- 原应用的 ReadFile 工具依然正常工作（降级路径可用）

### 回滚方案

- 从 server.py 中取消注册 ReadFileTool
- 原应用工具保持不变

---

## 阶段三：SearchCode迁移

### 目标
- 将 SearchCode 工具迁移到 MCP 服务
- 保持功能完全一致

### 任务清单

- [ ] 创建 `mcp/tools/search_code.py`
- [ ] 实现 SearchCodeTool 类（复用原逻辑）
- [ ] 在 server.py 中注册 SearchCodeTool
- [ ] 编写 `tests/test_mcp/tools/test_search_code.py`
- [ ] 在 Claude Desktop 中测试 SearchCode 功能
- [ ] 验证关键词搜索
- [ ] 验证正则表达式搜索

### 验收标准

- SearchCode 工具能正常列出
- 关键词搜索功能正常
- 正则搜索功能正常
- 目录限制生效
- 原应用的 SearchCode 工具依然正常工作

### 回滚方案

- 从 server.py 中取消注册 SearchCodeTool

---

## 阶段四：RunCommand迁移

### 目标
- 将 RunCommand 工具迁移到 MCP 服务
- 保持安全沙箱机制

### 任务清单

- [ ] 创建 `mcp/tools/run_command.py`
- [ ] 实现 RunCommandTool 类（复用原逻辑）
- [ ] 在 server.py 中注册 RunCommandTool
- [ ] 编写 `tests/test_mcp/tools/test_run_command.py`
- [ ] 在 Claude Desktop 中测试 RunCommand 功能
- [ ] 验证命令白名单机制
- [ ] 验证禁止的参数（如 ls -R）
- [ ] 验证超时机制
- [ ] 验证 Windows 命令适配

### 验收标准

- RunCommand 工具能正常列出
- 白名单命令能正常执行
- 非白名单命令被拒绝
- 危险参数被拒绝
- 超时机制生效
- 原应用的 RunCommand 工具依然正常工作

### 回滚方案

- 从 server.py 中取消注册 RunCommandTool

---

## 阶段五：索引脚本包装

### 目标
- 将索引脚本包装为 MCP 工具

### 任务清单

- [ ] 创建 `mcp/tools/index_manager/` 目录
- [ ] 创建 `mcp/tools/index_manager/__init__.py`
- [ ] 创建 `mcp/tools/index_manager/index_repo.py` 实现 IndexRepoTool
- [ ] 创建 `mcp/tools/index_manager/add_by_file_path.py` 实现 AddByFilePathTool
- [ ] 创建 `mcp/tools/index_manager/delete_by_file_path.py` 实现 DeleteByFilePathTool
- [ ] 在 server.py 中注册索引管理工具
- [ ] 编写相应测试
- [ ] 在 Claude Desktop 中测试索引功能

### 验收标准

- 索引管理工具能正常列出
- 能成功触发仓库索引
- 能添加单个文件到索引
- 能从索引删除单个文件
- 索引写入正确的持久化位置

### 回滚方案

- 从 server.py 中取消注册索引管理工具

---

## 阶段六：集成测试 & 文档

### 目标
- 完整端到端测试
- 完善文档
- 性能基准测试

### 任务清单

- [ ] 完整端到端测试（所有工具一起测试）
- [ ] 性能基准测试（对比迁移前后）
- [ ] 编写部署文档
- [ ] 编写用户使用指南
- [ ] 编写开发者维护文档
- [ ] 最终代码审查
- [ ] 更新 README.md

### 验收标准

- 所有工具在 Claude Desktop 中正常工作
- 原 FastAPI 应用依然完全正常工作
- 性能无明显下降（核心检索保持原样）
- 文档完整准确

---

## 降级方案

在迁移过程中，原应用的所有工具保留不变，作为降级路径：

- `agent/tools/read_file.py` - 保留
- `agent/tools/search_code.py` - 保留
- `agent/tools/run_command.py` - 保留

如果 MCP 服务出现问题，可以随时停止使用 MCP，完全回退到原应用。

## 检查点

每个阶段结束后，运行以下检查：

1. [ ] 原应用所有单元测试通过
2. [ ] MCP 服务能正常启动
3. [ ] 已迁移工具在 Claude Desktop 中正常工作
4. [ ] 已迁移工具在原应用中依然正常工作
5. [ ] 文档同步更新
