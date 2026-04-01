"""Tests for the PipelineDebugger and SchemaDriftDetector AI workers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tycoon.ai.workers.ingestion import PipelineDebugger, SchemaDriftDetector
from tycoon.ai.workers.base import WorkerResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_result() -> WorkerResult:
    return WorkerResult(success=True, proposals=[], message="")


def _fake_response(path: str, content: str) -> str:
    return f"```{path}\n{content}\n```\n"


_STACK_TRACE = (
    "Traceback (most recent call last):\n"
    "  File 'pipeline.py', line 42, in run\n"
    "    pipeline.run()\n"
    "dlt.common.exceptions.PipelineStepFailed: schema mismatch on column 'amount'"
)

_SOURCE_CONFIG = (
    "pipeline_name: my_orders\n"
    "destination: duckdb\n"
    "dataset_name: orders_raw\n"
)

_EXPECTED_SCHEMA = "id: BIGINT\nname: VARCHAR\namount: NUMERIC"
_ACTUAL_SCHEMA = "id: BIGINT\nname: VARCHAR\namount: VARCHAR\nnew_col: TEXT"


# ---------------------------------------------------------------------------
# PipelineDebugger
# ---------------------------------------------------------------------------


class TestPipelineDebuggerSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = PipelineDebugger().system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_dlt(self):
        prompt = PipelineDebugger().system_prompt()
        assert "dlt" in prompt.lower()

    def test_describes_failure_modes(self):
        prompt = PipelineDebugger().system_prompt()
        assert "schema" in prompt.lower() or "mismatch" in prompt.lower()


class TestPipelineDebuggerFormatRequest:
    def test_includes_pipeline_name(self):
        request = PipelineDebugger().format_request(
            pipeline_name="my_orders",
            error_output=_STACK_TRACE,
            source_config=_SOURCE_CONFIG,
        )
        assert "my_orders" in request

    def test_includes_error_output(self):
        request = PipelineDebugger().format_request(
            pipeline_name="my_orders",
            error_output=_STACK_TRACE,
            source_config=_SOURCE_CONFIG,
        )
        assert "schema mismatch on column 'amount'" in request

    def test_includes_source_config(self):
        request = PipelineDebugger().format_request(
            pipeline_name="my_orders",
            error_output=_STACK_TRACE,
            source_config=_SOURCE_CONFIG,
        )
        assert "destination: duckdb" in request

    def test_schema_info_included_when_provided(self):
        request = PipelineDebugger().format_request(
            pipeline_name="my_orders",
            error_output=_STACK_TRACE,
            source_config=_SOURCE_CONFIG,
            schema_info="id: BIGINT\namount: NUMERIC",
        )
        assert "id: BIGINT" in request

    def test_schema_info_absent_message_when_not_provided(self):
        request = PipelineDebugger().format_request(
            pipeline_name="my_orders",
            error_output=_STACK_TRACE,
            source_config=_SOURCE_CONFIG,
        )
        assert "not available" in request.lower()


class TestPipelineDebuggerValidate:
    def test_always_returns_true(self):
        # PipelineDebugger.validate is always True — text-only diagnosis is valid
        assert PipelineDebugger().validate(_empty_result()) is True

    def test_returns_true_with_proposals_too(self):
        from tycoon.ai.file_proposals import FileProposal

        result = WorkerResult(
            success=True,
            proposals=[FileProposal(path="tycoon.yml", content="pipeline_name: fixed\n")],
            message="",
        )
        assert PipelineDebugger().validate(result) is True


class TestPipelineDebuggerExtractMetadata:
    def test_diagnosed_is_true(self):
        meta = PipelineDebugger().extract_metadata(
            "The failure is a schema mismatch.",
            pipeline_name="my_orders",
        )
        assert meta["diagnosed"] is True

    def test_has_fix_true_when_proposals_present(self):
        response = _fake_response("tycoon.yml", "pipeline_name: fixed\n")
        meta = PipelineDebugger().extract_metadata(response, pipeline_name="my_orders")
        assert meta["has_fix"] is True

    def test_has_fix_false_when_no_proposals(self):
        meta = PipelineDebugger().extract_metadata(
            "Manual intervention required.",
            pipeline_name="my_orders",
        )
        assert meta["has_fix"] is False


class TestPipelineDebuggerRun:
    def test_run_returns_success_with_text_only_response(self):
        # Valid even with no proposals because validate() always returns True
        with patch("tycoon.ai.workers.base.chat", return_value="Manual fix required."):
            result = PipelineDebugger().run(
                pipeline_name="my_orders",
                error_output=_STACK_TRACE,
                source_config=_SOURCE_CONFIG,
            )
        assert result.success is True
        assert result.metadata["diagnosed"] is True
        assert result.metadata["has_fix"] is False

    def test_run_returns_success_with_file_proposals(self):
        response = _fake_response("tycoon.yml", "pipeline_name: fixed\ndestination: duckdb\n")
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            result = PipelineDebugger().run(
                pipeline_name="my_orders",
                error_output=_STACK_TRACE,
                source_config=_SOURCE_CONFIG,
            )
        assert result.success is True
        assert len(result.proposals) == 1
        assert result.metadata["has_fix"] is True

    def test_run_fails_when_chat_raises(self):
        with patch("tycoon.ai.workers.base.chat", side_effect=Exception("connection error")):
            result = PipelineDebugger().run(
                pipeline_name="my_orders",
                error_output=_STACK_TRACE,
                source_config=_SOURCE_CONFIG,
            )
        assert result.success is False
        assert "connection error" in result.message


# ---------------------------------------------------------------------------
# SchemaDriftDetector
# ---------------------------------------------------------------------------


class TestSchemaDriftDetectorSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = SchemaDriftDetector().system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_drift(self):
        prompt = SchemaDriftDetector().system_prompt()
        assert "drift" in prompt.lower()

    def test_mentions_added_removed_columns(self):
        prompt = SchemaDriftDetector().system_prompt()
        assert "added" in prompt.lower() and "removed" in prompt.lower()

    def test_never_drop_data_rule(self):
        prompt = SchemaDriftDetector().system_prompt()
        assert "drop" in prompt.lower() or "never" in prompt.lower()


class TestSchemaDriftDetectorFormatRequest:
    def test_includes_source_name(self):
        request = SchemaDriftDetector().format_request(
            source_name="orders",
            expected_schema=_EXPECTED_SCHEMA,
            actual_schema=_ACTUAL_SCHEMA,
        )
        assert "orders" in request

    def test_includes_expected_schema(self):
        request = SchemaDriftDetector().format_request(
            source_name="orders",
            expected_schema=_EXPECTED_SCHEMA,
            actual_schema=_ACTUAL_SCHEMA,
        )
        assert "amount: NUMERIC" in request

    def test_includes_actual_schema(self):
        request = SchemaDriftDetector().format_request(
            source_name="orders",
            expected_schema=_EXPECTED_SCHEMA,
            actual_schema=_ACTUAL_SCHEMA,
        )
        assert "new_col: TEXT" in request


class TestSchemaDriftDetectorValidate:
    def test_always_returns_true_when_no_proposals(self):
        # No drift → empty proposals → still valid
        assert SchemaDriftDetector().validate(_empty_result()) is True

    def test_returns_true_with_proposals(self):
        from tycoon.ai.file_proposals import FileProposal

        result = WorkerResult(
            success=True,
            proposals=[FileProposal(path="schema_drift.md", content="## Added\n- new_col\n")],
            message="",
        )
        assert SchemaDriftDetector().validate(result) is True


class TestSchemaDriftDetectorExtractMetadata:
    def test_drift_detected_true_when_proposals_present(self):
        response = _fake_response("schema_drift.md", "## Added\n- new_col: TEXT\n")
        meta = SchemaDriftDetector().extract_metadata(response, source_name="orders")
        assert meta["drift_detected"] is True

    def test_drift_detected_false_when_no_proposals(self):
        meta = SchemaDriftDetector().extract_metadata(
            "No schema drift detected.",
            source_name="orders",
        )
        assert meta["drift_detected"] is False

    def test_source_name_propagated(self):
        meta = SchemaDriftDetector().extract_metadata(
            "No schema drift detected.",
            source_name="orders",
        )
        assert meta["source_name"] == "orders"

    def test_source_name_defaults_to_empty_string(self):
        meta = SchemaDriftDetector().extract_metadata("No drift.")
        assert meta["source_name"] == ""


class TestSchemaDriftDetectorRun:
    def test_run_succeeds_with_no_drift_response(self):
        with patch("tycoon.ai.workers.base.chat", return_value="No schema drift detected."):
            result = SchemaDriftDetector().run(
                source_name="orders",
                expected_schema=_EXPECTED_SCHEMA,
                actual_schema=_ACTUAL_SCHEMA,
            )
        assert result.success is True
        assert len(result.proposals) == 0
        assert result.metadata["drift_detected"] is False

    def test_run_succeeds_with_drift_report(self):
        response = _fake_response("schema_drift.md", "## Added\n- new_col: TEXT\n## Type Changes\n- amount: NUMERIC → VARCHAR\n")
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            result = SchemaDriftDetector().run(
                source_name="orders",
                expected_schema=_EXPECTED_SCHEMA,
                actual_schema=_ACTUAL_SCHEMA,
            )
        assert result.success is True
        assert len(result.proposals) == 1
        assert result.metadata["drift_detected"] is True
        assert result.metadata["source_name"] == "orders"

    def test_run_fails_when_chat_raises(self):
        with patch("tycoon.ai.workers.base.chat", side_effect=Exception("server error")):
            result = SchemaDriftDetector().run(
                source_name="orders",
                expected_schema=_EXPECTED_SCHEMA,
                actual_schema=_ACTUAL_SCHEMA,
            )
        assert result.success is False
