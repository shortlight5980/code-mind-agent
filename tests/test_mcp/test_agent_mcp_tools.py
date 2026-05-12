import unittest
from unittest.mock import Mock

from agent.agent import get_tools


class AgentMCPToolTests(unittest.TestCase):
    def test_get_tools_merges_local_and_mcp_tools(self):
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

        tools = get_tools(client)
        names = [tool.name for tool in tools]
        self.assertIn("RetrieveAndSummarize", names)
        self.assertIn("codemind_read_file", names)

    def test_dynamic_mcp_tool_calls_client(self):
        client = Mock()
        client.list_tools.return_value = [
            {
                "name": "codemind_run_command",
                "description": "执行命令",
                "inputSchema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ]
        client.call_tool.return_value = "remote-result"

        tools = {tool.name: tool for tool in get_tools(client)}
        result = tools["codemind_run_command"].invoke({"command": "git status"})
        self.assertEqual("remote-result", result)
        client.call_tool.assert_called_once_with("codemind_run_command", {"command": "git status"})


if __name__ == "__main__":
    unittest.main()
