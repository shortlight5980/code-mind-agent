import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from codemind_mcp.server import call_registered_tool, get_tools, list_registered_tools


class MCPServerTests(unittest.TestCase):
    def test_get_tools_contains_expected_names(self):
        names = {tool.name for tool in get_tools()}
        self.assertEqual(
            names,
            {
                "codemind_read_file",
                "codemind_search_code",
                "codemind_run_command",
                "codemind_index_repo",
                "codemind_add_by_file_path",
                "codemind_delete_by_file_path",
            },
        )

    def test_list_registered_tools_returns_definitions(self):
        definitions = asyncio.run(list_registered_tools())
        self.assertTrue(definitions)
        self.assertTrue(all(hasattr(item, "name") for item in definitions))

    def test_call_registered_tool_dispatches(self):
        tool = get_tools()[0]
        with patch.object(tool, "call", new=AsyncMock(return_value="ok")) as mocked:
            result = asyncio.run(call_registered_tool(tool.name, {"file_path": "README.md"}))

        self.assertEqual("ok", result)
        mocked.assert_awaited_once()

    def test_call_registered_tool_rejects_unknown_tool(self):
        with self.assertRaises(ValueError):
            asyncio.run(call_registered_tool("unknown_tool", {}))


if __name__ == "__main__":
    unittest.main()
