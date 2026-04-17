# 03. Agent 工具实现

Agent 的强大之处在于它可以调用**工具**来扩展能力。在本项目中，我们实现了三个工具：

| 工具 | 功能 |
|------|------|
| **ReadFile** | 读取指定文件内容，支持行号范围 |
| **SearchCode** | 在代码库中搜索关键词或正则表达式 |
| **RunCommand** | 执行只读 shell 命令 |

让我们逐个解析它们的实现！

---

## LangChain @tool 装饰器

在解析具体工具之前，先了解一下 LangChain 的 `@tool` 装饰器。

### 基本用法

```python
from langchain_core.tools import tool

@tool
def MyTool(arg1: str, arg2: int) -> str:
    """
    这里是工具的描述，LLM 会看这个描述来理解工具的作用。
    
    Args:
        arg1: 参数1的说明
        arg2: 参数2的说明
    
    Returns:
        返回值的说明
    """
    # 工具逻辑
    return "结果"
```

**关键点**：
- ✅ 用 `@tool` 装饰函数
- ✅ 函数的 docstring 很重要！LLM 用它来理解工具
- ✅ 类型提示 `arg1: str` 也很重要！LLM 用它来理解参数类型

### 工具是如何被调用的？

```
LLM 决定调用 ReadFile
    ↓
生成 JSON：{"tool": "ReadFile", "args": {"file_path": "utils/logger.py"}}
    ↓
LangChain 自动解析并调用 ReadFile(file_path="utils/logger.py")
    ↓
工具返回结果
    ↓
结果追加到对话上下文中，LLM 继续思考
```

---

## 工具一：ReadFile

ReadFile 用于读取指定文件的内容，支持按行号范围读取。

### 完整代码

```python
"""
ReadFile 工具

使用 LangChain @tool 装饰器定义，用于读取指定仓库文件内容，支持行号范围。
"""
from typing import Optional
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import validate_file_access

logger = get_logger("agent.tools.read_file")


@tool
def ReadFile(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    读取指定文件的内容，支持按行号范围读取。

    Args:
        file_path: 文件路径（相对于项目根目录或绝对路径）
        start_line: 起始行号（从 1 开始，包含），不指定则从文件开头读取
        end_line: 结束行号（包含），不指定则读取到文件末尾

    Returns:
        文件内容字符串
    """
    from utils.config import Config

    logger.info(f"[ToolsCall] ReadFile called: file_path={file_path}, start_line={start_line}, end_line={end_line}")

    # 加载配置
    allowed_dirs = Config.get("agent.allowed_dirs", ["."])
    blocked_patterns = Config.get("agent.blocked_files", None)

    # 安全验证
    is_allowed, error_msg = validate_file_access(file_path, allowed_dirs, blocked_patterns)
    if not is_allowed:
        return f"[错误] {error_msg}"

    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total_lines = len(lines)

        # 处理行号范围
        if start_line is None:
            start_idx = 0
        else:
            start_idx = max(0, start_line - 1)

        if end_line is None:
            end_idx = total_lines
        else:
            end_idx = min(total_lines, end_line)

        if start_idx >= end_idx:
            return f"[警告] 行号范围无效: start_line={start_line}, end_line={end_line}, 文件共 {total_lines} 行"

        # 截取内容并添加行号
        result_lines = []
        for i in range(start_idx, end_idx):
            line_num = i + 1
            result_lines.append(f"{line_num:6d} | {lines[i]}")

        content = ''.join(result_lines)
        file_info = f"文件: {file_path} (总行数: {total_lines}, 显示: {start_idx + 1}-{end_idx})\n"
        separator = "-" * 80 + "\n"

        logger.info(f"Successfully read file: {file_path}")
        logger.debug(file_info + separator + content)
        return file_info + separator + content

    except UnicodeDecodeError:
        # 尝试用其他编码读取
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
            logger.info(f"Successfully read file with gbk encoding: {file_path}")
            return f"文件: {file_path} (GBK 编码)\n" + "-" * 80 + "\n" + content
        except Exception as e2:
            logger.error(f"Failed to read file with fallback encoding: {e2}")
            return f"[错误] 无法读取文件 {file_path}: 编码不支持"
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"[错误] 读取文件失败: {str(e)}"
    
```

### 关键逻辑解析

**1. 先安全验证，再执行！**

```python
is_allowed, error_msg = validate_file_access(...)
if not is_allowed:
    return f"[错误] {error_msg}"
```

**2. 行号处理**

- 用户输入的是 1-based（从 1 开始）
- Python 列表是 0-based（从 0 开始）
- 需要转换：`start_idx = max(0, start_line - 1)`

**3. 编码容错**

```python
try:
    # 先用 UTF-8 读取
    with open(file_path, 'r', encoding='utf-8') as f:
        ...
except UnicodeDecodeError:
    # 失败了试试 GBK（Windows 常见）
    with open(file_path, 'r', encoding='gbk') as f:
        ...
```

**4. 友好的返回格式**

```
文件: utils/logger.py (总行数: 50, 显示: 1-50)
--------------------------------------------------------------------------------
     1 | import logging
     2 | import os
     3 | ...
```

---

## 工具二：SearchCode

SearchCode 用于在代码库中搜索关键词或正则表达式。

### 核心代码片段

```python
@tool
def SearchCode(query: str, is_regex: bool = False, search_dir: str = ".") -> str:
    """
    在代码库中搜索关键词或正则表达式。

    Args:
        query: 搜索关键词或正则表达式
        is_regex: 是否使用正则表达式搜索，默认为 False
        search_dir: 搜索目录，默认为当前目录 "."

    Returns:
        搜索结果字符串
    """
    from utils.config import Config

    logger.info(f"SearchCode called: query={query}, is_regex={is_regex}, search_dir={search_dir}")

    # 加载配置
    allowed_dirs = Config.get("agent.allowed_dirs", ["."])
    max_results = Config.get("agent.max_search_results", 50)

    # 安全验证：搜索目录必须在白名单内
    if not is_path_allowed(search_dir, allowed_dirs):
        return f"[错误] 搜索目录不在允许的白名单内: {search_dir}"

    # ... 省略目录遍历代码 ...

    # 编译正则表达式
    if is_regex:
        pattern = re.compile(query, re.IGNORECASE)
    else:
        # 普通关键词搜索，转义特殊字符
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    # 遍历目录搜索
    for root, dirs, files in os.walk(abs_search_dir):
        # 过滤掉需要忽略的目录
        dirs[:] = [d for d in dirs if not should_ignore_dir(d)]
        
        for file_name in files:
            if should_ignore_file(file_name):
                continue
            
            # 读取文件并搜索
            # ...
```

### 关键逻辑解析

**1. 支持普通搜索和正则搜索**

```python
if is_regex:
    pattern = re.compile(query, re.IGNORECASE)
else:
    # 普通搜索：用 re.escape() 转义特殊字符
    pattern = re.compile(re.escape(query), re.IGNORECASE)
```

**2. 忽略目录和文件**

```python
def should_ignore_dir(dir_name: str) -> bool:
    ignore_dirs = {'.git', '__pycache__', 'node_modules', ...}
    return dir_name in ignore_dirs

def should_ignore_file(file_name: str) -> bool:
    ignore_extensions = {'.pyc', '.zip', '.jpg', ...}
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ignore_extensions
```

**3. 友好的结果展示**

```
搜索结果 (共 5 个匹配):
================================================================================
📄 app.py
    行 15: from agent.agent import create_codemind_agent
    行 20: services: Dict[str, Any] = {}

📄 utils/logger.py
    行 43: def get_logger(name: str = "codemind") -> logging.Logger:
```

---

## 工具三：RunCommand

RunCommand 用于执行只读 shell 命令。

### 完整代码

```python
"""
RunCommand 工具

使用 LangChain @tool 装饰器定义，用于执行只读 shell 命令。
"""
import subprocess
import shlex
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import is_command_allowed

logger = get_logger("agent.tools.run_command")


@tool
def RunCommand(command: str) -> str:
    """
    执行只读 shell 命令（仅白名单内的命令允许执行）。

    允许的命令: ls, cat, grep, git, find, head, tail, wc

    Args:
        command: 要执行的 shell 命令字符串

    Returns:
        命令执行结果（stdout + stderr）
    """
    from utils.config import Config

    logger.info(f"RunCommand called: {command}")

    # 加载配置
    allowed_commands = Config.get("agent.allowed_commands", [
        "ls", "cat", "grep", "git", "find", "head", "tail", "wc"
    ])
    timeout = Config.get("agent.command_timeout", 5)

    # 安全验证：检查命令是否在白名单内
    if not is_command_allowed(command, allowed_commands):
        return f"[错误] 命令不在白名单内，禁止执行: {command}"

    try:
        # 解析命令（安全解析，防止 shell 注入）
        args = shlex.split(command)

        # 执行命令，不使用 shell=True
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False  # 关键安全设置：不使用 shell
        )

        output = []

        if result.stdout:
            output.append("标准输出:\n" + "-" * 40 + "\n" + result.stdout)

        if result.stderr:
            output.append("标准错误:\n" + "-" * 40 + "\n" + result.stderr)

        output.append(f"\n返回码: {result.returncode}")

        logger.info(f"Command executed successfully: {command}")
        logger.debug("\n".join(output))
        return "\n".join(output)

    except subprocess.TimeoutExpired:
        logger.warning(f"Command timeout: {command}")
        return f"[错误] 命令执行超时（{timeout}秒）: {command}"
    except FileNotFoundError:
        logger.error(f"Command not found: {command}")
        return f"[错误] 命令未找到: {command}"
    except ValueError as e:
        logger.error(f"Invalid command: {e}")
        return f"[错误] 命令格式无效: {str(e)}"
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return f"[错误] 命令执行失败: {str(e)}"
```

### 关键安全设计

**1. 永远不要用 shell=True！**

```python
# ❌ 危险！容易受到 shell 注入
subprocess.run(command, shell=True)

# ✅ 安全！
args = shlex.split(command)  # 先解析
subprocess.run(args, shell=False)  # 再执行
```

**2. shlex.split() 的作用**

```python
command = 'ls -la "my dir"'
shlex.split(command)
# 结果：['ls', '-la', 'my dir']
# 正确处理了空格和引号！
```

**3. 超时保护**

```python
timeout = Config.get("agent.command_timeout", 5)  # 默认 5 秒
result = subprocess.run(args, timeout=timeout, ...)
```

防止命令卡住。

---

## 工具的统一注册

在 `agent/tools/__init__.py` 中：

```python
from .read_file import ReadFile
from .search_code import SearchCode
from .run_command import RunCommand

__all__ = ["ReadFile", "SearchCode", "RunCommand"]
```

然后在 `agent/agent.py` 中：

```python
from agent.tools import ReadFile, SearchCode, RunCommand

def get_tools():
    return [ReadFile, SearchCode, RunCommand]
```

---

## 关键知识点总结

| 知识点 | 说明 |
|--------|------|
| `@tool` 装饰器 | 将函数变成 LangChain 工具 |
| **Docstring** | LLM 用它来理解工具的作用 |
| **类型提示** | LLM 用它来理解参数类型 |
| **安全优先** | 工具执行前先验证安全性 |
| `shlex.split()` | 安全解析命令，防止注入 |
| `shell=False` | 永远不要用 shell=True！ |

---

## 下一步

现在你理解了三个工具的实现，接下来阅读 [04-Agent核心逻辑.md](./04-Agent核心逻辑.md)，深入 Agent 的核心代码！
