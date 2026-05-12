"""
Base class for CodeMind MCP tools.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..sdk import ToolDefinition, load_sdk_modules


class BaseMCPTool(ABC):
    """Common interface for local MCP tool wrappers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        pass

    def get_definition(self):
        _, _, sdk_tool_type = load_sdk_modules()
        if sdk_tool_type is not None:
            return sdk_tool_type(
                name=self.name,
                description=self.description,
                inputSchema=self.input_schema,
            )

        return ToolDefinition(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema,
        )

    @abstractmethod
    async def call(self, arguments: dict[str, Any]) -> str:
        pass
