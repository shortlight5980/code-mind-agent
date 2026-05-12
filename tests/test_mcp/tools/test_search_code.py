import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mcp.tools.search_code import SearchCodeTool


class SearchCodeToolTests(unittest.TestCase):
    def test_searches_keyword_in_repo(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            (repo_root / "app.py").write_text("needle = 'found'\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": ["."],
                "agent.max_search_results": 50,
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = asyncio.run(SearchCodeTool().call({"query": "needle"}))

        self.assertIn("app.py", result)
        self.assertIn("needle = 'found'", result)

    def test_rejects_search_dir_outside_allowlist(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            outside_dir = Path(temp_dir) / "outside"
            outside_dir.mkdir()

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": [str(repo_root / "safe")],
                "agent.max_search_results": 50,
            }

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                result = asyncio.run(
                    SearchCodeTool().call({"query": "needle", "search_dir": str(outside_dir)})
                )

        self.assertIn("搜索目录不在允许的白名单内", result)


if __name__ == "__main__":
    unittest.main()
