import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from codemind_mcp.server import call_registered_tool, call_tool, get_tools, list_registered_tools
from codemind_mcp.tools.output_truncation import MAX_TOOL_OUTPUT_CHARS


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

    def test_call_tool_truncates_large_result_at_server_boundary(self):
        large_result = "x" * (MAX_TOOL_OUTPUT_CHARS + 5000)

        with patch("codemind_mcp.server.call_registered_tool", new=AsyncMock(return_value=large_result)):
            result = asyncio.run(call_tool("codemind_index_repo", {}))

        if hasattr(result, "content"):
            text = result.content[0].text
        else:
            text = result

        self.assertIn("[警告] IndexRepo 输出过长，已截断。", text)
        self.assertLess(len(text), MAX_TOOL_OUTPUT_CHARS + 300)


if __name__ == "__main__":
    unittest.main()
