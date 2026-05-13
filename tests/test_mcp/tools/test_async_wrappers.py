import asyncio
import sys
import time
import unittest
from unittest.mock import patch

from codemind_mcp.tools.read_file import ReadFileTool
from codemind_mcp.tools.run_command import RunCommandTool
from codemind_mcp.tools.search_code import SearchCodeTool


class AsyncWrapperTests(unittest.TestCase):
    def test_tool_modules_do_not_import_legacy_tool_impl(self):
        self.assertNotIn("codemind_mcp.tool_impl", sys.modules)

    def _assert_call_does_not_block_event_loop(self, tool, arguments, patch_target):
        def blocking_impl(*args, **kwargs):
            time.sleep(0.2)
            return "ok"

        async def run_check():
            with patch(patch_target, side_effect=blocking_impl):
                call_task = asyncio.create_task(tool.call(arguments))
                started = time.perf_counter()
                await asyncio.sleep(0)
                elapsed = time.perf_counter() - started
                result = await call_task
                return elapsed, result

        elapsed, result = asyncio.run(run_check())

        self.assertEqual("ok", result)
        self.assertLess(elapsed, 0.1)

    def test_read_file_call_does_not_block_event_loop(self):
        self._assert_call_does_not_block_event_loop(
            ReadFileTool(),
            {"file_path": "README.md"},
            "codemind_mcp.tools.read_file.read_file_impl",
        )

    def test_search_code_call_does_not_block_event_loop(self):
        self._assert_call_does_not_block_event_loop(
            SearchCodeTool(),
            {"query": "needle"},
            "codemind_mcp.tools.search_code.search_code_impl",
        )

    def test_run_command_call_does_not_block_event_loop(self):
        self._assert_call_does_not_block_event_loop(
            RunCommandTool(),
            {"command": "git status"},
            "codemind_mcp.tools.run_command.run_command_impl",
        )


if __name__ == "__main__":
    unittest.main()
