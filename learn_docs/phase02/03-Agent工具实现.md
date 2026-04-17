# 03. Agent 工具实现

Agent 的强大之处在于它可以调用**工具**来扩展能力。在本项目中，我们实现了三个工具：

| 工具 | 功能 |
|------|------|
| **ReadFile** | 读取指定文件内容，支持行号范围，支持文件名智能搜索，支持外部仓库 |
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

ReadFile 用于读取指定文件的内容，支持按行号范围读取，还支持文件名智能搜索，并且支持读取外部被索引仓库的文件。

### 配置说明

在 `config.yml` 中新增了 `repo.path` 配置项：

```yaml
# 被索引的代码仓库路径（用于 Agent 工具查找文件）
repo:
  path: "/path/to/your/indexed/repo"
```

设置为 `"."` 表示索引的是 CodeMindAgent 项目本身。

### 核心功能

| 功能 | 说明 |
|------|------|
| **多路径解析** | 支持直接路径、相对于 repo_path 的路径、绝对路径 |
| **智能搜索** | 文件不存在时自动按文件名搜索 |
| **外部仓库支持** | 通过 repo.path 配置读取被索引的外部仓库文件 |

### 完整代码

```python
"""
ReadFile 工具

使用 LangChain @tool 装饰器定义，用于读取指定仓库文件内容，支持行号范围。
"""
import os
from typing import Optional, List, Tuple
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import validate_file_access, is_path_allowed, normalize_path

logger = get_logger("agent.tools.read_file")


def should_ignore_dir(dir_name: str) -> bool:
    """判断是否应该忽略的目录"""
    ignore_dirs = {
        '.git', '__pycache__', '.venv', 'venv', 'env', '.env',
        'node_modules', 'build', 'dist', '.idea', '.vscode',
        'chroma_db', 'logs', '.pytest_cache', '.mypy_cache'
    }
    return dir_name in ignore_dirs


def should_ignore_file(file_name: str) -> bool:
    """判断是否应该忽略的文件"""
    ignore_extensions = {
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe',
        '.bin', '.obj', '.o', '.a', '.lib',
        '.zip', '.tar', '.tar.gz', '.rar',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
        '.pdf', '.doc', '.docx', '.ppt', '.pptx',
        '.db', '.sqlite', '.sqlite3'
    }
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ignore_extensions


def get_repo_paths() -> Tuple[str, List[str]]:
    """
    获取仓库路径配置和有效的搜索目录列表

    Returns:
        (repo_path, search_dirs) - 仓库路径和搜索目录列表
    """
    from utils.config import Config

    repo_path = Config.get("repo.path", ".")
    allowed_dirs = Config.get("agent.allowed_dirs", ["."])

    # 如果 repo_path 是绝对路径，直接使用；否则相对于项目根目录
    repo_path = normalize_path(repo_path)

    # 构建搜索目录列表：优先使用 repo_path，然后是 allowed_dirs
    search_dirs = []

    # 添加 repo_path
    if os.path.exists(repo_path) and os.path.isdir(repo_path):
        search_dirs.append(repo_path)

    # 添加 allowed_dirs（如果和 repo_path 不同）
    for allowed_dir in allowed_dirs:
        abs_allowed_dir = normalize_path(allowed_dir)
        if abs_allowed_dir not in search_dirs and os.path.exists(abs_allowed_dir) and os.path.isdir(abs_allowed_dir):
            search_dirs.append(abs_allowed_dir)

    if not search_dirs:
        search_dirs = [normalize_path(".")]

    return repo_path, search_dirs


def resolve_file_path(file_path: str, repo_path: str) -> Optional[str]:
    """
    尝试解析文件路径，支持多种方式

    Args:
        file_path: 用户传入的文件路径
        repo_path: 仓库根路径

    Returns:
        解析后的绝对路径，如果不存在返回 None
    """
    # 方式 1：直接尝试原始路径
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return normalize_path(file_path)

    # 方式 2：在 repo_path 下查找
    path_in_repo = os.path.join(repo_path, file_path)
    if os.path.exists(path_in_repo) and os.path.isfile(path_in_repo):
        return normalize_path(path_in_repo)

    # 方式 3：如果传入的是绝对路径，尝试只取文件名在 repo_path 下查找
    if os.path.isabs(file_path):
        file_name = os.path.basename(file_path)
        path_in_repo_by_name = os.path.join(repo_path, file_name)
        if os.path.exists(path_in_repo_by_name) and os.path.isfile(path_in_repo_by_name):
            return normalize_path(path_in_repo_by_name)

    return None


def search_file_by_name(file_name: str, search_dirs: List[str]) -> List[str]:
    """
    在指定目录中搜索指定文件名

    Args:
        file_name: 要搜索的文件名
        search_dirs: 要搜索的目录列表

    Returns:
        匹配的文件路径列表（相对路径或显示路径）
    """
    from utils.config import Config
    allowed_dirs = Config.get("agent.allowed_dirs", ["."])
    repo_path = Config.get("repo.path", ".")
    repo_path = normalize_path(repo_path)

    matches = []

    # 遍历搜索
    for search_root in search_dirs:
        for root, dirs, files in os.walk(search_root):
            # 过滤忽略目录
            dirs[:] = [d for d in dirs if not should_ignore_dir(d)]

            for f in files:
                if f == file_name and not should_ignore_file(f):
                    full_path = os.path.join(root, f)
                    # 验证路径安全
                    if is_path_allowed(full_path, allowed_dirs + [repo_path]):
                        # 优先显示相对于 repo_path 的路径
                        if full_path.startswith(repo_path + os.sep):
                            display_path = os.path.relpath(full_path, repo_path)
                        else:
                            display_path = os.path.relpath(full_path, normalize_path("."))
                        if display_path not in matches:
                            matches.append(display_path)

    return matches


def get_absolute_path_for_display_path(display_path: str, repo_path: str) -> Optional[str]:
    """
    根据显示路径获取绝对路径

    Args:
        display_path: 显示路径（相对于 repo_path 或项目根目录）
        repo_path: 仓库根路径

    Returns:
        绝对路径，如果不存在返回 None
    """
    # 先尝试在 repo_path 下查找
    path_in_repo = os.path.join(repo_path, display_path)
    if os.path.exists(path_in_repo) and os.path.isfile(path_in_repo):
        return normalize_path(path_in_repo)

    # 再尝试相对于项目根目录
    path_in_project = normalize_path(display_path)
    if os.path.exists(path_in_project) and os.path.isfile(path_in_project):
        return path_in_project

    return None


def _read_file_with_lines(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    内部辅助函数：读取文件内容并处理行号范围

    Args:
        file_path: 文件路径
        start_line: 起始行号
        end_line: 结束行号

    Returns:
        格式化的文件内容字符串
    """
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


@tool
def ReadFile(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    读取指定文件的内容，支持按行号范围读取。
    【重要】：文件路径相对于被索引仓库的根目录！

    Args:
        file_path: 文件路径（相对于被索引仓库根目录）
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
    repo_path, search_dirs = get_repo_paths()

    logger.info(f"Repo path: {repo_path}, search dirs: {search_dirs}")

    try:
        # 尝试解析文件路径
        abs_file_path = resolve_file_path(file_path, repo_path)

        if abs_file_path is not None:
            # 安全验证
            is_allowed, error_msg = validate_file_access(abs_file_path, allowed_dirs + [repo_path], blocked_patterns)
            if not is_allowed:
                return f"[错误] {error_msg}"
            return _read_file_with_lines(abs_file_path, start_line, end_line)

        # 文件不存在，尝试搜索文件名
        file_name = os.path.basename(file_path)
        logger.info(f"File not found: {file_path}, searching for filename: {file_name} in {search_dirs}")

        matches = search_file_by_name(file_name, search_dirs)

        if not matches:
            return f"[错误] 读取文件失败: 文件不存在: {file_path} (在仓库路径 {repo_path} 中未找到)"
        elif len(matches) == 1:
            found_display_path = matches[0]
            abs_found_path = get_absolute_path_for_display_path(found_display_path, repo_path)
            if abs_found_path is None:
                return f"[错误] 找到文件但无法访问: {found_display_path}"

            logger.info(f"Found single match: {abs_found_path}")
            # 验证找到的文件路径
            is_allowed, error_msg = validate_file_access(abs_found_path, allowed_dirs + [repo_path], blocked_patterns)
            if not is_allowed:
                return f"[错误] {error_msg}"
            return _read_file_with_lines(abs_found_path, start_line, end_line)
        else:
            # 多个匹配
            logger.info(f"Found multiple matches: {matches}")
            result = "存在多个同名文件，请传入相对于仓库根目录的完整路径！\n\n找到的文件:\n"
            for i, match in enumerate(matches, 1):
                result += f"{i}. {match}\n"
            return result

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"[错误] 读取文件失败: {str(e)}"
```

### 关键逻辑解析

**1. repo_path 配置支持**

通过 `get_repo_paths()` 函数获取仓库路径配置：

```python
def get_repo_paths() -> Tuple[str, List[str]]:
    repo_path = Config.get("repo.path", ".")
    repo_path = normalize_path(repo_path)
    # 构建搜索目录列表
    ...
```

**2. 多路径解析策略**

`resolve_file_path()` 函数按以下顺序尝试查找文件：

1. 直接使用传入的路径
2. 在 `repo_path` 下查找
3. 如果是绝对路径，提取文件名在 `repo_path` 下查找

**3. 文件名智能搜索**

当传入的文件路径不存在时，工具会自动提取文件名进行搜索，并根据匹配结果智能处理：

- **无匹配**：返回错误信息，包含仓库路径提示
- **单个匹配**：自动读取找到的文件
- **多个匹配**：返回提示信息，列出所有找到的文件路径

**4. 安全验证增强**

```python
# 安全验证时同时允许 allowed_dirs 和 repo_path
is_allowed, error_msg = validate_file_access(
    abs_file_path, 
    allowed_dirs + [repo_path],  # 同时允许两个目录列表
    blocked_patterns
)
```

**5. 友好的路径显示**

搜索结果优先显示相对于 `repo_path` 的路径，而不是绝对路径：

```python
if full_path.startswith(repo_path + os.sep):
    display_path = os.path.relpath(full_path, repo_path)
else:
    display_path = os.path.relpath(full_path, normalize_path("."))
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
支持 Windows 和 Unix 系统，自动进行命令映射。
"""
import subprocess
import shlex
import os
import sys
from langchain_core.tools import tool

from utils.logger import get_logger
from agent.security import is_command_allowed

logger = get_logger("agent.tools.run_command")

# 操作系统检测
IS_WINDOWS = sys.platform.startswith("win")

# Unix 命令到 Windows 命令的映射
# 对于复杂命令，我们提供 Python 实现
WINDOWS_CMD_MAPPING = {
    "ls": ["dir"],
    "cat": ["type"],
    "grep": ["findstr"],
    "find": None,  # 使用 Python 实现
    "head": None,  # 使用 Python 实现
    "tail": None,  # 使用 Python 实现
    "wc": None,    # 使用 Python 实现
    "git": ["git"],  # git 在 Windows 上通常也可用
}

# 同时也允许直接使用 Windows 命令
WINDOWS_ALLOWED_COMMANDS = ["dir", "type", "findstr", "where"]


def _normalize_command_for_windows(command: str) -> tuple[str, list]:
    """
    将 Unix 命令转换为 Windows 命令或 Python 实现

    Returns:
        (command_type, command_data)
        - "native": 使用原生命令，command_data 是 args 列表
        - "python": 使用 Python 实现，command_data 是函数名和参数
    """
    cmd_parts = command.strip().split()
    if not cmd_parts:
        return "native", cmd_parts

    base_cmd = cmd_parts[0].lower()
    args = cmd_parts[1:]

    # 如果已经是 Windows 命令，直接返回
    if base_cmd in WINDOWS_ALLOWED_COMMANDS:
        return "native", cmd_parts

    # 检查是否有映射
    if base_cmd not in WINDOWS_CMD_MAPPING:
        return "native", cmd_parts

    mapped = WINDOWS_CMD_MAPPING[base_cmd]

    # 如果映射为 None，表示使用 Python 实现
    if mapped is None:
        return "python", (base_cmd, args)

    # 替换命令并调整参数
    new_cmd_parts = mapped + args

    # 特殊处理：dir 命令的参数调整
    if base_cmd == "ls":
        # 将 ls 的常见参数转换为 dir 的参数
        new_args = []
        for arg in args:
            if arg == "-l" or arg == "-la" or arg == "-al":
                new_args.append("/Q")  # 显示所有者
            elif arg == "-a":
                new_args.append("/A")  # 显示所有文件
            elif arg == "-R":
                # 禁止递归，跳过此参数
                continue
            elif arg == "-h" or arg == "--human-readable":
                continue  # dir 默认就比较友好
            elif not arg.startswith("-"):
                new_args.append(arg)
        new_cmd_parts = ["dir"] + new_args

    # 特殊处理：grep -> findstr
    if base_cmd == "grep":
        # findstr 的参数顺序不同：pattern file
        new_cmd_parts = ["findstr"] + args

    return "native", new_cmd_parts


def _execute_python_command(cmd_name: str, args: list) -> str:
    """使用 Python 实现的命令"""
    from utils.config import Config

    repo_path = Config.get("repo.path", ".")

    try:
        if cmd_name == "find":
            # 实现简单的 find 命令（限制最多 100 条结果）
            MAX_RESULTS = 100
            result = []
            start_path = repo_path
            pattern = "*"

            # 简单解析参数
            if args:
                # 查找 -name 参数
                if "-name" in args:
                    idx = args.index("-name")
                    if idx + 1 < len(args):
                        pattern = args[idx + 1]
                # 第一个非 - 开头的参数作为起始路径
                for arg in args:
                    if not arg.startswith("-"):
                        start_path = arg
                        break

            # 确保起始路径是绝对路径
            if not os.path.isabs(start_path):
                start_path = os.path.join(repo_path, start_path)

            # 递归查找
            import fnmatch
            for root, dirs, files in os.walk(start_path):
                for name in files + dirs:
                    if fnmatch.fnmatch(name, pattern):
                        rel_path = os.path.relpath(os.path.join(root, name), repo_path)
                        result.append(rel_path)
                        if len(result) >= MAX_RESULTS:
                            break
                if len(result) >= MAX_RESULTS:
                    break

            output = "\n".join(result)
            if len(result) >= MAX_RESULTS:
                output += f"\n\n[警告] 结果已截断，仅显示前 {MAX_RESULTS} 条"

            return output

        elif cmd_name == "head":
            # 实现 head 命令
            n_lines = 10
            file_path = None

            if args:
                if args[0].startswith("-n"):
                    if len(args[0]) > 2:
                        n_lines = int(args[0][2:])
                    elif len(args) > 1:
                        n_lines = int(args[1])
                        args = args[1:]
                    args = args[1:]
                elif args[0].startswith("-") and args[0][1:].isdigit():
                    n_lines = int(args[0][1:])
                    args = args[1:]

            if args:
                file_path = args[0]
                if not os.path.isabs(file_path):
                    file_path = os.path.join(repo_path, file_path)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= n_lines:
                            break
                        lines.append(line.rstrip("\n"))
                    return "\n".join(lines)
            else:
                return "[错误] head 命令需要指定文件名"

        elif cmd_name == "tail":
            # 实现 tail 命令
            n_lines = 10
            file_path = None

            if args:
                if args[0].startswith("-n"):
                    if len(args[0]) > 2:
                        n_lines = int(args[0][2:])
                    elif len(args) > 1:
                        n_lines = int(args[1])
                        args = args[1:]
                    args = args[1:]
                elif args[0].startswith("-") and args[0][1:].isdigit():
                    n_lines = int(args[0][1:])
                    args = args[1:]

            if args:
                file_path = args[0]
                if not os.path.isabs(file_path):
                    file_path = os.path.join(repo_path, file_path)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                    return "\n".join(lines[-n_lines:])
            else:
                return "[错误] tail 命令需要指定文件名"

        elif cmd_name == "wc":
            # 实现 wc 命令
            show_lines = False
            show_words = False
            show_chars = False
            file_path = None

            if not args:
                return "[错误] wc 命令需要指定文件名"

            # 解析参数
            for arg in args:
                if arg == "-l":
                    show_lines = True
                elif arg == "-w":
                    show_words = True
                elif arg == "-c":
                    show_chars = True
                elif not arg.startswith("-"):
                    file_path = arg

            # 默认显示全部
            if not show_lines and not show_words and not show_chars:
                show_lines = show_words = show_chars = True

            if file_path:
                if not os.path.isabs(file_path):
                    file_path = os.path.join(repo_path, file_path)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.count("\n") + 1 if content else 0
                    words = len(content.split())
                    chars = len(content)

                    result = []
                    if show_lines:
                        result.append(str(lines))
                    if show_words:
                        result.append(str(words))
                    if show_chars:
                        result.append(str(chars))
                    result.append(file_path)

                    return " ".join(result)
            else:
                return "[错误] wc 命令需要指定文件名"

        else:
            return f"[错误] 不支持的命令: {cmd_name}"

    except Exception as e:
        logger.error(f"Python command error: {e}")
        return f"[错误] 命令执行失败: {str(e)}"


@tool
def RunCommand(command: str) -> str:
    """
    执行只读 shell 命令（仅白名单内的命令允许执行）。

    允许的命令: ls（推荐-l,禁止-R）, cat, grep, git, find, head, tail, wc
    （Windows 系统自动映射到等效命令或使用 Python 实现）

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
    repo_path = Config.get("repo.path", ".")

    # Windows 下也允许使用 Windows 原生命令
    if IS_WINDOWS:
        allowed_commands = allowed_commands + WINDOWS_ALLOWED_COMMANDS

    # 安全验证：检查命令是否在白名单内
    if not is_command_allowed(command, allowed_commands):
        return f"[错误] 命令不在白名单内，禁止执行: {command}"

    try:
        # Windows 系统特殊处理
        if IS_WINDOWS:
            cmd_type, cmd_data = _normalize_command_for_windows(command)

            if cmd_type == "python":
                # 使用 Python 实现
                logger.info(f"Using Python implementation for: {command}")
                result = _execute_python_command(cmd_data[0], cmd_data[1])
                return "标准输出:\n" + "-" * 40 + "\n" + result

            # 使用原生命令，但需要设置 shell=True 才能正确执行 dir 等内置命令
            args = cmd_data
            work_dir = os.path.abspath(repo_path)

            logger.info(f"Executing Windows command: {args} in {work_dir}")

            # 对于 Windows 内置命令（如 dir），需要使用 shell=True
            base_cmd = args[0].lower() if args else ""
            use_shell = base_cmd in ["dir", "type", "findstr"]

            result = subprocess.run(
                args if not use_shell else " ".join(args),
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=use_shell,
                encoding="utf-8",
                errors="ignore"
            )
        else:
            # Unix 系统正常处理
            args = shlex.split(command)
            work_dir = os.path.abspath(repo_path)

            result = subprocess.run(
                args,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )

        output = []
        MAX_OUTPUT_CHARS = 10000  # 最大输出字符数

        if result.stdout:
            stdout_content = result.stdout
            if len(stdout_content) > MAX_OUTPUT_CHARS:
                stdout_content = stdout_content[:MAX_OUTPUT_CHARS] + "\n\n[警告] 输出已截断，超过 %d 字符" % MAX_OUTPUT_CHARS
            output.append("标准输出:\n" + "-" * 40 + "\n" + stdout_content)

        if result.stderr:
            stderr_content = result.stderr
            if len(stderr_content) > MAX_OUTPUT_CHARS:
                stderr_content = stderr_content[:MAX_OUTPUT_CHARS] + "\n\n[警告] 输出已截断，超过 %d 字符" % MAX_OUTPUT_CHARS
            output.append("标准错误:\n" + "-" * 40 + "\n" + stderr_content)

        output.append(f"\n返回码: {result.returncode}")

        logger.info(f"Command executed successfully: {command}")
        logger.debug("\n".join(output))
        return "\n".join(output)

    except subprocess.TimeoutExpired:
        logger.warning(f"Command timeout: {command}")
        return f"[错误] 命令执行超时（{timeout}秒）: {command}"
    except FileNotFoundError as e:
        logger.error(f"Command not found: {command} (error: {e})")
        return f"[错误] 命令未找到: {command}"
    except ValueError as e:
        logger.error(f"Invalid command: {e}")
        return f"[错误] 命令格式无效: {str(e)}"
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return f"[错误] 命令执行失败: {str(e)}"
```

### 关键设计与安全考虑

**1. 跨平台兼容性**

Windows 和 Unix 系统的命令不同，因此实现了智能映射：

```python
WINDOWS_CMD_MAPPING = {
    "ls": ["dir"],
    "cat": ["type"],
    "grep": ["findstr"],
    "find": None,  # 使用 Python 原生实现
    ...
}
```

对于 `find`、`head`、`tail`、`wc` 等复杂命令，直接用 Python 实现，确保行为一致。

**2. 永远不要用 shell=True！（Unix）**

```python
# ❌ 危险！容易受到 shell 注入
subprocess.run(command, shell=True)

# ✅ 安全！
args = shlex.split(command)  # 先解析
subprocess.run(args, shell=False)  # 再执行
```

**注意**：Windows 下 `dir` 等是 shell 内置命令，需要 `shell=True` 才能执行，但只限于白名单内的命令。

**3. 输出限制**

为了防止输出过多内容消耗 Token，设置了多重限制：

- **参数禁止**：`ls -R`、`dir /S` 等递归参数被安全模块禁止
- **结果数量限制**：`find` 命令最多返回 100 条结果
- **字符数限制**：所有命令输出最多 10000 字符，超过自动截断

```python
MAX_OUTPUT_CHARS = 10000
if len(stdout_content) > MAX_OUTPUT_CHARS:
    stdout_content = stdout_content[:MAX_OUTPUT_CHARS] + "\n\n[警告] 输出已截断..."
```

**4. shlex.split() 的作用**

```python
command = 'ls -la "my dir"'
shlex.split(command)
# 结果：['ls', '-la', 'my dir']
# 正确处理了空格和引号！
```

**5. 超时保护**

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
| **repo.path 配置** | 支持读取外部被索引仓库的文件 |
| **智能搜索** | ReadFile 支持文件名搜索，提升易用性 |
| **多路径解析** | 支持直接路径、repo_path 相对路径、绝对路径 |
| `shlex.split()` | 安全解析命令，防止注入 |
| `shell=False` | 永远不要用 shell=True！ |

---

## 下一步

现在你理解了三个工具的实现，接下来阅读 [04-Agent核心逻辑.md](./04-Agent核心逻辑.md)，深入 Agent 的核心代码！
