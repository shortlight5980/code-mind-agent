"""
RunCommand MCP wrapper.
"""

from __future__ import annotations

from typing import Any

from agent.tools.run_command import RunCommand

from .base import BaseMCPTool


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
        return RunCommand.invoke(arguments)
