"""
MCP wrapper for full repository indexing.
"""

from __future__ import annotations

from typing import Any

from scripts.index_repo import index_repo

from mcp.tools.base import BaseMCPTool


class IndexRepoTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_index_repo"

    @property
    def description(self) -> str:
        return "重建整个仓库的 Chroma 和 BM25 索引。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "待索引仓库路径；为空时读取 config.yml",
                },
                "persist_dir": {
                    "type": "string",
                    "description": "Chroma 持久化目录；为空时读取 config.yml",
                },
            },
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        repo_path = arguments.get("repo_path")
        persist_dir = arguments.get("persist_dir")
        index_repo(repo_path=repo_path, persist_dir=persist_dir)
        return "仓库索引完成"

