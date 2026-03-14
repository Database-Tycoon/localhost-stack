"""CLI integration tests — verify help text and subcommand registration."""

from __future__ import annotations

import pytest
from tycoon.cli import app


class TestCLIHelp:
    """Verify top-level help and subcommand availability."""

    def test_help_exits_zero(self, cli_runner):
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_expected_commands(self, cli_runner):
        result = cli_runner.invoke(app, ["--help"])
        output = result.stdout
        for cmd in ("check", "ingest", "db", "transform", "setup", "serve", "demo", "version"):
            assert cmd in output, f"Expected command '{cmd}' in help output"

    def test_version_prints_version(self, cli_runner):
        result = cli_runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "tycoon" in result.stdout

    def test_check_help(self, cli_runner):
        result = cli_runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "--verbose" in result.stdout or "--fix" in result.stdout

    def test_ingest_help_lists_subcommands(self, cli_runner):
        result = cli_runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        output = result.stdout
        for sub in ("dot", "mta", "bus-speeds", "all"):
            assert sub in output, f"Expected ingest subcommand '{sub}' in help output"

    def test_transform_help_lists_subcommands(self, cli_runner):
        result = cli_runner.invoke(app, ["transform", "--help"])
        assert result.exit_code == 0
        output = result.stdout
        for sub in ("run", "test", "build", "docs"):
            assert sub in output, f"Expected transform subcommand '{sub}' in help output"

    def test_db_help_lists_subcommands(self, cli_runner):
        result = cli_runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0
        output = result.stdout
        for sub in ("stats", "query", "clean"):
            assert sub in output, f"Expected db subcommand '{sub}' in help output"

    def test_setup_help(self, cli_runner):
        result = cli_runner.invoke(app, ["setup", "--help"])
        assert result.exit_code == 0
        assert "--quick" in result.stdout

    def test_serve_help(self, cli_runner):
        result = cli_runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.stdout

    def test_demo_help(self, cli_runner):
        result = cli_runner.invoke(app, ["demo", "--help"])
        assert result.exit_code == 0
        assert "--skip" in result.stdout or "--only" in result.stdout
