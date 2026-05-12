import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from agent.tools import get_agent_toolset
from agent.tools.mcp_common import initialize_mcp_tool_service_manager
from agent.tools.mcp_read_file import MCPReadFile
from agent.tools.mcp_run_command import MCPRunCommand
from agent.tools.mcp_search_code import MCPSearchCode


class _ServiceManagerStub:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client


class AgentMCPToolTests(unittest.TestCase):
    def test_get_agent_toolset_uses_mcp_tools_when_enabled(self):
        with patch("utils.config.Config.get", side_effect=lambda key, default=None: True if key == "mcp.enabled" else default):
            tools = get_agent_toolset()

        names = [tool.name for tool in tools]
        self.assertEqual(names[:3], ["MCPReadFile", "MCPSearchCode", "MCPRunCommand"])

    def test_mcp_read_file_calls_client(self):
        client = Mock()
        client.call_tool.return_value = "remote-result"
        initialize_mcp_tool_service_manager(_ServiceManagerStub(client))

        result = MCPReadFile.invoke({"file_path": "README.md"})

        self.assertEqual("remote-result", result)
        client.call_tool.assert_called_once_with("codemind_read_file", {"file_path": "README.md"})

    def test_mcp_search_code_falls_back_to_local(self):
        client = Mock()
        client.call_tool.side_effect = RuntimeError("boom")
        initialize_mcp_tool_service_manager(_ServiceManagerStub(client))

        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "app.py"
            target.write_text("needle = 1\n", encoding="utf-8")

            values = {
                "mcp.fallback_to_local": True,
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.max_search_results": 50,
            }
            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = MCPSearchCode.invoke({"query": "needle"})

        self.assertIn("needle = 1", result)

    def test_mcp_run_command_returns_error_without_fallback(self):
        client = Mock()
        client.call_tool.side_effect = RuntimeError("boom")
        initialize_mcp_tool_service_manager(_ServiceManagerStub(client))

        values = {
            "mcp.fallback_to_local": False,
        }
        with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
            result = MCPRunCommand.invoke({"command": "git status"})

        self.assertIn("MCP RunCommand 调用失败", result)


if __name__ == "__main__":
    unittest.main()
