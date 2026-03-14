"""Tests for the `tycoon check` command."""

from __future__ import annotations

from unittest.mock import patch

from tycoon.cli import app


class TestCheckCommand:

    def test_check_runs_without_crash(self, cli_runner):
        """check should run and produce output (may exit 0 or 1 depending on env)."""
        result = cli_runner.invoke(app, ["check"])
        # It should produce output regardless of pass/fail
        assert len(result.stdout) > 0

    def test_check_fix_flag_accepted(self, cli_runner):
        """--fix flag should be accepted and not cause a crash."""
        result = cli_runner.invoke(app, ["check", "--fix"])
        assert len(result.stdout) > 0

    def test_check_verbose_flag_accepted(self, cli_runner):
        """--verbose flag should be accepted and not cause a crash."""
        result = cli_runner.invoke(app, ["check", "--verbose"])
        assert len(result.stdout) > 0

    def test_check_fix_creates_data_dir(self, cli_runner, tmp_config, monkeypatch):
        """check --fix should create the data directory if missing."""
        import shutil

        # Remove the data dir that the fixture created
        if tmp_config.data_dir.exists():
            shutil.rmtree(tmp_config.data_dir)

        # Patch the module-level config singleton used by check.py
        monkeypatch.setattr("tycoon.commands.check.config", tmp_config)

        result = cli_runner.invoke(app, ["check", "--fix"])
        assert tmp_config.data_dir.exists()
