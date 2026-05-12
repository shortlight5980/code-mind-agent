import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent.mcp_host import MCPClient, build_langchain_mcp_tools


class MCPProxyEndToEndTests(unittest.TestCase):
    def test_dynamic_mcp_tools_work_end_to_end_with_local_transport(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "src" / "main.py"
            target.parent.mkdir()
            target.write_text("needle = 'value'\nprint('ok')\n", encoding="utf-8")

            values = {
                "mcp.transport": "local",
                "mcp.call_timeout": 5,
                "mcp.startup_timeout": 5,
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.blocked_files": [],
                "agent.max_search_results": 50,
                "agent.allowed_commands": ["git"],
                "agent.command_timeout": 5,
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                client = MCPClient()
                client.initialize()
                try:
                    tools = {tool.name: tool for tool in build_langchain_mcp_tools(client)}
                    read_result = tools["codemind_read_file"].invoke({"file_path": "src/main.py"})
                    search_result = tools["codemind_search_code"].invoke({"query": "needle"})
                    with patch("codemind_mcp.tool_impl.subprocess.run") as mock_run:
                        import subprocess
                        mock_run.return_value = subprocess.CompletedProcess(
                            args=["git", "status"],
                            returncode=0,
                            stdout="On branch main\n",
                            stderr="",
                        )
                        run_result = tools["codemind_run_command"].invoke({"command": "git status"})
                finally:
                    client.close()

        self.assertIn("needle = 'value'", read_result)
        self.assertIn("needle = 'value'", search_result)
        self.assertIn("On branch main", run_result)


if __name__ == "__main__":
    unittest.main()
