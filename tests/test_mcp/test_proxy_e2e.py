import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent.mcp_client import MCPClient
from agent.tools.mcp_common import initialize_mcp_tool_service_manager
from agent.tools.mcp_read_file import MCPReadFile
from agent.tools.mcp_run_command import MCPRunCommand
from agent.tools.mcp_search_code import MCPSearchCode


class _ServiceManagerStub:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client


class MCPProxyEndToEndTests(unittest.TestCase):
    def test_proxy_tools_work_end_to_end_with_local_transport(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "src" / "main.py"
            target.parent.mkdir()
            target.write_text("needle = 'value'\nprint('ok')\n", encoding="utf-8")

            values = {
                "mcp.enabled": True,
                "mcp.transport": "local",
                "mcp.call_timeout": 5,
                "mcp.startup_timeout": 5,
                "mcp.fallback_to_local": True,
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
                initialize_mcp_tool_service_manager(_ServiceManagerStub(client))
                try:
                    read_result = MCPReadFile.invoke({"file_path": "src/main.py"})
                    search_result = MCPSearchCode.invoke({"query": "needle"})
                    with patch("agent.tools.run_command.subprocess.run") as mock_run:
                        import subprocess
                        mock_run.return_value = subprocess.CompletedProcess(
                            args=["git", "status"],
                            returncode=0,
                            stdout="On branch main\n",
                            stderr="",
                        )
                        run_result = MCPRunCommand.invoke({"command": "git status"})
                finally:
                    client.close()

        self.assertIn("needle = 'value'", read_result)
        self.assertIn("needle = 'value'", search_result)
        self.assertIn("On branch main", run_result)


if __name__ == "__main__":
    unittest.main()
