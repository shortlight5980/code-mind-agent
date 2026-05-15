"""
MCP wrapper for updating index by Git changes.
"""

from __future__ import annotations

from typing import Any

from scripts.update_by_git import update_index_by_git

from ..base import BaseMCPTool


class UpdateByGitTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_update_by_git"

    @property
    def description(self) -> str:
        return "根据 Git 提交、修订号或工作区变更增量更新索引。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["commits", "revision", "staged", "working"],
                    "description": "Git 变更来源模式，默认 commits",
                },
                "commits": {
                    "type": "integer",
                    "description": "mode=commits 时使用的最近提交数，默认 1",
                },
                "revision": {
                    "type": "string",
                    "description": "mode=revision 时使用的提交修订号",
                },
                "persist_dir": {
                    "type": "string",
                    "description": "Chroma 持久化目录；为空时读取 config.yml",
                },
            },
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        mode = arguments.get("mode", "commits")
        commits = arguments.get("commits", 1)
        revision = arguments.get("revision")
        persist_dir = arguments.get("persist_dir")
        stats = await self.run_blocking(
            update_index_by_git,
            mode=mode,
            commits=commits,
            revision=revision,
            persist_dir=persist_dir,
        )
        return (
            "Git 索引更新完成: "
            f"mode={stats['mode']}, changed_files={stats['changed_files']}, "
            f"deleted={stats['deleted']}, added_chunks={stats['added_chunks']}, "
            f"skipped={stats['skipped']}"
        )
