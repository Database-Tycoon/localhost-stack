"""Tests for tycoon ai fix — agentic dbt test fix loop."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from tycoon.ai.client import LMStudioStatus, ModelInfo
from tycoon.ai.fix_loop import (
    _backup_and_write,
    _parse_failure_models,
    _restore_backups,
    run_fix_loop,
)
from tycoon.cli import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASSING_RESULT = MagicMock(returncode=0, stdout="1 passed, 0 failed", stderr="")
_FAILING_RESULT = MagicMock(
    returncode=1,
    stdout=(
        "Running with dbt=1.8.0\n"
        "Failure in test not_null_trips_trip_id "
        "(models/staging/stg_trips.sql)\n"
        "  Got 5 results, configured to fail if != 0\n"
        "Failure in test not_null_trips_fare_amount "
        "(models/marts/fct_trips.sql)\n"
    ),
    stderr="",
)

_AI_PROPOSAL_RESPONSE = """\
Here are the fixes:

```models/staging/stg_trips.sql
SELECT trip_id, fare_amount FROM raw.trips WHERE trip_id IS NOT NULL
```

```models/marts/fct_trips.sql
SELECT trip_id, fare_amount FROM {{ ref('stg_trips') }}
```
"""


def _ready_status() -> LMStudioStatus:
    return LMStudioStatus(
        running=True,
        models=[ModelInfo(id="test-model", state="loaded")],
    )


# ---------------------------------------------------------------------------
# _parse_failure_models
# ---------------------------------------------------------------------------


class TestParseFailureModels:
    def test_extracts_paths_from_failure_lines(self, tmp_path):
        output = (
            "Failure in test not_null_trips_trip_id (models/staging/stg_trips.sql)\n"
            "Failure in test not_null_trips_fare (models/marts/fct_trips.sql)\n"
        )
        paths = _parse_failure_models(output, tmp_path)
        assert len(paths) == 2
        assert paths[0] == tmp_path / "models/staging/stg_trips.sql"
        assert paths[1] == tmp_path / "models/marts/fct_trips.sql"

    def test_deduplicates_same_model(self, tmp_path):
        output = (
            "Failure in test t1 (models/staging/stg_trips.sql)\n"
            "Failure in test t2 (models/staging/stg_trips.sql)\n"
        )
        paths = _parse_failure_models(output, tmp_path)
        assert len(paths) == 1

    def test_returns_empty_for_clean_output(self, tmp_path):
        output = "All 10 tests passed.\n"
        paths = _parse_failure_models(output, tmp_path)
        assert paths == []

    def test_handles_paths_with_subdirectories(self, tmp_path):
        output = "Error in models/staging/nyc/stg_citibike_trips.sql\n"
        paths = _parse_failure_models(output, tmp_path)
        assert len(paths) == 1
        assert paths[0] == tmp_path / "models/staging/nyc/stg_citibike_trips.sql"

    def test_preserves_first_seen_order(self, tmp_path):
        output = (
            "models/staging/a.sql\n"
            "models/marts/b.sql\n"
            "models/staging/a.sql\n"
            "models/marts/c.sql\n"
        )
        paths = _parse_failure_models(output, tmp_path)
        names = [p.name for p in paths]
        assert names == ["a.sql", "b.sql", "c.sql"]


# ---------------------------------------------------------------------------
# _backup_and_write
# ---------------------------------------------------------------------------


class TestBackupAndWrite:
    def test_creates_backup_of_existing_file(self, tmp_path):
        target = tmp_path / "model.sql"
        target.write_text("original content")

        _backup_and_write(target, "new content")

        bak = target.with_suffix(".sql.bak")
        assert bak.exists()
        assert bak.read_text() == "original content"
        assert target.read_text() == "new content"

    def test_writes_new_content_when_no_existing_file(self, tmp_path):
        target = tmp_path / "new_model.sql"
        assert not target.exists()

        _backup_and_write(target, "brand new content")

        assert target.read_text() == "brand new content"
        assert not target.with_suffix(".sql.bak").exists()

    def test_creates_parent_directories(self, tmp_path):
        target = tmp_path / "models" / "staging" / "stg_trips.sql"

        _backup_and_write(target, "SELECT 1")

        assert target.exists()
        assert target.read_text() == "SELECT 1"

    def test_overwrites_existing_backup(self, tmp_path):
        target = tmp_path / "model.sql"
        target.write_text("second version")
        bak = target.with_suffix(".sql.bak")
        bak.write_text("first version")

        _backup_and_write(target, "third version")

        # The backup reflects the state just before this write
        assert bak.read_text() == "second version"
        assert target.read_text() == "third version"


# ---------------------------------------------------------------------------
# _restore_backups
# ---------------------------------------------------------------------------


class TestRestoreBackups:
    def test_restores_file_from_backup(self, tmp_path):
        target = tmp_path / "model.sql"
        target.write_text("broken content")
        bak = target.with_suffix(".sql.bak")
        bak.write_text("original content")

        _restore_backups([target])

        assert target.read_text() == "original content"
        assert not bak.exists()

    def test_skips_files_without_backup(self, tmp_path):
        target = tmp_path / "model.sql"
        target.write_text("current content")

        # Should not raise even with no .bak file
        _restore_backups([target])

        assert target.read_text() == "current content"

    def test_restores_multiple_files(self, tmp_path):
        files = []
        for name in ("a.sql", "b.sql", "c.sql"):
            f = tmp_path / name
            f.write_text(f"broken {name}")
            f.with_suffix(".sql.bak").write_text(f"original {name}")
            files.append(f)

        _restore_backups(files)

        for f in files:
            assert f.read_text() == f"original {f.name}"
            assert not f.with_suffix(".sql.bak").exists()

    def test_handles_empty_list(self, tmp_path):
        # Should not raise
        _restore_backups([])


# ---------------------------------------------------------------------------
# run_fix_loop
# ---------------------------------------------------------------------------


class TestRunFixLoop:
    def test_returns_true_immediately_when_tests_pass(self, tmp_path):
        with patch("tycoon.ai.fix_loop.subprocess.run", return_value=_PASSING_RESULT):
            result = run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
            )
        assert result is True

    def test_calls_ai_and_applies_fixes_on_failure(self, tmp_path):
        # First call fails, second call passes after the fix
        failing = MagicMock(
            returncode=1,
            stdout="Failure in test t (models/staging/stg_trips.sql)\n",
            stderr="",
        )
        passing = MagicMock(returncode=0, stdout="", stderr="")

        # Create the model file so the loop can read it
        model_file = tmp_path / "models" / "staging" / "stg_trips.sql"
        model_file.parent.mkdir(parents=True)
        model_file.write_text("SELECT * FROM raw.trips")

        with (
            patch(
                "tycoon.ai.fix_loop.subprocess.run",
                side_effect=[failing, passing],
            ),
            patch(
                "tycoon.ai.fix_loop.chat",
                return_value=_AI_PROPOSAL_RESPONSE,
            ) as mock_chat,
        ):
            result = run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
                max_attempts=3,
            )

        assert result is True
        mock_chat.assert_called_once()
        # The proposed file should have been written
        assert model_file.read_text() == (
            "SELECT trip_id, fare_amount FROM raw.trips WHERE trip_id IS NOT NULL\n"
        )

    def test_restores_backups_after_max_attempts(self, tmp_path):
        model_file = tmp_path / "models" / "staging" / "stg_trips.sql"
        model_file.parent.mkdir(parents=True)
        original_content = "SELECT * FROM raw.trips"
        model_file.write_text(original_content)

        always_failing = MagicMock(
            returncode=1,
            stdout="Failure in test t (models/staging/stg_trips.sql)\n",
            stderr="",
        )

        with (
            patch("tycoon.ai.fix_loop.subprocess.run", return_value=always_failing),
            patch(
                "tycoon.ai.fix_loop.chat",
                return_value=_AI_PROPOSAL_RESPONSE,
            ),
        ):
            result = run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
                max_attempts=2,
            )

        assert result is False
        # Backup should have been restored to original content
        assert model_file.read_text() == original_content

    def test_passes_select_to_dbt_command(self, tmp_path):
        with patch(
            "tycoon.ai.fix_loop.subprocess.run", return_value=_PASSING_RESULT
        ) as mock_run:
            run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
                select="staging",
            )
        cmd = mock_run.call_args[0][0]
        assert "--select" in cmd
        assert "staging" in cmd

    def test_passes_target_to_dbt_command(self, tmp_path):
        with patch(
            "tycoon.ai.fix_loop.subprocess.run", return_value=_PASSING_RESULT
        ) as mock_run:
            run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
                target="prod",
            )
        cmd = mock_run.call_args[0][0]
        assert "--target" in cmd
        assert "prod" in cmd

    def test_returns_false_and_restores_when_ai_raises(self, tmp_path):
        model_file = tmp_path / "models" / "stg.sql"
        model_file.parent.mkdir(parents=True)
        model_file.write_text("original")

        failing = MagicMock(
            returncode=1,
            stdout="Failure in test t (models/stg.sql)\n",
            stderr="",
        )

        with (
            patch("tycoon.ai.fix_loop.subprocess.run", return_value=failing),
            patch("tycoon.ai.fix_loop.chat", side_effect=Exception("timeout")),
        ):
            result = run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
                max_attempts=3,
            )

        assert result is False

    def test_returns_false_when_ai_proposes_nothing(self, tmp_path):
        failing = MagicMock(
            returncode=1,
            stdout="Failure in test t (models/stg.sql)\n",
            stderr="",
        )

        with (
            patch("tycoon.ai.fix_loop.subprocess.run", return_value=failing),
            patch("tycoon.ai.fix_loop.chat", return_value="I cannot fix this."),
        ):
            result = run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
                max_attempts=3,
            )

        assert result is False

    def test_passes_model_to_chat(self, tmp_path):
        failing = MagicMock(
            returncode=1,
            stdout="Failure in test t (models/stg.sql)\n",
            stderr="",
        )
        passing = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch(
                "tycoon.ai.fix_loop.subprocess.run",
                side_effect=[failing, passing],
            ),
            patch(
                "tycoon.ai.fix_loop.chat",
                return_value="```models/stg.sql\nSELECT 1\n```",
            ) as mock_chat,
        ):
            run_fix_loop(
                dbt_dir=tmp_path,
                project_root=tmp_path,
                system_prompt="sys",
                model="my-model",
            )

        assert mock_chat.call_args[1]["model"] == "my-model"


# ---------------------------------------------------------------------------
# fix CLI command
# ---------------------------------------------------------------------------


class TestFixCommand:
    def test_fix_help(self, cli_runner):
        result = cli_runner.invoke(app, ["ai", "fix", "--help"])
        assert result.exit_code == 0
        assert "--max-attempts" in result.stdout
        assert "--model" in result.stdout
        assert "--target" in result.stdout
        assert "--select" in result.stdout

    def test_fix_exits_1_when_server_down(self, cli_runner):
        with patch(
            "tycoon.commands.ai.get_status",
            return_value=LMStudioStatus(running=False),
        ):
            result = cli_runner.invoke(app, ["ai", "fix"])
        assert result.exit_code == 1

    def test_fix_exits_1_when_no_model_loaded(self, cli_runner):
        with patch(
            "tycoon.commands.ai.get_status",
            return_value=LMStudioStatus(
                running=True,
                models=[ModelInfo(id="test", state="not-loaded")],
            ),
        ):
            result = cli_runner.invoke(app, ["ai", "fix"])
        assert result.exit_code == 1

    def test_fix_exits_0_when_loop_returns_true(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=_ready_status()),
            patch("tycoon.commands.ai.run_fix_loop", return_value=True),
        ):
            result = cli_runner.invoke(app, ["ai", "fix", "--no-context"])
        assert result.exit_code == 0
        assert "passing" in result.stdout.lower() or "pass" in result.stdout.lower()

    def test_fix_exits_1_when_loop_returns_false(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=_ready_status()),
            patch("tycoon.commands.ai.run_fix_loop", return_value=False),
        ):
            result = cli_runner.invoke(app, ["ai", "fix", "--no-context"])
        assert result.exit_code == 1

    def test_fix_passes_max_attempts_to_loop(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=_ready_status()),
            patch("tycoon.commands.ai.run_fix_loop", return_value=True) as mock_loop,
        ):
            cli_runner.invoke(app, ["ai", "fix", "--no-context", "--max-attempts", "7"])
        assert mock_loop.call_args[1]["max_attempts"] == 7

    def test_fix_passes_target_to_loop(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=_ready_status()),
            patch("tycoon.commands.ai.run_fix_loop", return_value=True) as mock_loop,
        ):
            cli_runner.invoke(app, ["ai", "fix", "--no-context", "--target", "prod"])
        assert mock_loop.call_args[1]["target"] == "prod"

    def test_fix_passes_select_to_loop(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=_ready_status()),
            patch("tycoon.commands.ai.run_fix_loop", return_value=True) as mock_loop,
        ):
            cli_runner.invoke(app, ["ai", "fix", "--no-context", "--select", "staging+"])
        assert mock_loop.call_args[1]["select"] == "staging+"

    def test_fix_prints_ai_hint_on_failure(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=_ready_status()),
            patch("tycoon.commands.ai.run_fix_loop", return_value=False),
        ):
            result = cli_runner.invoke(app, ["ai", "fix", "--no-context"])
        assert "dbt test failures" in result.stdout

    def test_fix_uses_no_context_system_prompt(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=_ready_status()),
            patch("tycoon.commands.ai.run_fix_loop", return_value=True) as mock_loop,
        ):
            cli_runner.invoke(app, ["ai", "fix", "--no-context"])
        system_prompt = mock_loop.call_args[1]["system_prompt"]
        assert "data pipeline assistant" in system_prompt
