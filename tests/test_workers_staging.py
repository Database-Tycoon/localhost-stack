"""Tests for the StagingImprover, NullHandler, ColumnDocumenter, and ColumnRenamer workers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tycoon.ai.workers.staging import (
    ColumnDocumenter,
    ColumnRenamer,
    NullHandler,
    StagingImprover,
)
from tycoon.ai.workers.base import WorkerResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_result() -> WorkerResult:
    return WorkerResult(success=True, proposals=[], message="")


def _fake_response(path: str, content: str) -> str:
    return f"```{path}\n{content}\n```\n"


_SAMPLE_SQL = "SELECT id, name, amount FROM raw.orders"
_SAMPLE_PROFILE = "column: id, likely_pk=true\ncolumn: name, null_rate=0.0\ncolumn: amount, null_rate=0.3"
_MODEL_NAME = "stg_orders"


# ---------------------------------------------------------------------------
# StagingImprover
# ---------------------------------------------------------------------------


class TestStagingImproverSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = StagingImprover().system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_staging_conventions(self):
        prompt = StagingImprover().system_prompt()
        assert "staging" in prompt.lower()

    def test_mentions_snake_case(self):
        prompt = StagingImprover().system_prompt()
        assert "snake_case" in prompt


class TestStagingImproverFormatRequest:
    def test_includes_model_name(self):
        request = StagingImprover().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert _MODEL_NAME in request

    def test_includes_profile_summary(self):
        request = StagingImprover().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert "likely_pk=true" in request

    def test_includes_model_sql(self):
        request = StagingImprover().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert "SELECT id, name, amount" in request


class TestStagingImproverValidate:
    def test_returns_false_when_proposals_empty(self):
        assert StagingImprover().validate(_empty_result()) is False

    def test_returns_true_when_proposals_present(self):
        from tycoon.ai.file_proposals import FileProposal

        result = WorkerResult(
            success=True,
            proposals=[FileProposal(path="models/staging/stg_orders.sql", content="SELECT id FROM raw.orders\n")],
            message="",
        )
        assert StagingImprover().validate(result) is True


class TestStagingImproverExtractMetadata:
    def test_returns_improved_model_path(self):
        response = _fake_response("models/staging/stg_orders.sql", "SELECT id FROM raw.orders\n")
        meta = StagingImprover().extract_metadata(response, model_name=_MODEL_NAME)
        assert isinstance(meta, dict)
        assert meta.get("improved_model_path") == "models/staging/stg_orders.sql"

    def test_returns_empty_dict_when_no_proposals(self):
        meta = StagingImprover().extract_metadata("No fenced blocks.", model_name=_MODEL_NAME)
        assert meta == {}


class TestStagingImproverRun:
    def test_run_returns_success_with_proposal(self):
        response = _fake_response("models/staging/stg_orders.sql", "SELECT id FROM raw.orders\n")
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            result = StagingImprover().run(
                model_name=_MODEL_NAME,
                model_sql=_SAMPLE_SQL,
                profile_summary=_SAMPLE_PROFILE,
            )
        assert result.success is True
        assert len(result.proposals) == 1

    def test_run_fails_validation_when_no_proposals(self):
        with patch("tycoon.ai.workers.base.chat", return_value="Just prose, no files."):
            result = StagingImprover().run(
                model_name=_MODEL_NAME,
                model_sql=_SAMPLE_SQL,
                profile_summary=_SAMPLE_PROFILE,
            )
        assert result.success is False
        assert "validation failed" in result.message


# ---------------------------------------------------------------------------
# NullHandler
# ---------------------------------------------------------------------------


class TestNullHandlerSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = NullHandler().system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_coalesce(self):
        prompt = NullHandler().system_prompt()
        assert "COALESCE" in prompt

    def test_mentions_null_rate(self):
        prompt = NullHandler().system_prompt()
        assert "null_rate" in prompt or "null rate" in prompt.lower()


class TestNullHandlerFormatRequest:
    def test_includes_model_name(self):
        request = NullHandler().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert _MODEL_NAME in request

    def test_default_null_threshold_shown(self):
        request = NullHandler().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        # Default threshold is 0.1 → rendered as 10%
        assert "10%" in request

    def test_custom_null_threshold_shown(self):
        request = NullHandler().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
            null_threshold=0.25,
        )
        assert "25%" in request

    def test_includes_model_sql(self):
        request = NullHandler().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert "SELECT id, name, amount" in request


class TestNullHandlerValidate:
    def test_returns_false_when_proposals_empty(self):
        assert NullHandler().validate(_empty_result()) is False

    def test_returns_true_when_proposals_present(self):
        from tycoon.ai.file_proposals import FileProposal

        result = WorkerResult(
            success=True,
            proposals=[FileProposal(path="models/staging/stg_orders.sql", content="SELECT COALESCE(amount, 0)\n")],
            message="",
        )
        assert NullHandler().validate(result) is True


class TestNullHandlerRun:
    def test_run_returns_success_with_proposal(self):
        response = _fake_response("models/staging/stg_orders.sql", "SELECT COALESCE(amount, 0)\n")
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            result = NullHandler().run(
                model_name=_MODEL_NAME,
                model_sql=_SAMPLE_SQL,
                profile_summary=_SAMPLE_PROFILE,
            )
        assert result.success is True
        assert len(result.proposals) == 1

    def test_run_fails_when_chat_raises(self):
        with patch("tycoon.ai.workers.base.chat", side_effect=Exception("LM Studio offline")):
            result = NullHandler().run(
                model_name=_MODEL_NAME,
                model_sql=_SAMPLE_SQL,
                profile_summary=_SAMPLE_PROFILE,
            )
        assert result.success is False


# ---------------------------------------------------------------------------
# ColumnDocumenter
# ---------------------------------------------------------------------------


class TestColumnDocumenterSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = ColumnDocumenter().system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_documentation(self):
        prompt = ColumnDocumenter().system_prompt()
        assert "description" in prompt.lower() or "document" in prompt.lower()

    def test_mentions_schema_yml(self):
        prompt = ColumnDocumenter().system_prompt()
        assert "schema.yml" in prompt


class TestColumnDocumenterFormatRequest:
    def test_includes_model_name(self):
        request = ColumnDocumenter().format_request(
            model_name=_MODEL_NAME,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert _MODEL_NAME in request

    def test_includes_profile_summary(self):
        request = ColumnDocumenter().format_request(
            model_name=_MODEL_NAME,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert "likely_pk=true" in request

    def test_no_existing_schema_shows_create_from_scratch(self):
        request = ColumnDocumenter().format_request(
            model_name=_MODEL_NAME,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert "scratch" in request.lower()

    def test_existing_schema_yaml_included_in_request(self):
        existing = "version: 2\nmodels:\n  - name: stg_orders"
        request = ColumnDocumenter().format_request(
            model_name=_MODEL_NAME,
            profile_summary=_SAMPLE_PROFILE,
            existing_schema_yaml=existing,
        )
        assert "version: 2" in request


class TestColumnDocumenterValidate:
    def test_returns_false_when_proposals_empty(self):
        assert ColumnDocumenter().validate(_empty_result()) is False

    def test_returns_true_when_proposals_present(self):
        from tycoon.ai.file_proposals import FileProposal

        result = WorkerResult(
            success=True,
            proposals=[FileProposal(path="models/staging/schema.yml", content="version: 2\n")],
            message="",
        )
        assert ColumnDocumenter().validate(result) is True


class TestColumnDocumenterExtractMetadata:
    def test_returns_documented_columns_count(self):
        response = (
            _fake_response("models/staging/schema.yml", "version: 2\n")
        )
        meta = ColumnDocumenter().extract_metadata(response, model_name=_MODEL_NAME)
        assert isinstance(meta, dict)
        assert "documented_columns" in meta
        assert meta["documented_columns"] == 1

    def test_returns_zero_when_no_proposals(self):
        meta = ColumnDocumenter().extract_metadata("No blocks.", model_name=_MODEL_NAME)
        assert meta["documented_columns"] == 0


class TestColumnDocumenterRun:
    def test_run_returns_success_with_proposal(self):
        response = _fake_response("models/staging/schema.yml", "version: 2\nmodels:\n  - name: stg_orders\n")
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            result = ColumnDocumenter().run(
                model_name=_MODEL_NAME,
                profile_summary=_SAMPLE_PROFILE,
            )
        assert result.success is True
        assert result.metadata.get("documented_columns") == 1


# ---------------------------------------------------------------------------
# ColumnRenamer
# ---------------------------------------------------------------------------


class TestColumnRenamerSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = ColumnRenamer().system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mentions_snake_case(self):
        prompt = ColumnRenamer().system_prompt()
        assert "snake_case" in prompt

    def test_mentions_rename_plan(self):
        prompt = ColumnRenamer().system_prompt()
        assert "rename" in prompt.lower()


class TestColumnRenamerFormatRequest:
    def test_includes_model_name(self):
        request = ColumnRenamer().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert _MODEL_NAME in request

    def test_includes_rename_plan_md_instruction(self):
        request = ColumnRenamer().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert "rename_plan.md" in request

    def test_includes_model_sql(self):
        request = ColumnRenamer().format_request(
            model_name=_MODEL_NAME,
            model_sql=_SAMPLE_SQL,
            profile_summary=_SAMPLE_PROFILE,
        )
        assert "SELECT id, name, amount" in request


class TestColumnRenamerValidate:
    def test_returns_false_when_proposals_empty(self):
        assert ColumnRenamer().validate(_empty_result()) is False

    def test_returns_true_when_proposals_present(self):
        from tycoon.ai.file_proposals import FileProposal

        result = WorkerResult(
            success=True,
            proposals=[
                FileProposal(path="rename_plan.md", content="| old | new | reason |\n"),
                FileProposal(path="models/staging/stg_orders.sql", content="SELECT id AS order_id\n"),
            ],
            message="",
        )
        assert ColumnRenamer().validate(result) is True


class TestColumnRenamerExtractMetadata:
    def test_rename_count_excludes_plan_doc(self):
        # Two proposals: rename_plan.md + one SQL file → rename_count = 1
        response = (
            _fake_response("rename_plan.md", "| old | new | reason |\n")
            + _fake_response("models/staging/stg_orders.sql", "SELECT id AS order_id\n")
        )
        meta = ColumnRenamer().extract_metadata(response, model_name=_MODEL_NAME)
        assert isinstance(meta, dict)
        assert meta["rename_count"] == 1

    def test_rename_count_is_zero_when_only_plan(self):
        response = _fake_response("rename_plan.md", "| old | new | reason |\n")
        meta = ColumnRenamer().extract_metadata(response, model_name=_MODEL_NAME)
        assert meta["rename_count"] == 0

    def test_rename_count_floors_at_zero_when_no_proposals(self):
        meta = ColumnRenamer().extract_metadata("No blocks.", model_name=_MODEL_NAME)
        assert meta["rename_count"] == 0


class TestColumnRenamerRun:
    def test_run_returns_success_with_two_proposals(self):
        response = (
            _fake_response("rename_plan.md", "| old | new | reason |\n")
            + _fake_response("models/staging/stg_orders.sql", "SELECT id AS order_id\n")
        )
        with patch("tycoon.ai.workers.base.chat", return_value=response):
            result = ColumnRenamer().run(
                model_name=_MODEL_NAME,
                model_sql=_SAMPLE_SQL,
                profile_summary=_SAMPLE_PROFILE,
            )
        assert result.success is True
        assert len(result.proposals) == 2
        assert result.metadata["rename_count"] == 1

    def test_run_fails_validation_when_no_proposals(self):
        with patch("tycoon.ai.workers.base.chat", return_value="No renames needed."):
            result = ColumnRenamer().run(
                model_name=_MODEL_NAME,
                model_sql=_SAMPLE_SQL,
                profile_summary=_SAMPLE_PROFILE,
            )
        assert result.success is False
        assert "validation failed" in result.message
