import asyncio
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from codemind_mcp.tools.run_command import RunCommandTool


class RunCommandToolTests(unittest.TestCase):
    def test_executes_whitelisted_command(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_commands": ["git"],
                "agent.command_timeout": 5,
            }
            completed = subprocess.CompletedProcess(
                args=["git", "status"],
                returncode=0,
                stdout="ok\n",
                stderr="",
            )

            with (
                patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)),
                patch("codemind_mcp.tool_impl.subprocess.run", return_value=completed),
            ):
                result = asyncio.run(RunCommandTool().call({"command": "git status"}))

        self.assertIn("标准输出", result)
        self.assertIn("ok", result)

    def test_rejects_blocked_argument(self):
        values = {
            "repo.path": ".",
            "agent.allowed_commands": ["ls"],
            "agent.command_timeout": 5,
        }

        with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
            result = asyncio.run(RunCommandTool().call({"command": "ls -R"}))

        self.assertIn("命令不在白名单内", result)


if __name__ == "__main__":
    unittest.main()
