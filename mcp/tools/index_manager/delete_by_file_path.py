"""
MCP wrapper for index deletion by source path.
"""

from __future__ import annotations

from typing import Any

from scripts.delete_by_file_path import delete_documents_by_source

from mcp.tools.base import BaseMCPTool


class DeleteByFilePathTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_delete_by_file_path"

    @property
    def description(self) -> str:
        return "从索引中删除指定文件或目录对应的文档。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "待删除的文件路径或目录路径",
                }
            },
            "required": ["source_path"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        source_path = arguments["source_path"]
        delete_documents_by_source(source_path)
        return f"索引删除完成: {source_path}"

