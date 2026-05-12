import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from codemind_mcp.tools.output_truncation import MAX_TOOL_OUTPUT_CHARS
from codemind_mcp.tool_impl import read_file_impl, run_command_impl, search_code_impl


class ToolRepoPathTests(unittest.TestCase):
    def test_read_file_uses_configured_repo_path(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "external-repo"
            repo_root.mkdir()
            target = repo_root / "src" / "main.py"
            target.parent.mkdir()
            target.write_text("print('repo path works')\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.blocked_files": [],
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = read_file_impl("src/main.py")

        self.assertIn("repo path works", result)
        self.assertIn(str(target), result)

    def test_search_code_defaults_to_repo_path_instead_of_project_root(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "external-repo"
            repo_root.mkdir()
            (repo_root / "app.py").write_text("needle = 'in repo'\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.max_search_results": 50,
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = search_code_impl("needle")

        self.assertIn("app.py", result)
        self.assertIn("needle = 'in repo'", result)

    def test_run_command_executes_in_configured_repo_path(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "external-repo"
            repo_root.mkdir()

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_commands": ["git"],
                "agent.command_timeout": 5,
            }

            completed = subprocess.CompletedProcess(
                args=["git", "rev-parse", "--show-toplevel"],
                returncode=0,
                stdout=str(repo_root) + "\n",
                stderr="",
            )

            with (
                patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)),
                patch("codemind_mcp.tool_impl.subprocess.run", return_value=completed) as mock_run,
            ):
                result = run_command_impl("git rev-parse --show-toplevel")

        self.assertIn(str(repo_root), result)
        self.assertEqual(str(repo_root), mock_run.call_args.kwargs["cwd"])

    def test_read_file_truncates_large_output(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "external-repo"
            repo_root.mkdir()
            target = repo_root / "large.txt"
            target.write_text(("x" * 200 + "\n") * 200, encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.blocked_files": [],
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = read_file_impl("large.txt")

        self.assertIn("[警告] ReadFile 输出过长，已截断。", result)
        self.assertLess(len(result), MAX_TOOL_OUTPUT_CHARS + 300)

    def test_search_code_truncates_large_output(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "external-repo"
            repo_root.mkdir()
            large_line = "needle " + ("x" * 400)
            for idx in range(60):
                (repo_root / f"file_{idx}.py").write_text(large_line + "\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.max_search_results": 100,
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = search_code_impl("needle")

        self.assertIn("[警告] SearchCode 输出过长，已截断。", result)
        self.assertLess(len(result), MAX_TOOL_OUTPUT_CHARS + 300)

    def test_run_command_truncates_large_output(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "external-repo"
            repo_root.mkdir()

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_commands": ["git"],
                "agent.command_timeout": 5,
            }

            completed = subprocess.CompletedProcess(
                args=["git", "status"],
                returncode=0,
                stdout="x" * (MAX_TOOL_OUTPUT_CHARS + 5000),
                stderr="",
            )

            with (
                patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)),
                patch("codemind_mcp.tool_impl.subprocess.run", return_value=completed),
            ):
                result = run_command_impl("git status")

        self.assertIn("[警告] RunCommand 输出过长，已截断。", result)
        self.assertLess(len(result), MAX_TOOL_OUTPUT_CHARS + 300)


if __name__ == "__main__":
    unittest.main()
