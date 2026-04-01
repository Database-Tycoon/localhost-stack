"""Tests for the TestWriter and TestFixer AI workers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tycoon.ai.workers.tests import TestFixer, TestWriter
from tycoon.ai.workers.base import WorkerResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_result() -> WorkerResult:
    return WorkerResult(success=True, proposals=[], message="")


def _fake_response(path: str, content: str) -> str:
    return f"Here you go:\n\n```{path}\n{content}\n```\n"


# ---------------------------------------------------------------------------
# TestWriter
# ---------------------------------------------------------------------------


class TestTestWriterSystemPrompt:
    def test_returns_nonempty_string(self):
        worker = TestWriter()
        prompt = worker.system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_dbt_test_engineer(self):
        prompt = TestWriter().system_prompt()
        assert "dbt" in prompt.lower()

    def test_mentions_schema_yml(self):
        prompt = TestWriter().system_prompt()
        assert "schema.yml" in prompt


class TestTestWriterFormatRequest:
    def test_includes_model_name(self):
        worker = TestWriter()
        request = worker.format_request(
            model_name="stg_trips",
            model_path="models/staging/stg_trips.sql",
            profile_summary="column: trip_id, likely_pk=true",
        )
        assert "stg_trips" in request

    def test_includes_profile_summary(self):
        worker = TestWriter()
        request = worker.format_request(
            model_name="stg_trips",
            model_path="models/staging/stg_trips.sql",
            profile_summary="column: trip_id, likely_pk=true",
        )
        assert "likely_pk=true" in request

    def test_includes_schema_yml_output_path(self):
        worker = TestWriter()
        request = worker.format_request(
            model_name="stg_trips",
            model_path="models/staging/stg_trips.sql",
            profile_summary="col: id",
        )
        assert "schema.yml" in request


class TestTestWriterValidate:
    def test_returns_false_when_proposals_empty(self):
        worker = TestWriter()
        assert worker.validate(_empty_result()) is False

    def test_returns_true_when_proposals_present(self):
        from tycoon.ai.file_proposals import FileProposal

        worker = TestWriter()
        result = WorkerResult(
            success=True,
            proposals=[FileProposal(path="models/staging/schema.yml", content="version: 2\n")],
            message="",
        )
        assert worker.validate(result) is True


class TestTestWriterExtractMetadata:
    def test_returns_schema_yml_path_from_response(self):
        worker = TestWriter()
        response = _fake_response("models/staging/schema.yml", "version: 2\nmodels:\n  - name: stg_trips\n")
        meta = worker.extract_metadata(response, model_name="stg_trips", model_path="models/staging/stg_trips.sql")
        assert isinstance(meta, dict)
        assert meta.get("schema_yml_path") == "models/staging/schema.yml"

    def test_returns_empty_dict_when_no_proposals(self):
        worker = TestWriter()
        meta = worker.extract_metadata("No fenced blocks here.", model_name="stg_trips", model_path="x.sql")
        assert meta == {}


class TestTestWriterRun:
    def test_run_returns_worker_result_on_success(self):
        response = _fake_response("models/staging/schema.yml", "version: 2\n")
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            worker = TestWriter()
            result = worker.run(
                model_name="stg_trips",
                model_path="models/staging/stg_trips.sql",
                profile_summary="column: trip_id, likely_pk=true",
            )
        assert result.success is True
        assert len(result.proposals) == 1
        assert result.proposals[0].path == "models/staging/schema.yml"

    def test_run_fails_when_chat_raises(self):
        with patch("tycoon.ai.workers.base.chat", side_effect=Exception("server down")):
            worker = TestWriter()
            result = worker.run(
                model_name="stg_trips",
                model_path="models/staging/stg_trips.sql",
                profile_summary="col: id",
            )
        assert result.success is False
        assert "server down" in result.message

    def test_run_fails_validation_when_no_proposals(self):
        with patch("tycoon.ai.workers.base.chat", return_value="No fenced blocks."):
            worker = TestWriter()
            result = worker.run(
                model_name="stg_trips",
                model_path="models/staging/stg_trips.sql",
                profile_summary="col: id",
            )
        assert result.success is False
        assert "validation failed" in result.message


# ---------------------------------------------------------------------------
# TestFixer
# ---------------------------------------------------------------------------


class TestTestFixerSystemPrompt:
    def test_returns_nonempty_string(self):
        worker = TestFixer()
        prompt = worker.system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_dbt_debugger(self):
        prompt = TestFixer().system_prompt()
        assert "dbt" in prompt.lower()

    def test_mentions_minimal_fix(self):
        prompt = TestFixer().system_prompt()
        assert "minimal" in prompt.lower() or "smallest" in prompt.lower()


class TestTestFixerFormatRequest:
    def test_includes_test_name(self):
        worker = TestFixer()
        request = worker.format_request(
            test_name="not_null_stg_trips_trip_id",
            failure_output="1 row failed",
            model_sql="SELECT trip_id FROM source",
            schema_yaml="version: 2",
        )
        assert "not_null_stg_trips_trip_id" in request

    def test_includes_failure_output(self):
        worker = TestFixer()
        request = worker.format_request(
            test_name="unique_stg_trips_trip_id",
            failure_output="5 duplicate rows found",
            model_sql="SELECT trip_id FROM source",
            schema_yaml="version: 2",
        )
        assert "5 duplicate rows found" in request

    def test_includes_schema_yaml_section(self):
        worker = TestFixer()
        request = worker.format_request(
            test_name="not_null_stg_trips_trip_id",
            failure_output="1 row failed",
            model_sql="SELECT trip_id FROM source",
            schema_yaml="version: 2\nmodels:\n  - name: stg_trips",
        )
        assert "schema.yml" in request.lower() or "version: 2" in request

    def test_includes_model_sql(self):
        worker = TestFixer()
        request = worker.format_request(
            test_name="not_null_stg_trips_trip_id",
            failure_output="1 row failed",
            model_sql="SELECT trip_id FROM source_table",
            schema_yaml="version: 2",
        )
        assert "source_table" in request


class TestTestFixerValidate:
    def test_returns_false_when_proposals_empty(self):
        worker = TestFixer()
        assert worker.validate(_empty_result()) is False

    def test_returns_true_when_proposals_present(self):
        from tycoon.ai.file_proposals import FileProposal

        worker = TestFixer()
        result = WorkerResult(
            success=True,
            proposals=[FileProposal(path="models/staging/schema.yml", content="version: 2\n")],
            message="",
        )
        assert worker.validate(result) is True


class TestTestFixerRun:
    def test_run_returns_worker_result_on_success(self):
        response = _fake_response("models/staging/schema.yml", "version: 2\nmodels:\n  - name: stg_trips\n")
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            worker = TestFixer()
            result = worker.run(
                test_name="not_null_stg_trips_trip_id",
                failure_output="1 row failed",
                model_sql="SELECT trip_id FROM source",
                schema_yaml="version: 2",
            )
        assert result.success is True
        assert len(result.proposals) == 1

    def test_run_fails_when_chat_raises(self):
        with patch("tycoon.ai.workers.base.chat", side_effect=Exception("timeout")):
            worker = TestFixer()
            result = worker.run(
                test_name="not_null_stg_trips_trip_id",
                failure_output="1 row failed",
                model_sql="SELECT trip_id FROM source",
                schema_yaml="version: 2",
            )
        assert result.success is False

    def test_run_fails_validation_when_no_proposals(self):
        with patch("tycoon.ai.workers.base.chat", return_value="Just a text explanation, no files."):
            worker = TestFixer()
            result = worker.run(
                test_name="not_null_stg_trips_trip_id",
                failure_output="1 row failed",
                model_sql="SELECT trip_id FROM source",
                schema_yaml="version: 2",
            )
        assert result.success is False
        assert "validation failed" in result.message
