"""
RunCommand MCP wrapper.
"""

from __future__ import annotations

from typing import Any

from .base import BaseMCPTool
from ..tool_impl import run_command_impl


class RunCommandTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "codemind_run_command"

    @property
    def description(self) -> str:
        return "执行白名单内的只读 shell 命令。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                }
            },
            "required": ["command"],
        }

    async def call(self, arguments: dict[str, Any]) -> str:
        return await self.run_blocking(run_command_impl, command=arguments["command"])
