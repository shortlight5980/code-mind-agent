import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from agent.mcp_host import MCPHostClient, build_langchain_mcp_tools


class MCPClientTests(unittest.TestCase):
    def test_local_transport_list_tools_and_call_tool(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "hello.py"
            target.write_text("print('hello')\n", encoding="utf-8")

            values = {
                "mcp.transport": "local",
                "mcp.call_timeout": 5,
                "mcp.startup_timeout": 5,
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.blocked_files": [],
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                client = MCPHostClient()
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
            "mcp.transport": "local",
            "mcp.call_timeout": 5,
            "mcp.startup_timeout": 5,
        }

        with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
            client = MCPHostClient()
            client.initialize()
            try:
                self.assertTrue(client.health_check())
            finally:
                client.close()

    def test_build_langchain_mcp_tools_creates_callable_tools(self):
        client = Mock()
        client.list_tools.return_value = [
            {
                "name": "codemind_read_file",
                "description": "读取文件",
                "inputSchema": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string"}},
                    "required": ["file_path"],
                },
            }
        ]
        client.call_tool.return_value = "ok"

        tools = build_langchain_mcp_tools(client)
        result = tools[0].invoke({"file_path": "README.md"})

        self.assertEqual("ok", result)
        client.call_tool.assert_called_once_with("codemind_read_file", {"file_path": "README.md"})


if __name__ == "__main__":
    unittest.main()
