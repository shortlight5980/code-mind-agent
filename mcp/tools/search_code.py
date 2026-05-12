"""
SearchCode MCP wrapper.
"""

from __future__ import annotations

from typing import Any

from agent.tools.search_code import SearchCode

from mcp.tools.base import BaseMCPTool


class SearchCodeTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_search_code"

    @property
    def description(self) -> str:
        return "在代码库中搜索关键词或正则表达式。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或正则表达式",
                },
                "is_regex": {
                    "type": "boolean",
                    "description": "是否使用正则表达式搜索",
                    "default": False,
                },
                "search_dir": {
                    "type": "string",
                    "description": "搜索目录，相对于仓库根目录",
                    "default": ".",
                },
            },
            "required": ["query"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        return SearchCode.invoke(arguments)

