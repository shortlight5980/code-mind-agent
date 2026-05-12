# MCP服务器设计

## MCP服务器入口

### 核心依赖

```
mcp>=1.0.0
```

需添加到 requirements.txt

### 代码结构

```python
# mcp/server.py
"""
CodeMind MCP Server

提供文件操作、代码搜索、命令执行、索引管理等工具的MCP服务
"""
import asyncio
import sys
from pathlib import Path

# 确保项目根目录在PYTHONPATH中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from utils.config import Config
from utils.logger import get_logger

# 导入MCP工具
from mcp.tools.read_file import ReadFileTool
from mcp.tools.search_code import SearchCodeTool
from mcp.tools.run_command import RunCommandTool
from mcp.tools.index_manager import IndexRepoTool, AddByFilePathTool, DeleteByFilePathTool

logger = get_logger("mcp.server")

# 创建MCP服务器实例
app = Server("codemind-mcp-server")

# 工具注册表
# 使用惰性初始化，避免在导入时就初始化所有工具
_TOOLS = None

def get_tools():
    """获取所有工具实例（惰性初始化）"""
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = [
            ReadFileTool(),
            SearchCodeTool(),
            RunCommandTool(),
            IndexRepoTool(),
            AddByFilePathTool(),
            DeleteByFilePathTool(),
        ]
    return _TOOLS

@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的MCP工具"""
    tools = get_tools()
    return [tool.get_definition() for tool in tools]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """
    调用MCP工具

    Args:
        name: 工具名称
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    logger.info(f"Calling tool: {name}")

    for tool in get_tools():
        if tool.name == name:
            try:
                result = await tool.call(arguments)
                return result
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return f"Error: {str(e)}"

    raise ValueError(f"Unknown tool: {name}")

async def main():
    """启动MCP服务器"""
    # 加载配置
    Config.load()
    logger.info("CodeMind MCP Server starting...")

    # 使用stdio传输层运行服务器
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

## MCP工具基类

为了统一工具实现，创建基类：

```python
# mcp/tools/base.py
"""
MCP工具基类
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from mcp.types import Tool


class BaseMCPTool(ABC):
    """MCP工具基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """工具输入参数JSON Schema"""
        pass

    def get_definition(self) -> Tool:
        """获取MCP工具定义"""
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema,
        )

    @abstractmethod
    async def call(self, arguments: Dict[str, Any]) -> str:
        """
        调用工具

        Args:
            arguments: 工具参数字典

        Returns:
            工具执行结果字符串
        """
        pass
```

## 工具接口规范

### ReadFileTool

```python
# mcp/tools/read_file.py
"""
ReadFile MCP Tool
"""
from typing import Any, Dict, Optional
from mcp.tools.base import BaseMCPTool
from utils.logger import get_logger

# 导入共享模块
from agent.security import validate_file_access, is_path_allowed, normalize_path
from agent.tool_paths import get_allowed_dirs, get_repo_path, get_repo_paths_for_read
from agent.tools.output_truncation import truncate_tool_output

logger = get_logger("mcp.tools.read_file")


class ReadFileTool(BaseMCPTool):
    """读取文件内容的MCP工具"""

    @property
    def name(self) -> str:
        return "codemind_read_file"

    @property
    def description(self) -> str:
        return (
            "读取指定文件的内容，支持按行号范围读取。"
            "文件路径相对于被索引仓库的根目录。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（相对于被索引仓库根目录）",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从1开始，包含），不指定则从文件开头读取",
                    "minimum": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（包含），不指定则读取到文件末尾",
                    "minimum": 1,
                },
            },
            "required": ["file_path"],
        }

    async def call(self, arguments: Dict[str, Any]) -> str:
        """调用ReadFile工具"""
        # 复用原有的read_file.py中的核心逻辑
        from agent.tools.read_file import (
            resolve_file_path,
            search_file_by_name,
            get_absolute_path_for_display_path,
            _read_file_with_lines,
        )

        file_path = arguments["file_path"]
        start_line = arguments.get("start_line")
        end_line = arguments.get("end_line")

        logger.info(f"ReadFile called: file_path={file_path}, start_line={start_line}, end_line={end_line}")

        # 以下复用原有逻辑...
        allowed_dirs = get_allowed_dirs(include_repo_path=False)
        repo_path, search_dirs = get_repo_paths_for_read()

        try:
            # 尝试解析文件路径
            abs_file_path = resolve_file_path(file_path, repo_path)

            if abs_file_path is not None:
                # 安全验证
                is_allowed, error_msg = validate_file_access(abs_file_path, allowed_dirs + [repo_path])
                if not is_allowed:
                    return f"Error: {error_msg}"
                return _read_file_with_lines(abs_file_path, start_line, end_line)

            # 文件不存在，尝试搜索文件名
            file_name = Path(file_path).name
            logger.info(f"File not found: {file_path}, searching for filename: {file_name}")

            matches = search_file_by_name(file_name, search_dirs)

            if not matches:
                return f"Error: File not found: {file_path}"
            elif len(matches) == 1:
                found_display_path = matches[0]
                abs_found_path = get_absolute_path_for_display_path(found_display_path, repo_path)
                if abs_found_path is None:
                    return f"Error: Found file but cannot access: {found_display_path}"

                # 验证找到的文件路径
                is_allowed, error_msg = validate_file_access(abs_found_path, allowed_dirs + [repo_path])
                if not is_allowed:
                    return f"Error: {error_msg}"
                return _read_file_with_lines(abs_found_path, start_line, end_line)
            else:
                # 多个匹配
                result = "Multiple files found:\n\n"
                for i, match in enumerate(matches, 1):
                    result += f"{i}. {match}\n"
                return truncate_tool_output(result, "ReadFile")

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return f"Error: Failed to read file: {str(e)}"
```

### SearchCodeTool

类似地，SearchCodeTool 复用原有的 search_code.py 逻辑：

```python
# mcp/tools/search_code.py
"""
SearchCode MCP Tool
"""
from typing import Any, Dict
from mcp.tools.base import BaseMCPTool
from utils.logger import get_logger

from agent.security import is_path_allowed
from agent.tool_paths import get_allowed_dirs, get_repo_path, resolve_repo_relative_path
from agent.tools.output_truncation import truncate_tool_output

logger = get_logger("mcp.tools.search_code")


class SearchCodeTool(BaseMCPTool):
    """在代码库中搜索的MCP工具"""

    @property
    def name(self) -> str:
        return "codemind_search_code"

    @property
    def description(self) -> str:
        return "在代码库中搜索关键词或正则表达式。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或正则表达式",
                },
                "is_regex": {
                    "type": "boolean",
                    "description": "是否使用正则表达式搜索，默认为false",
                    "default": False,
                },
                "search_dir": {
                    "type": "string",
                    "description": "搜索目录，默认为当前目录",
                    "default": ".",
                },
            },
            "required": ["query"],
        }

    async def call(self, arguments: Dict[str, Any]) -> str:
        """调用SearchCode工具"""
        # 复用原有的search_code.py核心逻辑
        from agent.tools.search_code import (
            should_ignore_dir,
            should_ignore_file,
        )
        import os
        import re
        from typing import List

        query = arguments["query"]
        is_regex = arguments.get("is_regex", False)
        search_dir = arguments.get("search_dir", ".")

        logger.info(f"SearchCode called: query={query}, is_regex={is_regex}, search_dir={search_dir}")

        from utils.config import Config

        allowed_dirs = get_allowed_dirs()
        max_results = Config.get("agent.max_search_results", 50)
        repo_path = get_repo_path()

        # 安全验证：搜索目录必须在白名单内
        abs_search_dir = resolve_repo_relative_path(search_dir, repo_path)

        if not is_path_allowed(abs_search_dir, allowed_dirs):
            return f"Error: Search directory not allowed: {search_dir}"

        if not os.path.exists(abs_search_dir):
            return f"Error: Search directory not found: {search_dir}"

        if not os.path.isdir(abs_search_dir):
            return f"Error: Not a directory: {search_dir}"

        try:
            # 以下复用原有搜索逻辑...
            if is_regex:
                try:
                    pattern = re.compile(query, re.IGNORECASE)
                except re.error as e:
                    return f"Error: Invalid regex: {str(e)}"
            else:
                pattern = re.compile(re.escape(query), re.IGNORECASE)

            results: List[str] = []
            match_count = 0

            for root, dirs, files in os.walk(abs_search_dir):
                dirs[:] = [d for d in dirs if not should_ignore_dir(d)]

                for file in files:
                    if should_ignore_file(file):
                        continue

                    file_path = os.path.join(root, file)

                    if not is_path_allowed(file_path, allowed_dirs):
                        continue

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()

                        file_matches = []
                        for line_num, line in enumerate(lines, 1):
                            if pattern.search(line):
                                snippet = line.rstrip('\n')
                                file_matches.append(f"    Line {line_num}: {snippet}")
                                match_count += 1

                        if file_matches:
                            rel_path = os.path.relpath(file_path, abs_search_dir)
                            results.append(f"📄 {rel_path}")
                            results.extend(file_matches)
                            results.append("")

                        if len(results) >= max_results * 3:
                            results.append(f"... (Truncated, showing first {max_results} matches)")
                            break

                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        logger.debug(f"Error searching file {file_path}: {e}")
                        continue

                if len(results) >= max_results * 3:
                    break

            if not results:
                return f"No matches found: {query}"

            header = f"Search results (total {match_count} matches):\n" + "=" * 80 + "\n"
            return truncate_tool_output(header + "\n".join(results), "SearchCode")

        except Exception as e:
            logger.error(f"Error in SearchCode: {e}")
            return f"Error: Search failed: {str(e)}"
```

### RunCommandTool

```python
# mcp/tools/run_command.py
"""
RunCommand MCP Tool
"""
from typing import Any, Dict
from mcp.tools.base import BaseMCPTool
from utils.logger import get_logger

from agent.security import is_command_allowed
from agent.tool_paths import get_repo_path
from agent.tools.output_truncation import truncate_tool_output

logger = get_logger("mcp.tools.run_command")


class RunCommandTool(BaseMCPTool):
    """执行只读shell命令的MCP工具"""

    @property
    def name(self) -> str:
        return "codemind_run_command"

    @property
    def description(self) -> str:
        return (
            "执行只读shell命令（仅白名单内的命令允许执行）。"
            "允许的命令：ls, cat, grep, git, find, head, tail, wc"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的shell命令字符串",
                },
            },
            "required": ["command"],
        }

    async def call(self, arguments: Dict[str, Any]) -> str:
        """调用RunCommand工具"""
        # 复用原有的run_command.py核心逻辑
        from agent.tools.run_command import (
            _normalize_command_for_windows,
            _execute_python_command,
            IS_WINDOWS,
        )
        import subprocess
        import sys
        import os

        command = arguments["command"]

        logger.info(f"RunCommand called: {command}")

        from utils.config import Config

        allowed_commands = Config.get("agent.allowed_commands", [
            "ls", "cat", "grep", "git", "find", "head", "tail", "wc"
        ])
        timeout = Config.get("agent.command_timeout", 5)
        repo_path = get_repo_path()

        # Windows下也允许使用Windows原生命令
        if IS_WINDOWS:
            allowed_commands = allowed_commands + ["dir", "type", "findstr", "where"]

        # 安全验证：检查命令是否在白名单内
        if not is_command_allowed(command, allowed_commands):
            return f"Error: Command not allowed: {command}"

        try:
            # Windows系统特殊处理
            if IS_WINDOWS:
                cmd_type, cmd_data = _normalize_command_for_windows(command)

                if cmd_type == "python":
                    logger.info(f"Using Python implementation for: {command}")
                    result = _execute_python_command(cmd_data[0], cmd_data[1])
                    return truncate_tool_output("Stdout:\n" + "-" * 40 + "\n" + result, "RunCommand")

                args = cmd_data
                work_dir = repo_path

                logger.info(f"Executing Windows command: {args} in {work_dir}")

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
                import shlex
                args = shlex.split(command)
                work_dir = repo_path

                result = subprocess.run(
                    args,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    shell=False
                )

            output = []

            if result.stdout:
                output.append("Stdout:\n" + "-" * 40 + "\n" + result.stdout)

            if result.stderr:
                output.append("Stderr:\n" + "-" * 40 + "\n" + result.stderr)

            output.append(f"\nExit code: {result.returncode}")

            logger.info(f"Command executed successfully: {command}")
            return truncate_tool_output("\n".join(output), "RunCommand")

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timeout: {command}")
            return f"Error: Command timed out ({timeout}s): {command}"
        except FileNotFoundError as e:
            logger.error(f"Command not found: {command} (error: {e})")
            return f"Error: Command not found: {command}"
        except ValueError as e:
            logger.error(f"Invalid command: {e}")
            return f"Error: Invalid command: {str(e)}"
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return f"Error: Command execution failed: {str(e)}"
```

### 索引管理工具

索引管理工具包装 scripts/ 下的脚本：

```python
# mcp/tools/index_manager/__init__.py
"""
Index Manager MCP Tools
"""
from mcp.tools.index_manager.index_repo import IndexRepoTool
from mcp.tools.index_manager.add_by_file_path import AddByFilePathTool
from mcp.tools.index_manager.delete_by_file_path import DeleteByFilePathTool

__all__ = [
    "IndexRepoTool",
    "AddByFilePathTool",
    "DeleteByFilePathTool",
]
```

```python
# mcp/tools/index_manager/index_repo.py
"""
IndexRepo MCP Tool
"""
from typing import Any, Dict, Optional
from mcp.tools.base import BaseMCPTool
from utils.logger import get_logger

logger = get_logger("mcp.tools.index_repo")


class IndexRepoTool(BaseMCPTool):
    """索引整个仓库的MCP工具"""

    @property
    def name(self) -> str:
        return "codemind_index_repo"

    @property
    def description(self) -> str:
        return "索引整个Git仓库到向量数据库。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "仓库路径（可选，默认为配置文件中的repo.path）",
                },
                "persist_dir": {
                    "type": "string",
                    "description": "向量数据库保存目录（可选）",
                },
            },
            "required": [],
        }

    async def call(self, arguments: Dict[str, Any]) -> str:
        """调用IndexRepo工具"""
        import sys
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent.parent
        sys.path.insert(0, str(project_root))

        from scripts.index_repo import index_repo
        from utils.config import Config

        repo_path = arguments.get("repo_path")
        persist_dir = arguments.get("persist_dir")

        logger.info(f"IndexRepo called: repo_path={repo_path}, persist_dir={persist_dir}")

        try:
            # 确保配置已加载
            Config.load()

            # 调用索引函数
            index_repo(repo_path, persist_dir)

            return "Indexing completed successfully"

        except Exception as e:
            logger.error(f"Error indexing repo: {e}")
            return f"Error: Indexing failed: {str(e)}"
```

## Claude Desktop配置

```json
{
  "mcpServers": {
    "codemind": {
      "command": "python",
      "args": [
        "/home/ljw/桌面/CodeMind/code-mind-agent/mcp/server.py"
      ],
      "cwd": "/home/ljw/桌面/CodeMind/code-mind-agent",
      "env": {
        "PYTHONPATH": ".",
        "DASHSCOPE_API_KEY": "${env:DASHSCOPE_API_KEY}"
      }
    }
  }
}
```
