# MCP工具E2B沙箱重构计划

## 概述

本计划旨在将CodeMind Agent中的MCP工具迁移到E2B沙箱环境中执行，以提高系统安全性。通过使用E2B沙箱，我们可以在隔离环境中运行文件操作和命令执行，防止潜在的恶意操作影响宿主系统。

## 目标

1. 将`ReadFileTool`、`SearchCodeTool`、`RunCommandTool`迁移到E2B沙箱
2. 保持现有API接口不变，最小化对上层代码的影响
3. 支持本地模式和沙箱模式的配置切换
4. 索引管理工具继续在本地执行（需要访问本地向量数据库）
5. 保持现有安全检查作为第一道防线

## 当前架构分析

### MCP工具清单

| 工具 | 类名 | 文件 | 是否沙箱化 |
|------|------|------|-----------|
| 读取文件 | ReadFileTool | codemind_mcp/tools/read_file.py | 是 |
| 搜索代码 | SearchCodeTool | codemind_mcp/tools/search_code.py | 是 |
| 执行命令 | RunCommandTool | codemind_mcp/tools/run_command.py | 是 |
| 索引仓库 | IndexRepoTool | codemind_mcp/tools/index_manager/__init__.py | 否 |
| 添加文件到索引 | AddByFilePathTool | codemind_mcp/tools/index_manager/add_by_file_path.py | 否 |
| 从索引删除 | DeleteByFilePathTool | codemind_mcp/tools/index_manager/delete_by_file_path.py | 否 |

### 关键文件

- `codemind_mcp/server.py` - MCP服务器入口，工具注册和调用分发
- `codemind_mcp/tools/base.py` - 工具基类`BaseMCPTool`
- `codemind_mcp/security.py` - 安全检查模块
- `agent/mcp_host.py` - MCP客户端
- `config.yml` - 配置文件

## 新架构设计

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Server (server.py)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Tool Router (根据配置选择执行模式)          │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│         ┌─────────────────┴─────────────────┐                │
│         │                                   │                │
│         ▼                                   ▼                │
│  ┌───────────────┐                   ┌───────────────┐     │
│  │  Local Mode   │                   │ Sandbox Mode  │     │
│  │  (现有实现)   │                   │   (E2B)       │     │
│  └───────────────┘                   └───────────────┘     │
│         │                                   │                │
│         └─────────────────┬─────────────────┘                │
│                           │                                  │
│                           ▼                                  │
│              ┌───────────────────────┐                      │
│              │   BaseMCPTool         │                      │
│              │   (不变的接口)         │                      │
│              └───────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### 新增模块

#### 1. `codemind_mcp/sandbox/__init__.py`
沙箱模块初始化文件

#### 2. `codemind_mcp/sandbox/e2b_sandbox.py`git@github.com:shortlight5980/docs.git
E2B沙箱封装类

```python
class E2BSandbox:
    """E2B沙箱封装，管理沙箱生命周期和操作"""
    
    def __init__(self, api_key: str | None = None, template: str | None = None):
        """初始化沙箱管理器"""
        
    async def __aenter__(self):
        """异步上下文管理器入口 - 创建沙箱"""
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口 - 清理沙箱"""
        
    async def upload_file(self, local_path: str, remote_path: str):
        """上传文件到沙箱"""
        
    async def download_file(self, remote_path: str) -> str:
        """从沙箱下载文件内容"""
        
    async def run_command(self, command: str, timeout: int = 30) -> dict:
        """在沙箱中执行命令，返回stdout、stderr、returncode"""
        
    async def list_dir(self, path: str) -> list[str]:
        """列出沙箱目录内容"""
        
    async def file_exists(self, path: str) -> bool:
        """检查文件是否存在于沙箱中"""
        
    async def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """读取沙箱中的文件"""
```

#### 3. `codemind_mcp/sandbox/tool_executor.py`
沙箱工具执行器

```python
class SandboxedToolExecutor:
    """在沙箱中执行工具逻辑的执行器"""
    
    def __init__(self, sandbox: E2BSandbox, repo_path: str, allowed_dirs: list[str]):
        """初始化执行器"""
        
    async def sync_repo_to_sandbox(self):
        """将仓库文件同步到沙箱（按需同步）"""
        
    async def execute_read_file(self, file_path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """在沙箱中执行ReadFile逻辑"""
        
    async def execute_search_code(self, query: str, max_results: int = 50) -> str:
        """在沙箱中执行SearchCode逻辑"""
        
    async def execute_run_command(self, command: str, timeout: int = 5) -> str:
        """在沙箱中执行RunCommand逻辑"""
```

#### 4. `codemind_mcp/sandbox/sandboxed_tools.py`
沙箱版本的工具包装类

```python
class SandboxedReadFileTool(BaseMCPTool):
    """沙箱版本的ReadFileTool"""
    
class SandboxedSearchCodeTool(BaseMCPTool):
    """沙箱版本的SearchCodeTool"""
    
class SandboxedRunCommandTool(BaseMCPTool):
    """沙箱版本的RunCommandTool"""
```

### 修改的文件

#### 1. `config.yml`
新增E2B相关配置

```yaml
# 新增配置
e2b:
  enabled: false  # 是否启用E2B沙箱
  api_key: "${E2B_API_KEY}"  # E2B API密钥
  template: "base"  # E2B模板
  timeout: 30  # 沙箱操作超时时间
  repo_sync_enabled: true  # 是否同步仓库到沙箱
```

#### 2. `utils/config.py`
新增E2B配置加载逻辑

#### 3. `codemind_mcp/server.py`
修改工具注册逻辑，根据配置选择本地工具或沙箱工具

```python
def get_tools():
    """返回懒初始化的CodeMind MCP工具列表"""
    global _TOOLS
    if _TOOLS is None:
        use_sandbox = Config.get("e2b.enabled", False)
        if use_sandbox:
            # 使用沙箱工具
            _TOOLS = [
                SandboxedReadFileTool(),
                SandboxedSearchCodeTool(),
                SandboxedRunCommandTool(),
                # 索引工具继续使用本地版本
                IndexRepoTool(),
                AddByFilePathTool(),
                DeleteByFilePathTool(),
            ]
        else:
            # 使用本地工具（原有逻辑）
            _TOOLS = [
                ReadFileTool(),
                SearchCodeTool(),
                RunCommandTool(),
                IndexRepoTool(),
                AddByFilePathTool(),
                DeleteByFilePathTool(),
            ]
    return _TOOLS
```

#### 4. `requirements.txt`
新增E2B依赖

```
# 新增
e2b>=0.16.0
```

## 实现步骤

### 阶段1: 基础设施准备

1. **步骤1.1: 更新requirements.txt**
   - 添加`e2b>=0.16.0`依赖
   - 文档说明如何安装

2. **步骤1.2: 新增配置项**
   - 更新`config.yml`添加E2B配置
   - 更新`utils/config.py`支持新配置
   - 创建`.env.example`示例

3. **步骤1.3: 创建沙箱模块目录结构**
   - 创建`codemind_mcp/sandbox/`目录
   - 创建`__init__.py`

### 阶段2: E2B沙箱封装

4. **步骤2.1: 实现E2BSandbox类**
   - 创建`codemind_mcp/sandbox/e2b_sandbox.py`
   - 实现沙箱生命周期管理
   - 实现文件上传/下载
   - 实现命令执行
   - 添加错误处理和日志

5. **步骤2.2: 单元测试E2BSandbox**
   - 创建测试文件
   - 测试基本操作

### 阶段3: 沙箱工具执行器

6. **步骤3.1: 实现工具执行逻辑**
   - 创建`codemind_mcp/sandbox/tool_executor.py`
   - 实现`execute_read_file`
   - 实现`execute_search_code`
   - 实现`execute_run_command`
   - 实现仓库同步逻辑

7. **步骤3.2: 单元测试ToolExecutor**
   - 测试各工具执行逻辑

### 阶段4: 沙箱工具包装

8. **步骤4.1: 创建沙箱工具类**
   - 创建`codemind_mcp/sandbox/sandboxed_tools.py`
   - 实现`SandboxedReadFileTool`
   - 实现`SandboxedSearchCodeTool`
   - 实现`SandboxedRunCommandTool`

### 阶段5: 集成与配置

9. **步骤5.1: 修改MCP服务器**
   - 更新`codemind_mcp/server.py`
   - 实现工具选择逻辑
   - 处理沙箱初始化

10. **步骤5.2: 更新文档**
    - 更新README.md
    - 添加E2B配置说明

### 阶段6: 测试

11. **步骤6.1: 集成测试**
    - 测试本地模式
    - 测试沙箱模式
    - 验证工具功能一致性

12. **步骤6.2: 安全测试**
    - 验证安全检查仍然有效
    - 验证沙箱隔离性

## 测试策略

### 单元测试
- 测试`E2BSandbox`类的各个方法
- 测试`SandboxedToolExecutor`的工具执行逻辑
- Mock E2B SDK避免实际调用

### 集成测试
- 测试完整工具调用流程
- 对比本地模式和沙箱模式的输出一致性
- 测试配置切换功能

### 安全测试
- 验证路径白名单仍然生效
- 验证命令白名单仍然生效
- 验证敏感文件保护仍然有效

## 回滚计划

如果沙箱集成出现问题，可以通过以下步骤回滚：

1. 将`config.yml`中的`e2b.enabled`设置为`false`
2. 如果代码有问题，可以从git恢复修改的文件
3. 卸载E2B依赖（可选）

## 后续优化方向

1. **增量文件同步** - 只同步变更的文件到沙箱
2. **沙池复用** - 复用沙箱实例避免频繁创建
3. **多模板支持** - 为不同类型的任务使用不同的E2B模板
4. **性能监控** - 添加沙箱操作的性能指标
5. **离线模式** - 当E2B不可用时自动降级到本地模式

## 文件清单

### 新增文件
```
codemind_mcp/sandbox/
├── __init__.py
├── e2b_sandbox.py          # E2B沙箱封装
├── tool_executor.py        # 工具执行器
└── sandboxed_tools.py      # 沙箱版本工具
tests/test_sandbox/
├── __init__.py
├── test_e2b_sandbox.py
└── test_tool_executor.py
```

### 修改文件
```
requirements.txt
config.yml
utils/config.py
codemind_mcp/server.py
```

## 注意事项

1. **E2B API密钥**: 需要用户配置E2B API密钥，可以从e2b.dev获取
2. **网络连接**: 沙箱模式需要网络连接到E2B服务
3. **文件同步**: 大仓库首次同步可能需要较长时间
4. **成本**: E2B可能有使用费用，需要用户了解
5. **索引工具**: 索引管理工具继续在本地执行，因为需要访问本地向量数据库

## 附录：E2B使用示例

```python
# 伪代码示例
from e2b import Sandbox

async def demo():
    sandbox = await Sandbox.create()
    
    # 上传文件
    await sandbox.files.write("/test.txt", "Hello, E2B!")
    
    # 执行命令
    result = await sandbox.commands.run("ls -la")
    print(result.stdout)
    
    # 读取文件
    content = await sandbox.files.read("/test.txt")
    print(content)
    
    await sandbox.close()
```
