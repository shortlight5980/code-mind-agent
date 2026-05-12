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

from agent.mcp_host import MCPHostClient, build_langchain_mcp_tools
from codemind_mcp.tool_impl import read_file_impl, run_command_impl, search_code_impl


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
            "mcp.call_timeout": 10,
            "mcp.startup_timeout": 15,
        }

        with patch("codemind_mcp.tool_impl.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "status"],
                returncode=0,
                stdout="On branch main\n",
                stderr="",
            )

            local_values = dict(base_values)
            with patch("utils.config.Config.get", side_effect=lambda key, default=None: local_values.get(key, default)):
                print("\n== Memory Delta: Core Implementations ==")
                for label, fn in [
                    ("Core ReadFile", lambda: read_file_impl("src/main.py")),
                    ("Core SearchCode", lambda: search_code_impl("needle")),
                    ("Core RunCommand", lambda: run_command_impl("git status")),
                ]:
                    delta_kb, preview = _measure_delta_kb(fn)
                    _print_row(label, delta_kb, preview)

            local_mcp_values = dict(base_values, **{"mcp.transport": "local"})
            with patch("utils.config.Config.get", side_effect=lambda key, default=None: local_mcp_values.get(key, default)):
                client = MCPHostClient()
                client.initialize()
                try:
                    mcp_tools = {tool.name: tool for tool in build_langchain_mcp_tools(client)}
                    print("\n== Memory Delta: MCP Local Transport ==")
                    for label, fn in [
                        ("MCP(local) ReadFile", lambda: mcp_tools["codemind_read_file"].invoke({"file_path": "src/main.py"})),
                        ("MCP(local) SearchCode", lambda: mcp_tools["codemind_search_code"].invoke({"query": "needle"})),
                        ("MCP(local) RunCommand", lambda: mcp_tools["codemind_run_command"].invoke({"command": "git status"})),
                    ]:
                        delta_kb, preview = _measure_delta_kb(fn)
                        _print_row(label, delta_kb, preview)
                finally:
                    client.close()

            if args.stdio:
                stdio_values = dict(
                    base_values,
                    **{
                        "mcp.transport": "stdio",
                        "mcp.server_command": [
                            "conda",
                            "run",
                            "--no-capture-output",
                            "-n",
                            "AIP312",
                            "python",
                            str(PROJECT_ROOT / "codemind_mcp" / "server.py"),
                        ],
                        "mcp.server_env": {"CODEMIND_CONFIG_PATH": str(benchmark_config)},
                    },
                )
                with patch("utils.config.Config.get", side_effect=lambda key, default=None: stdio_values.get(key, default)):
                    client = MCPHostClient()
                    client.initialize()
                    try:
                        mcp_tools = {tool.name: tool for tool in build_langchain_mcp_tools(client)}
                        print("\n== Memory Delta: MCP Stdio Transport ==")
                        for label, fn in [
                            ("MCP(stdio) ReadFile", lambda: mcp_tools["codemind_read_file"].invoke({"file_path": "src/main.py"})),
                            ("MCP(stdio) SearchCode", lambda: mcp_tools["codemind_search_code"].invoke({"query": "needle"})),
                            ("MCP(stdio) RunCommand", lambda: mcp_tools["codemind_run_command"].invoke({"command": "git status"})),
                        ]:
                            delta_kb, preview = _measure_delta_kb(fn)
                            _print_row(label, delta_kb, preview)
                    finally:
                        client.close()


if __name__ == "__main__":
    main()
