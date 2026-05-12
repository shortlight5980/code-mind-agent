import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent.mcp_client import MCPClient


class MCPClientTests(unittest.TestCase):
    def test_local_transport_list_tools_and_call_tool(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "hello.py"
            target.write_text("print('hello')\n", encoding="utf-8")

            values = {
                "mcp.enabled": True,
                "mcp.transport": "local",
                "mcp.call_timeout": 5,
                "mcp.startup_timeout": 5,
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.blocked_files": [],
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                client = MCPClient()
                client.initialize()
                try:
                    tools = client.list_tools()
                    result = client.call_tool("codemind_read_file", {"file_path": "hello.py"})
                finally:
                    client.close()

        names = {tool["name"] for tool in tools}
        self.assertIn("codemind_read_file", names)
        self.assertIn("print('hello')", result)

    def test_health_check_uses_list_tools(self):
        values = {
            "mcp.enabled": True,
            "mcp.transport": "local",
            "mcp.call_timeout": 5,
            "mcp.startup_timeout": 5,
        }

        with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
            client = MCPClient()
            client.initialize()
            try:
                self.assertTrue(client.health_check())
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
