import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _install_import_stubs():
    utils_config = types.ModuleType("utils.config")
    utils_logger = types.ModuleType("utils.logger")

    class StubConfig:
        @staticmethod
        def load():
            return None

        @staticmethod
        def get(key, default=None):
            return default

    class StubLogger:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    utils_config.Config = StubConfig
    utils_logger.get_logger = lambda name="codemind": StubLogger()

    stubs = {
        "utils.config": utils_config,
        "utils.logger": utils_logger,
        "scripts.add_by_file_path": types.ModuleType("scripts.add_by_file_path"),
        "scripts.delete_by_file_path": types.ModuleType("scripts.delete_by_file_path"),
    }
    stubs["scripts.add_by_file_path"].add_documents_by_source = lambda *args, **kwargs: 0
    stubs["scripts.delete_by_file_path"].delete_documents_by_source = lambda *args, **kwargs: None
    return stubs


def _load_update_by_git():
    stubs = _install_import_stubs()
    originals = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "update_by_git.py"
        spec = importlib.util.spec_from_file_location("update_by_git_for_tests", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


update_by_git = _load_update_by_git()


class UpdateByGitTests(unittest.TestCase):
    def test_build_git_diff_command_for_supported_modes(self):
        self.assertEqual(
            ["git", "diff", "HEAD~2", "HEAD", "--name-only"],
            update_by_git._build_git_diff_command("commits", commits=2),
        )
        self.assertEqual(
            ["git", "diff", "abc123~1", "abc123", "--name-only"],
            update_by_git._build_git_diff_command("revision", revision="abc123"),
        )
        self.assertEqual(["git", "diff", "--cached", "--name-only"], update_by_git._build_git_diff_command("staged"))
        self.assertEqual(["git", "diff", "--name-only"], update_by_git._build_git_diff_command("working"))

    def test_get_git_changed_files_returns_normalized_absolute_paths(self):
        completed = types.SimpleNamespace(stdout="src/app.py\nREADME.md\n")
        with (
            patch.object(update_by_git, "get_repo_root", return_value="/repo"),
            patch.object(update_by_git.subprocess, "run", return_value=completed) as mocked_run,
        ):
            files = update_by_git.get_git_changed_files(mode="working")

        mocked_run.assert_called_once_with(
            ["git", "diff", "--name-only"],
            cwd="/repo",
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(["/repo/src/app.py", "/repo/README.md"], files)

    def test_update_index_by_git_deletes_and_readds_existing_files(self):
        changed_files = ["/repo/src/app.py", "/repo/docs/removed.md"]

        with (
            patch.object(update_by_git.Config, "load"),
            patch.object(update_by_git, "get_git_changed_files", return_value=changed_files),
            patch.object(update_by_git, "delete_documents_by_source") as mocked_delete,
            patch.object(update_by_git, "add_documents_by_source", return_value=4) as mocked_add,
            patch.object(update_by_git.os.path, "isfile", side_effect=lambda path: path.endswith("app.py")),
        ):
            stats = update_by_git.update_index_by_git(mode="commits", commits=1, persist_dir="/tmp/db")

        self.assertEqual(
            {"mode": "commits", "changed_files": 2, "deleted": 2, "added_chunks": 4, "skipped": 1},
            stats,
        )
        mocked_delete.assert_any_call("/repo/src/app.py", persist_dir="/tmp/db")
        mocked_delete.assert_any_call("/repo/docs/removed.md", persist_dir="/tmp/db")
        mocked_add.assert_called_once_with("/repo/src/app.py", persist_dir="/tmp/db")


if __name__ == "__main__":
    unittest.main()
