import asyncio
import unittest
from unittest.mock import patch

from codemind_mcp.tools.index_manager import AddByFilePathTool, DeleteByFilePathTool, IndexRepoTool, UpdateByGitTool


class IndexManagerToolTests(unittest.TestCase):
    def test_index_repo_tool_calls_script_function(self):
        with patch("codemind_mcp.tools.index_manager.index_repo.index_repo") as mocked:
            result = asyncio.run(IndexRepoTool().call({"repo_path": "/tmp/repo", "persist_dir": "/tmp/db"}))

        mocked.assert_called_once_with(repo_path="/tmp/repo", persist_dir="/tmp/db")
        self.assertEqual("仓库索引完成", result)

    def test_add_by_file_path_tool_reports_added_count(self):
        with patch("codemind_mcp.tools.index_manager.add_by_file_path.add_documents_by_source", return_value=7) as mocked:
            result = asyncio.run(AddByFilePathTool().call({"source_path": "/tmp/repo/file.py"}))

        mocked.assert_called_once_with(source_path="/tmp/repo/file.py", persist_dir=None)
        self.assertIn("新增分块数: 7", result)

    def test_delete_by_file_path_tool_calls_script_function(self):
        with patch("codemind_mcp.tools.index_manager.delete_by_file_path.delete_documents_by_source") as mocked:
            result = asyncio.run(DeleteByFilePathTool().call({"source_path": "/tmp/repo/file.py"}))

        mocked.assert_called_once_with("/tmp/repo/file.py")
        self.assertIn("/tmp/repo/file.py", result)

    def test_update_by_git_tool_calls_script_function(self):
        with patch(
            "codemind_mcp.tools.index_manager.update_by_git.update_index_by_git",
            return_value={"mode": "commits", "changed_files": 2, "deleted": 2, "added_chunks": 5, "skipped": 0},
        ) as mocked:
            result = asyncio.run(
                UpdateByGitTool().call({"mode": "commits", "commits": 3, "persist_dir": "/tmp/db"})
            )

        mocked.assert_called_once_with(mode="commits", commits=3, revision=None, persist_dir="/tmp/db")
        self.assertIn("changed_files=2", result)


if __name__ == "__main__":
    unittest.main()
