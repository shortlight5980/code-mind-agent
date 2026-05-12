"""
Measure memory deltas for local tools and MCP proxy tool calls.

This benchmark is lightweight and Linux-oriented. It samples RSS in KB via
``resource.getrusage`` and reports peak delta per scenario.
"""

from __future__ import annotations

import argparse
import os
import resource
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.mcp_client import MCPClient
from agent.tools.mcp_common import initialize_mcp_tool_service_manager
from agent.tools.mcp_read_file import MCPReadFile
from agent.tools.mcp_run_command import MCPRunCommand
from agent.tools.mcp_search_code import MCPSearchCode
from agent.tools.read_file import ReadFile
from agent.tools.run_command import RunCommand
from agent.tools.search_code import SearchCode


class _ServiceManagerStub:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client


def _rss_kb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _measure_delta_kb(fn) -> tuple[int, str]:
    before = _rss_kb()
    result = fn()
    after = _rss_kb()
    return max(0, after - before), result.splitlines()[0] if result else ""


def _print_row(label: str, delta_kb: int, preview: str) -> None:
    print(f"{label:<24} delta_rss={delta_kb:>8} KB")
    print(f"  preview: {preview}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark CodeMind tool memory deltas.")
    parser.add_argument("--stdio", action="store_true", help="Also measure real stdio MCP transport.")
    args = parser.parse_args()

    with TemporaryDirectory() as temp_dir:
        repo_root = Path(temp_dir) / "repo"
        repo_root.mkdir()
        sample = repo_root / "src" / "main.py"
        sample.parent.mkdir()
        sample.write_text(
            "needle = 'value'\n"
            "def greet():\n"
            "    return 'hello'\n",
            encoding="utf-8",
        )

        benchmark_config = Path(temp_dir) / "benchmark_config.yml"
        benchmark_config.write_text(
            "\n".join(
                [
                    "repo:",
                    f"  path: \"{repo_root}\"",
                    "agent:",
                    "  allowed_dirs:",
                    "    - \".\"",
                    "  blocked_files: []",
                    "  allowed_commands:",
                    "    - \"git\"",
                    "  command_timeout: 5",
                    "  max_search_results: 50",
                ]
            ),
            encoding="utf-8",
        )

        base_values = {
            "repo.path": str(repo_root),
            "agent.allowed_dirs": ["."],
            "agent.blocked_files": [],
            "agent.max_search_results": 50,
            "agent.allowed_commands": ["git"],
            "agent.command_timeout": 5,
            "mcp.fallback_to_local": True,
            "mcp.call_timeout": 10,
            "mcp.startup_timeout": 15,
        }

        with patch("agent.tools.run_command.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "status"],
                returncode=0,
                stdout="On branch main\n",
                stderr="",
            )

            local_values = dict(base_values, **{"mcp.enabled": False})
            with patch("utils.config.Config.get", side_effect=lambda key, default=None: local_values.get(key, default)):
                print("\n== Memory Delta: Local Tools ==")
                for label, fn in [
                    ("Local ReadFile", lambda: ReadFile.invoke({"file_path": "src/main.py"})),
                    ("Local SearchCode", lambda: SearchCode.invoke({"query": "needle"})),
                    ("Local RunCommand", lambda: RunCommand.invoke({"command": "git status"})),
                ]:
                    delta_kb, preview = _measure_delta_kb(fn)
                    _print_row(label, delta_kb, preview)

            local_mcp_values = dict(base_values, **{"mcp.enabled": True, "mcp.transport": "local"})
            with patch("utils.config.Config.get", side_effect=lambda key, default=None: local_mcp_values.get(key, default)):
                client = MCPClient()
                client.initialize()
                initialize_mcp_tool_service_manager(_ServiceManagerStub(client))
                try:
                    print("\n== Memory Delta: MCP Local Transport ==")
                    for label, fn in [
                        ("MCP(local) ReadFile", lambda: MCPReadFile.invoke({"file_path": "src/main.py"})),
                        ("MCP(local) SearchCode", lambda: MCPSearchCode.invoke({"query": "needle"})),
                        ("MCP(local) RunCommand", lambda: MCPRunCommand.invoke({"command": "git status"})),
                    ]:
                        delta_kb, preview = _measure_delta_kb(fn)
                        _print_row(label, delta_kb, preview)
                finally:
                    client.close()

            if args.stdio:
                stdio_values = dict(
                    base_values,
                    **{
                        "mcp.enabled": True,
                        "mcp.transport": "stdio",
                        "mcp.server_command": [
                            "conda",
                            "run",
                            "--no-capture-output",
                            "-n",
                            "AIP312",
                            "python",
                            str(PROJECT_ROOT / "mcp" / "server.py"),
                        ],
                        "mcp.server_env": {"CODEMIND_CONFIG_PATH": str(benchmark_config)},
                    },
                )
                with patch("utils.config.Config.get", side_effect=lambda key, default=None: stdio_values.get(key, default)):
                    client = MCPClient()
                    client.initialize()
                    initialize_mcp_tool_service_manager(_ServiceManagerStub(client))
                    try:
                        print("\n== Memory Delta: MCP Stdio Transport ==")
                        for label, fn in [
                            ("MCP(stdio) ReadFile", lambda: MCPReadFile.invoke({"file_path": "src/main.py"})),
                            ("MCP(stdio) SearchCode", lambda: MCPSearchCode.invoke({"query": "needle"})),
                            ("MCP(stdio) RunCommand", lambda: MCPRunCommand.invoke({"command": "git status"})),
                        ]:
                            delta_kb, preview = _measure_delta_kb(fn)
                            _print_row(label, delta_kb, preview)
                    finally:
                        client.close()


if __name__ == "__main__":
    main()
