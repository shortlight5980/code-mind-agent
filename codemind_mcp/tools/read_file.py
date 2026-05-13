"""
ReadFile MCP wrapper.
"""

from __future__ import annotations

from typing import Any

from .base import BaseMCPTool
from ..tool_impl import read_file_impl


class ReadFileTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_read_file"

    @property
    def description(self) -> str:
        return "读取指定文件内容，支持按行号范围读取。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（相对于被索引仓库根目录）",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从 1 开始，包含）",
                    "minimum": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（包含）",
                    "minimum": 1,
                },
            },
            "required": ["file_path"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        return await self.run_blocking(
            read_file_impl,
            file_path=arguments["file_path"],
            start_line=arguments.get("start_line"),
            end_line=arguments.get("end_line"),
        )
