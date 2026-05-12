"""
CodeMind MCP 服务器入口点。

本模块作为 CodeMind Model Context Protocol (MCP) 服务器的核心启动脚本，
负责初始化环境、动态加载依赖、注册工具以及启动 STDIO 传输层以处理客户端请求。
支持两种运行模式：
1. 作为独立脚本直接运行（__package__ 为空）：通过动态导入机制模拟包结构，确保路径正确。
2. 作为 Python 包的一部分运行：使用标准的相对导入机制。
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys

# ==============================================================================
# 1. 环境变量配置
# ==============================================================================

# 设置环境变量 CODEMIND_LOG_STDERR 为 "1"，指示日志系统将日志输出重定向到标准错误流 (stderr)。
# 使用 setdefault 确保只有在环境变量未设置时才进行设置，允许外部覆盖此行为。
os.environ.setdefault("CODEMIND_LOG_STDERR", "1")

# ==============================================================================
# 2. 动态导入与路径引导 (针对直接运行脚本模式)
# ==============================================================================

# 检查当前模块是否作为包的一部分运行。
# 如果 __package__ 为 None 或空字符串，说明是通过 `python server.py` 直接执行的。
if __package__ in (None, ""):
    # --------------------------------------------------------------------------
    # 2.1 添加项目根目录到 sys.path
    # --------------------------------------------------------------------------
    # 计算项目根目录：当前文件所在目录的上一级目录 (mcp/ 的父目录即项目根目录)。
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 如果项目根目录不在系统路径中，将其插入到路径列表的最前面，确保优先加载项目内的模块。
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # --------------------------------------------------------------------------
    # 2.2 动态创建本地包别名 (codemind_local_mcp)
    # --------------------------------------------------------------------------
    # 获取当前文件所在的目录，即 mcp/ 目录，作为本地包的根路径。
    local_package_root = os.path.dirname(os.path.abspath(__file__))
    
    # 定义一个临时的包别名，用于在直接运行时模拟包导入行为。
    local_alias = "codemind_local_mcp"
    
    # 检查该别名是否已经加载过，避免重复加载导致的状态不一致。
    if local_alias not in sys.modules:
        # 创建一个模块规范 (ModuleSpec)，指向本地包根目录下的 __init__.py 文件。
        # submodule_search_locations 指定了子模块的搜索路径，确保从该目录导入子模块。
        alias_spec = importlib.util.spec_from_file_location(
            local_alias,
            os.path.join(local_package_root, "__init__.py"),
            submodule_search_locations=[local_package_root],
        )
        
        # 安全检查：如果无法创建规范或加载器为空，抛出运行时错误。
        if alias_spec is None or alias_spec.loader is None:
            raise RuntimeError("Failed to bootstrap local MCP package")
        
        # 根据规范创建一个新的模块对象。
        alias_module = importlib.util.module_from_spec(alias_spec)
        
        # 将创建的模块注册到 sys.modules 中，键为别名，这样后续的 import 语句可以找到它。
        sys.modules[local_alias] = alias_module
        
        # 执行模块代码，完成模块的初始化。
        alias_spec.loader.exec_module(alias_module)

    # --------------------------------------------------------------------------
    # 2.3 从本地别名模块中导入 SDK 核心组件
    # --------------------------------------------------------------------------
    # 动态导入 sdk 子模块。
    sdk_module = importlib.import_module(f"{local_alias}.sdk")
    
    # 提取所需的类和函数：
    # LocalServerShim: 本地服务器垫片，用于兼容不同版本的 MCP SDK。
    LocalServerShim = sdk_module.LocalServerShim
    
    # load_sdk_modules: 加载并返回标准 SDK 模块和类型的辅助函数。
    load_sdk_modules = sdk_module.load_sdk_modules
    
    # local_stdio_server: 本地实现的 STDIO 服务器上下文管理器。
    local_stdio_server = sdk_module.local_stdio_server
    
    # 调用 load_sdk_modules 获取标准的服务器类型、stdio 服务器实现、忽略的第三个返回值以及类型定义模块。
    ServerType, stdio_server, _, types_module = load_sdk_modules()

    # --------------------------------------------------------------------------
    # 2.4 从本地别名模块中导入工具类
    # --------------------------------------------------------------------------
    # 动态导入 tools 主模块。
    tools_module = importlib.import_module(f"{local_alias}.tools")
    
    # 动态导入 index_manager 子模块，包含索引相关的工具。
    index_module = importlib.import_module(f"{local_alias}.tools.index_manager")
    
    # 提取具体的工具类：
    # ReadFileTool: 读取文件内容的工具。
    ReadFileTool = tools_module.ReadFileTool
    
    # RunCommandTool: 执行系统命令的工具。
    RunCommandTool = tools_module.RunCommandTool
    
    # SearchCodeTool: 搜索代码库的工具。
    SearchCodeTool = tools_module.SearchCodeTool
    
    # AddByFilePathTool: 通过文件路径添加内容到索引的工具。
    AddByFilePathTool = index_module.AddByFilePathTool
    
    # DeleteByFilePathTool: 通过文件路径从索引删除内容的工具。
    DeleteByFilePathTool = index_module.DeleteByFilePathTool
    
    # IndexRepoTool: 对整个仓库进行索引构建的工具。
    IndexRepoTool = index_module.IndexRepoTool

else:
    # ==============================================================================
    # 3. 标准包导入模式 (针对作为包运行模式)
    # ==============================================================================
    
    # 如果当前模块是作为包的一部分被导入的（例如 `python -m codemind.mcp.server`），
    # 则使用标准的相对导入语法，更加简洁且符合 Python 规范。
    
    # 从同级目录的 sdk 模块导入核心组件。
    from .sdk import LocalServerShim, load_sdk_modules, local_stdio_server
    
    # 从 tools.index_manager 子包导入索引管理工具。
    from .tools.index_manager import AddByFilePathTool, DeleteByFilePathTool, IndexRepoTool
    
    # 从 tools.read_file 模块导入文件读取工具。
    from .tools.read_file import ReadFileTool
    
    # 从 tools.run_command 模块导入命令执行工具。
    from .tools.run_command import RunCommandTool
    
    # 从 tools.search_code 模块导入代码搜索工具。
    from .tools.search_code import SearchCodeTool

# ==============================================================================
# 4. 路径二次确认与通用依赖导入
# ==============================================================================

# 再次检查并确保项目根目录在 sys.path 中。
# 这一步主要是为了在非包模式下提供额外的保障，防止在某些极端情况下路径丢失。
if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# 导入项目通用的配置管理模块。
from utils.config import Config

# 导入项目通用的日志记录模块。
from utils.logger import get_logger

# 初始化名为 "mcp.server" 的日志记录器实例，用于后续的服务日志输出。
logger = get_logger("mcp.server")

# 如果是在包模式下运行，此时需要调用 load_sdk_modules 来初始化 SDK 相关变量。
# 在非包模式下，这些变量已经在上面的 if 块中初始化过了。
if __package__ not in (None, ""):
    ServerType, stdio_server, _, types_module = load_sdk_modules()

# ==============================================================================
# 5. 服务器实例化与全局状态初始化
# ==============================================================================

# 创建 MCP 服务器应用实例。
# 优先使用从 SDK 加载的标准 ServerType，如果不可用则回退到 LocalServerShim。
# 服务器名称标识为 "codemind-mcp-server"。
app = (ServerType or LocalServerShim)("codemind-mcp-server")

# 定义全局变量 _TOOLS，用于缓存已初始化的工具实例列表。
# 初始值为 None，表示尚未加载。
_TOOLS = None

# 从类型定义模块中提取必要的响应类型类，用于构建符合 MCP 协议的标准响应对象。
# 使用 getattr 并提供默认值 None，以防止在某些精简环境下类型模块缺失导致崩溃。
TextContent = getattr(types_module, "TextContent", None) if types_module else None
CallToolResult = getattr(types_module, "CallToolResult", None) if types_module else None


# ==============================================================================
# 6. 工具管理辅助函数
# ==============================================================================

def get_tools():
    """
    获取所有注册的工具实例列表。

    采用单例模式（Lazy Initialization）缓存工具列表。
    首次调用时实例化所有工具并缓存到全局变量 _TOOLS 中，
    后续调用直接返回缓存列表，避免重复创建对象带来的开销。

    Returns:
        list: 包含所有已初始化工具实例的列表。
    """
    global _TOOLS
    if _TOOLS is None:
        # 实例化所有可用的工具类
        _TOOLS = [
            ReadFileTool(),       # 文件读取工具
            SearchCodeTool(),     # 代码搜索工具
            RunCommandTool(),     # 命令执行工具
            IndexRepoTool(),      # 仓库索引工具
            AddByFilePathTool(),  # 添加文件索引工具
            DeleteByFilePathTool(), # 删除文件索引工具
        ]
    return _TOOLS


async def list_registered_tools():
    """
    异步获取所有注册工具的定义描述列表。

    遍历所有工具实例，调用其 get_definition() 方法获取工具的元数据
    （如名称、描述、参数 schema 等），供 MCP 客户端发现和使用。

    Returns:
        list: 包含所有工具定义字典的列表。
    """
    return [tool.get_definition() for tool in get_tools()]


async def call_registered_tool(name: str, arguments: dict | None = None) -> str:
    """
    根据工具名称查找并执行对应的工具。

    Args:
        name (str): 要调用的工具的唯一名称。
        arguments (dict | None): 传递给工具的执行参数，默认为空字典。

    Returns:
        str: 工具执行后的结果字符串。

    Raises:
        ValueError: 如果提供的工具名称在已注册工具列表中不存在。
    """
    # 遍历所有已初始化的工具实例
    for tool in get_tools():
        # 匹配工具名称
        if tool.name == name:
            # 异步调用工具的 call 方法，传入参数（如果为 None 则传空字典）
            return await tool.call(arguments or {})
    
    # 如果遍历结束仍未找到匹配的工具，抛出异常
    raise ValueError(f"Unknown tool: {name}")


# ==============================================================================
# 7. MCP 协议接口实现
# ==============================================================================

@app.list_tools()
async def list_tools():
    """
    MCP 协议处理器：列出所有可用工具。

    当 MCP 客户端发送 `list_tools` 请求时，此异步函数会被调用。
    它委托给 list_registered_tools 函数来获取工具定义列表。

    Returns:
        list: 符合 MCP 协议格式的工具定义列表。
    """
    return await list_registered_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """
    MCP 协议处理器：调用指定工具。

    当 MCP 客户端发送 `call_tool` 请求时，此异步函数会被调用。
    它负责执行具体的工具逻辑，并将结果封装成标准的 MCP 响应格式。

    Args:
        name (str): 客户端请求调用的工具名称。
        arguments (dict): 客户端传递的参数字典。

    Returns:
        CallToolResult | str: 
            - 如果类型模块可用，返回封装好的 CallToolResult 对象。
            - 否则，直接返回原始结果字符串（兼容性回退）。
    """
    # 执行具体的工具调用逻辑
    result = await call_registered_tool(name, arguments)
    
    # 检查是否拥有标准的 MCP 响应类型定义
    if TextContent and CallToolResult:
        # 将结果文本封装为 TextContent 对象
        # 再将 TextContent 放入 CallToolResult 的 content 列表中
        return CallToolResult(content=[TextContent(type="text", text=result)])
    
    # 如果缺乏类型定义，直接返回原始结果（通常在测试或极简模式下）
    return result


# ==============================================================================
# 8. 服务器启动入口
# ==============================================================================

async def main():
    """
    服务器主启动协程。

    负责加载应用程序配置，初始化日志，并建立 STDIO 传输通道以开始监听和处理 MCP 消息。
    """
    # 加载配置文件 (config.yml) 和环境变量设置
    Config.load()
    
    # 记录服务器启动日志
    logger.info("CodeMind MCP Server starting...")

    # 选择可用的 STDIO 传输实现。
    # 优先使用标准 SDK 提供的 stdio_server，如果不可用则使用本地实现的 local_stdio_server。
    transport = stdio_server or local_stdio_server
    
    # 进入传输层的异步上下文管理器，获取读取流和写入流
    async with transport() as (read_stream, write_stream):
        # 启动 MCP 应用的主循环，处理来自 read_stream 的请求并将响应写入 write_stream
        # create_initialization_options() 提供服务器的初始化配置信息
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    # ==============================================================================
    # 9. 脚本执行入口
    # ==============================================================================
    
    # 当此文件作为主脚本直接运行时（而非被导入），执行以下代码块。
    # 使用 asyncio.run() 启动主协程 main()，这将阻塞直到服务器停止运行。
    asyncio.run(main())
