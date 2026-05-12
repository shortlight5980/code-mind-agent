# 分阶段迁移计划

## 概述

整个迁移分为 8 个阶段，每个阶段可独立验证、可回滚。

```mermaid
graph LR
    P1[阶段一：MCP服务器框架搭建]
    P2[阶段二：ReadFile迁移到MCP服务]
    P3[阶段三：SearchCode迁移到MCP服务]
    P4[阶段四：RunCommand迁移到MCP服务]
    P5[阶段五：索引脚本包装]
    P6[阶段六：MCP客户端层实现]
    P7[阶段七：Agent侧MCP代理工具]
    P8[阶段八：集成测试 & 文档]

    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> P6
    P6 --> P7
    P7 --> P8
```

## 阶段一：MCP服务器框架搭建 ✅

### 目标
- 搭建MCP服务器基础框架
- 集成MCP Python SDK
- 实现工具注册机制
- 复用配置和日志模块

### 状态
- **已完成**

---

## 阶段二：ReadFile迁移到MCP服务 ✅

### 目标
- 将 ReadFile 工具迁移到 MCP 服务
- 保持功能完全一致
- 验证安全性

### 状态
- **已完成**

---

## 阶段三：SearchCode迁移到MCP服务 ✅

### 目标
- 将 SearchCode 工具迁移到 MCP 服务
- 保持功能完全一致

### 状态
- **已完成**

---

## 阶段四：RunCommand迁移到MCP服务 ✅

### 目标
- 将 RunCommand 工具迁移到 MCP 服务
- 保持安全沙箱机制

### 状态
- **已完成**

---

## 阶段五：索引脚本包装 ✅

### 目标
- 将索引脚本包装为 MCP 工具

### 状态
- **已完成**

---

## 阶段六：MCP客户端层实现（新增）

### 目标
- 实现 MCP 客户端模块，能够启动/连接 MCP server
- 实现工具列表获取和调用功能
- 实现超时控制和降级机制
- 集成到 ServiceManager 生命周期

### 任务清单

- [ ] 创建 `agent/mcp_client.py`
  - [ ] 实现 `MCPClient` 类
  - [ ] 实现子进程启动和管理（启动 `python mcp/server.py`）
  - [ ] 实现 stdio 传输层
  - [ ] 实现 `list_tools()` 方法
  - [ ] 实现 `call_tool(name, arguments)` 方法
  - [ ] 实现超时控制
  - [ ] 实现健康检查
- [ ] 更新 `services/service_manager.py`
  - [ ] 在 `initialize()` 中启动 MCP client
  - [ ] 在 `cleanup()` 中关闭 MCP client
  - [ ] 提供 `get_mcp_client()` 访问方法
- [ ] 更新 `utils/config.py`
  - [ ] 增加 `mcp` 配置段
  - [ ] 支持 `enabled`、`transport`、`server_command`、`call_timeout`、`fallback_to_local`
- [ ] 创建 `tests/test_mcp/test_client.py`
  - [ ] 测试 MCP client 启动
  - [ ] 测试 list_tools
  - [ ] 测试 call_tool
  - [ ] 测试超时
  - [ ] 测试降级机制

### 验收标准

- MCP client 能成功启动 MCP server 子进程
- 能正确获取工具列表
- 能成功调用 MCP 工具并获取结果
- 超时机制正常工作
- 降级机制正常工作（MCP 失败时能返回错误或降级）
- ServiceManager 能正确管理 MCP client 生命周期
- 配置加载正常

### 回滚方案

- 删除 `agent/mcp_client.py`
- 恢复 `services/service_manager.py`
- 恢复 `utils/config.py`

---

## 阶段七：Agent侧MCP代理工具（新增）

### 目标
- 创建 Agent 侧的 MCP 代理工具
- 保持工具接口与原工具一致
- 集成到 Agent 的工具列表
- 验证完整调用链

### 任务清单

- [ ] 创建 `agent/tools/mcp_read_file.py`
  - [ ] 实现 `MCPReadFile` tool（保持与 ReadFile 相同的签名）
  - [ ] 内部调用 MCP client 的 `call_tool("codemind_read_file", ...)`
  - [ ] 实现降级逻辑（根据配置）
- [ ] 创建 `agent/tools/mcp_search_code.py`
  - [ ] 实现 `MCPSearchCode` tool
  - [ ] 内部调用 MCP client 的 `call_tool("codemind_search_code", ...)`
  - [ ] 实现降级逻辑
- [ ] 创建 `agent/tools/mcp_run_command.py`
  - [ ] 实现 `MCPRunCommand` tool
  - [ ] 内部调用 MCP client 的 `call_tool("codemind_run_command", ...)`
  - [ ] 实现降级逻辑
- [ ] 更新 `agent/tools/__init__.py`
  - [ ] 根据配置决定导出 MCP 代理工具还是原工具
  - [ ] 或者混合导出（RetrieveAndSummarize 本地，其他走 MCP）
- [ ] 更新 `agent/agent.py`
  - [ ] 修改 `get_tools()` 返回混合工具集
  - [ ] 本地：RetrieveAndSummarize
  - [ ] MCP 代理：ReadFile、SearchCode、RunCommand
- [ ] 创建相应测试
  - [ ] 测试 MCPReadFile 能正常工作
  - [ ] 测试 MCPSearchCode 能正常工作
  - [ ] 测试 MCPRunCommand 能正常工作
  - [ ] 测试降级机制（模拟 MCP 失败）
  - [ ] 端到端测试：Agent → MCP代理工具 → MCP client → MCP server

### 验收标准

- Agent 的工具列表包含混合工具集（本地 + MCP 代理）
- Agent 能通过 MCP 代理工具成功调用 MCP server
- 工具接口保持不变，Agent prompt 无需修改
- 降级机制正常工作（MCP 失败时自动切回本地工具）
- 错误语义与原工具保持一致
- 完整端到端调用链正常工作

### 回滚方案

- 从 `agent/tools/__init__.py` 中移除 MCP 代理工具导出
- 恢复 `agent/agent.py` 的 `get_tools()` 返回原工具
- 删除 `agent/tools/mcp_*.py`

---

## 阶段八：集成测试 & 文档

### 目标
- 完整端到端测试
- 完善文档
- 性能基准测试

### 任务清单

- [ ] 完整端到端测试（所有工具一起测试）
  - [ ] Agent → RetrieveAndSummarize（本地）
  - [ ] Agent → MCPReadFile → MCP server
  - [ ] Agent → MCPSearchCode → MCP server
  - [ ] Agent → MCPRunCommand → MCP server
  - [ ] 降级场景测试
- [ ] 性能基准测试（对比迁移前后）
  - [ ] 工具调用延迟对比
  - [ ] 内存占用对比
- [ ] 编写部署文档
- [ ] 编写用户使用指南
- [ ] 编写开发者维护文档
- [ ] 最终代码审查
- [ ] 更新 README.md

### 验收标准

- Agent 能正常通过 MCP 代理工具调用 MCP server
- 所有功能正常工作
- 降级机制正常工作
- 原 FastAPI 应用依然完全正常工作（开关可切换回纯本地）
- 性能无明显下降
- 文档完整准确

---

## 降级方案

### 开关控制

通过配置 `mcp.enabled` 和 `mcp.fallback_to_local` 可以灵活控制：

```yaml
mcp:
  enabled: false              # 完全禁用 MCP，使用原本地工具
  fallback_to_local: true     # MCP 失败时自动降级
```

### 完整降级路径

在迁移过程中，原应用的所有工具保留不变，作为降级路径：

- `agent/tools/read_file.py` - 保留
- `agent/tools/search_code.py` - 保留
- `agent/tools/run_command.py` - 保留

如果 MCP 服务出现问题，可以通过以下方式随时回退：

1. 设置 `mcp.enabled: false`
2. Agent 自动切回使用本地工具
3. 无需重启（如果支持热加载）或重启 FastAPI 应用

## 检查点

每个阶段结束后，运行以下检查：

1. [ ] 原应用所有单元测试通过
2. [ ] MCP 服务能正常启动
3. [ ] 已迁移工具在 MCP 客户端中正常工作
4. [ ] 已迁移工具在原应用中依然正常工作
5. [ ] 文档同步更新

## 索引工具策略

### 第一阶段：不暴露给 Agent

- 索引管理工具在 MCP server 中可用
- 但不创建 Agent 侧的代理工具
- 通过后台管理接口或脚本直接调用 MCP server
- 降低风险，先稳定核心工具链路

### 第二阶段：（可选）暴露给 Agent

- 核心工具稳定后，可考虑是否暴露索引工具
- 需要严格的权限控制和使用限制
