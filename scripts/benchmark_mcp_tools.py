"""
Benchmark local Agent tools against MCP proxy tools.

This script focuses on tool-call latency only. It does not involve LLM calls.
"""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
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


def _measure(label: str, fn: Callable[[], str], iterations: int) -> dict:
    samples = []
    last_result = ""
    for _ in range(iterations):
        start = time.perf_counter()
        last_result = fn()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "label": label,
        "avg_ms": round(statistics.mean(samples), 2),
        "p95_ms": round(max(samples) if len(samples) < 2 else statistics.quantiles(samples, n=20)[18], 2),
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
        "result_preview": last_result.splitlines()[0] if last_result else "",
    }


def _print_results(title: str, rows: list[dict]) -> None:
    print(f"\n== {title} ==")
    for row in rows:
        print(
            f"{row['label']:<24} avg={row['avg_ms']:>7} ms  "
            f"p95={row['p95_ms']:>7} ms  min={row['min_ms']:>7} ms  "
            f"max={row['max_ms']:>7} ms"
        )
        print(f"  preview: {row['result_preview']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark CodeMind local tools vs MCP proxy tools.")
    parser.add_argument("--iterations", type=int, default=5, help="Runs per scenario")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Also benchmark real stdio MCP transport. Requires the AIP312 environment command to work.",
    )
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
                    "mcp:",
                    "  enabled: true",
                    "  transport: \"stdio\"",
                    "  fallback_to_local: true",
                    "  call_timeout: 10",
                    "  startup_timeout: 15",
                ]
            ),
            encoding="utf-8",
        )

        with patch("agent.tools.run_command.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "status"],
                returncode=0,
                stdout="On branch main\n",
                stderr="",
            )

            local_values = dict(base_values, **{"mcp.enabled": False})
            with patch("utils.config.Config.get", side_effect=lambda key, default=None: local_values.get(key, default)):
                local_rows = [
                    _measure("Local ReadFile", lambda: ReadFile.invoke({"file_path": "src/main.py"}), args.iterations),
                    _measure("Local SearchCode", lambda: SearchCode.invoke({"query": "needle"}), args.iterations),
                    _measure("Local RunCommand", lambda: RunCommand.invoke({"command": "git status"}), args.iterations),
                ]

            local_mcp_values = dict(base_values, **{"mcp.enabled": True, "mcp.transport": "local"})
            with patch("utils.config.Config.get", side_effect=lambda key, default=None: local_mcp_values.get(key, default)):
                local_client = MCPClient()
                local_client.initialize()
                initialize_mcp_tool_service_manager(_ServiceManagerStub(local_client))
                try:
                    mcp_local_rows = [
                        _measure("MCP(local) ReadFile", lambda: MCPReadFile.invoke({"file_path": "src/main.py"}), args.iterations),
                        _measure("MCP(local) SearchCode", lambda: MCPSearchCode.invoke({"query": "needle"}), args.iterations),
                        _measure("MCP(local) RunCommand", lambda: MCPRunCommand.invoke({"command": "git status"}), args.iterations),
                    ]
                finally:
                    local_client.close()

            _print_results("Benchmark Summary", local_rows + mcp_local_rows)

            if args.stdio:
                stdio_server_command = [
                    "conda",
                    "run",
                    "--no-capture-output",
                    "-n",
                    "AIP312",
                    "python",
                    str(PROJECT_ROOT / "mcp" / "server.py"),
                ]
                stdio_values = dict(
                    base_values,
                    **{
                        "mcp.enabled": True,
                        "mcp.transport": "stdio",
                        "mcp.server_command": stdio_server_command,
                        "mcp.server_env": {"CODEMIND_CONFIG_PATH": str(benchmark_config)},
                    },
                )
                with patch("utils.config.Config.get", side_effect=lambda key, default=None: stdio_values.get(key, default)):
                    stdio_client = MCPClient()
                    stdio_client.initialize()
                    initialize_mcp_tool_service_manager(_ServiceManagerStub(stdio_client))
                    try:
                        stdio_rows = [
                            _measure("MCP(stdio) ReadFile", lambda: MCPReadFile.invoke({"file_path": "src/main.py"}), args.iterations),
                            _measure("MCP(stdio) SearchCode", lambda: MCPSearchCode.invoke({"query": "needle"}), args.iterations),
                            _measure("MCP(stdio) RunCommand", lambda: MCPRunCommand.invoke({"command": "git status"}), args.iterations),
                        ]
                    finally:
                        stdio_client.close()
                _print_results("Stdio Transport", stdio_rows)


if __name__ == "__main__":
    main()
