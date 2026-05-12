import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mcp.tools.read_file import ReadFileTool


class ReadFileToolTests(unittest.TestCase):
    def test_reads_file_from_configured_repo(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "src" / "main.py"
            target.parent.mkdir()
            target.write_text("print('mcp')\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.blocked_files": [],
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = asyncio.run(ReadFileTool().call({"file_path": "src/main.py"}))

        self.assertIn("print('mcp')", result)
        self.assertIn(str(target), result)

    def test_rejects_sensitive_file(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / ".env"
            target.write_text("SECRET=1\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.blocked_files": None,
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = asyncio.run(ReadFileTool().call({"file_path": ".env"}))

        self.assertIn("禁止访问敏感文件", result)


if __name__ == "__main__":
    unittest.main()

