"""
Base class for CodeMind MCP tools.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mcp.types import Tool


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
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema,
        )

    @abstractmethod
    async def call(self, arguments: dict[str, Any]) -> str:
        pass
