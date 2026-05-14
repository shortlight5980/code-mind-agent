import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from codemind_mcp.sandbox.sandboxed_tools import (
    SandboxedReadFileTool,
    SandboxedRunCommandTool,
    SandboxedSearchCodeTool,
)
from codemind_mcp.sandbox.tool_executor import SandboxedToolExecutor


class _FakeSandbox:
    def __init__(self):
        self.files: dict[str, str] = {}
        self.commands: list[tuple[str, int, str | None]] = []

    async def upload_file(self, local_path: str, remote_path: str) -> None:
        self.files[remote_path] = Path(local_path).read_text(encoding="utf-8")

    async def read_file(self, path: str, start_line=None, end_line=None) -> str:
        content = self.files[path]
        if start_line is None and end_line is None:
            return content
        lines = content.splitlines(keepends=True)
        start_idx = 0 if start_line is None else max(0, start_line - 1)
        end_idx = len(lines) if end_line is None else min(len(lines), end_line)
        return "".join(lines[start_idx:end_idx])

    async def run_command(self, command: str, timeout: int = 30, cwd: str | None = None) -> dict:
        self.commands.append((command, timeout, cwd))
        return {"stdout": "sandbox-ok\n", "stderr": "", "returncode": 0}


class _FakeE2BSandbox:
    instances: list["_FakeE2BSandbox"] = []

    def __init__(self, api_key=None, template=None, timeout=30):
        self.inner = _FakeSandbox()
        self.api_key = api_key
        self.template = template
        self.timeout = timeout
        _FakeE2BSandbox.instances.append(self)

    async def __aenter__(self):
        return self.inner

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class SandboxedExecutorTests(unittest.TestCase):
    def test_executor_reads_searches_and_runs_in_sandbox(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "src" / "main.py"
            target.parent.mkdir()
            target.write_text("needle = 'value'\nprint('ok')\n", encoding="utf-8")

            values = {
                "agent.blocked_files": [],
                "agent.max_search_results": 50,
                "agent.allowed_commands": ["git"],
                "e2b.repo_sync_enabled": True,
            }
            sandbox = _FakeSandbox()
            executor = SandboxedToolExecutor(
                sandbox=sandbox,
                repo_path=str(repo_root),
                allowed_dirs=[str(repo_root)],
            )

            with patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)):
                read_result = asyncio.run(executor.execute_read_file("src/main.py", 1, 2))
                search_result = asyncio.run(executor.execute_search_code("needle"))
                run_result = asyncio.run(executor.execute_run_command("git status", timeout=5))

        self.assertIn("needle = 'value'", read_result)
        self.assertIn("文件 src/main.py", search_result)
        self.assertIn("sandbox-ok", run_result)
        self.assertEqual(("git status", 5, "/workspace/repo"), sandbox.commands[0])


class SandboxedToolWrapperTests(unittest.TestCase):
    def setUp(self):
        _FakeE2BSandbox.instances.clear()

    def test_sandboxed_read_file_tool_uses_e2b_wrapper(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            target = repo_root / "hello.py"
            target.write_text("print('sandbox')\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": [str(repo_root)],
                "agent.blocked_files": [],
                "e2b.api_key": "test-key",
                "e2b.template": "base",
                "e2b.timeout": 30,
                "e2b.workspace_root": "/workspace",
            }

            with (
                patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)),
                patch("codemind_mcp.sandbox.sandboxed_tools.E2BSandbox", _FakeE2BSandbox),
            ):
                result = asyncio.run(SandboxedReadFileTool().call({"file_path": "hello.py"}))

        self.assertIn("print('sandbox')", result)
        self.assertEqual("test-key", _FakeE2BSandbox.instances[0].api_key)

    def test_sandboxed_search_and_run_tools_use_same_contract(self):
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            (repo_root / "app.py").write_text("needle = 1\n", encoding="utf-8")

            values = {
                "repo.path": str(repo_root),
                "agent.allowed_dirs": [str(repo_root)],
                "agent.blocked_files": [],
                "agent.max_search_results": 50,
                "agent.allowed_commands": ["git"],
                "agent.command_timeout": 5,
                "e2b.api_key": "test-key",
                "e2b.template": "base",
                "e2b.timeout": 30,
                "e2b.workspace_root": "/workspace",
                "e2b.repo_sync_enabled": True,
            }

            with (
                patch("utils.config.Config.get", side_effect=lambda key, default=None: values.get(key, default)),
                patch("codemind_mcp.sandbox.sandboxed_tools.E2BSandbox", _FakeE2BSandbox),
            ):
                search_result = asyncio.run(SandboxedSearchCodeTool().call({"query": "needle"}))
                run_result = asyncio.run(SandboxedRunCommandTool().call({"command": "git status"}))

        self.assertIn("needle = 1", search_result)
        self.assertIn("sandbox-ok", run_result)


if __name__ == "__main__":
    unittest.main()
