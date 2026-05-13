"""
MCP wrapper for incremental index additions.
"""

from __future__ import annotations

from typing import Any

from scripts.add_by_file_path import add_documents_by_source

from ..base import BaseMCPTool


class AddByFilePathTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_add_by_file_path"

    @property
    def description(self) -> str:
        return "向索引中增量添加指定文件或目录。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "待添加到索引的文件路径或目录路径",
                },
                "persist_dir": {
                    "type": "string",
                    "description": "Chroma 持久化目录；为空时读取 config.yml",
                },
            },
            "required": ["source_path"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        source_path = arguments["source_path"]
        persist_dir = arguments.get("persist_dir")
        count = await self.run_blocking(
            add_documents_by_source,
            source_path=source_path,
            persist_dir=persist_dir,
        )
        return f"索引追加完成，新增分块数: {count}"
