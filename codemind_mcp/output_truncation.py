"""
普通工具输出截断辅助。

不应用于 RetrieveAndSummarize，以免影响检索总结质量。
"""
from __future__ import annotations


MAX_TOOL_OUTPUT_CHARS = 12000
HEAD_CHARS = 8000
TAIL_CHARS = 3000


def truncate_tool_output(content: str, tool_name: str) -> str:
    """
    对普通工具输出做统一截断，保留开头和结尾，避免上下文过长。

    Args:
        content: 原始输出
        tool_name: 工具名，用于提示

    Returns:
        截断后的输出
    """
    if not isinstance(content, str):
        return content

    if len(content) <= MAX_TOOL_OUTPUT_CHARS:
        return content

    omitted_chars = len(content) - HEAD_CHARS - TAIL_CHARS
    notice = (
        f"\n\n[警告] {tool_name} 输出过长，已截断。"
        f"保留前 {HEAD_CHARS} 字符和后 {TAIL_CHARS} 字符，"
        f"省略约 {max(omitted_chars, 0)} 字符。\n\n"
    )
    return content[:HEAD_CHARS] + notice + content[-TAIL_CHARS:]
