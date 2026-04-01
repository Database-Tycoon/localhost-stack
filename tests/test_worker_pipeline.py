"""Tests for WorkerPipeline composition and file-writing behaviour."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tycoon.ai.workers.base import BaseWorker, WorkerPipeline, WorkerResult
from tycoon.ai.file_proposals import FileProposal


# ---------------------------------------------------------------------------
# Inline worker stubs (no LM Studio required)
# ---------------------------------------------------------------------------


class _StaticWorker(BaseWorker):
    """Returns a canned WorkerResult without hitting any LLM."""

    name = "static-worker"
    description = "Test stub that returns a fixed result."

    def __init__(self, proposals: list[FileProposal], metadata: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._proposals = proposals
        self._metadata = metadata or {}

    def system_prompt(self) -> str:
        return "Static system prompt for testing."

    def format_request(self, **kwargs: Any) -> str:
        return f"Static request with kwargs: {kwargs}"

    def run(self, **kwargs: Any) -> WorkerResult:  # type: ignore[override]
        return WorkerResult(
            success=True,
            proposals=self._proposals,
            message="static response",
            metadata=self._metadata,
        )


class _FailingWorker(BaseWorker):
    """Always returns a failed WorkerResult."""

    name = "failing-worker"
    description = "Test stub that always fails."

    def system_prompt(self) -> str:
        return "Failing worker prompt."

    def format_request(self, **kwargs: Any) -> str:
        return "Failing request."

    def run(self, **kwargs: Any) -> WorkerResult:  # type: ignore[override]
        return WorkerResult(success=False, proposals=[], message="deliberate failure")


# ---------------------------------------------------------------------------
# BaseWorker interface
# ---------------------------------------------------------------------------


class TestBaseWorkerInterface:
    def test_system_prompt_raises_not_implemented(self):
        worker = BaseWorker()
        with pytest.raises(NotImplementedError):
            worker.system_prompt()

    def test_format_request_raises_not_implemented(self):
        worker = BaseWorker()
        with pytest.raises(NotImplementedError):
            worker.format_request()

    def test_validate_default_returns_true(self):
        worker = BaseWorker()
        result = WorkerResult(success=True, proposals=[], message="")
        assert worker.validate(result) is True

    def test_extract_metadata_default_returns_empty_dict(self):
        worker = BaseWorker()
        assert worker.extract_metadata("anything") == {}


# ---------------------------------------------------------------------------
# WorkerPipeline — context merging
# ---------------------------------------------------------------------------


class TestWorkerPipelineContextMerging:
    def test_metadata_from_step1_available_to_step2(self, tmp_path: Path):
        """Metadata produced by step 1 must be merged into context before step 2 runs."""
        received_kwargs: dict[str, Any] = {}

        class _RecordingWorker(BaseWorker):
            name = "recording-worker"
            description = "Records kwargs it receives."

            def system_prompt(self) -> str:
                return "Recording worker."

            def format_request(self, **kwargs: Any) -> str:
                return ""

            def run(self, **kwargs: Any) -> WorkerResult:  # type: ignore[override]
                received_kwargs.update(kwargs)
                return WorkerResult(success=True, proposals=[], message="", metadata={})

        step1_worker = _StaticWorker(
            proposals=[],
            metadata={"step1_output": "hello_from_step1"},
        )
        step2_worker = _RecordingWorker()

        pipeline = WorkerPipeline(
            steps=[
                (step1_worker, {}),
                (step2_worker, {"downstream_key": "step1_output"}),
            ],
            project_root=tmp_path,
            dry_run=True,
        )
        pipeline.run(initial_inputs={})

        assert received_kwargs.get("downstream_key") == "hello_from_step1"

    def test_initial_inputs_available_to_all_steps(self, tmp_path: Path):
        received: list[dict] = []

        class _CapturingWorker(BaseWorker):
            name = "capturing"
            description = "Captures kwargs."

            def system_prompt(self) -> str:
                return ""

            def format_request(self, **kwargs: Any) -> str:
                return ""

            def run(self, **kwargs: Any) -> WorkerResult:  # type: ignore[override]
                received.append(dict(kwargs))
                return WorkerResult(success=True, proposals=[], message="", metadata={})

        pipeline = WorkerPipeline(
            steps=[
                (_CapturingWorker(), {"model": "model_name"}),
                (_CapturingWorker(), {"model": "model_name"}),
            ],
            project_root=tmp_path,
            dry_run=True,
        )
        pipeline.run(initial_inputs={"model_name": "stg_trips"})

        assert received[0].get("model") == "stg_trips"
        assert received[1].get("model") == "stg_trips"


# ---------------------------------------------------------------------------
# WorkerPipeline — dry_run=True
# ---------------------------------------------------------------------------


class TestWorkerPipelineDryRun:
    def test_dry_run_does_not_write_files(self, tmp_path: Path):
        output_path = "subdir/output.sql"
        step1 = _StaticWorker(
            proposals=[FileProposal(path=output_path, content="SELECT 1\n")],
        )

        pipeline = WorkerPipeline(
            steps=[(step1, {})],
            project_root=tmp_path,
            dry_run=True,
        )
        results = pipeline.run(initial_inputs={})

        assert results[0].success is True
        assert not (tmp_path / output_path).exists()

    def test_dry_run_returns_proposals_in_result(self, tmp_path: Path):
        step1 = _StaticWorker(
            proposals=[FileProposal(path="models/stg_test.sql", content="SELECT 1\n")],
        )

        pipeline = WorkerPipeline(
            steps=[(step1, {})],
            project_root=tmp_path,
            dry_run=True,
        )
        results = pipeline.run(initial_inputs={})

        assert len(results[0].proposals) == 1
        assert results[0].proposals[0].path == "models/stg_test.sql"


# ---------------------------------------------------------------------------
# WorkerPipeline — dry_run=False (actual file writing)
# ---------------------------------------------------------------------------


class TestWorkerPipelineFileWriting:
    def test_writes_file_at_relative_path(self, tmp_path: Path):
        output_path = "models/staging/stg_test.sql"
        step1 = _StaticWorker(
            proposals=[FileProposal(path=output_path, content="SELECT 1 AS id\n")],
        )

        pipeline = WorkerPipeline(
            steps=[(step1, {})],
            project_root=tmp_path,
            dry_run=False,
        )
        pipeline.run(initial_inputs={})

        written = tmp_path / output_path
        assert written.exists()
        assert written.read_text() == "SELECT 1 AS id\n"

    def test_writes_file_at_absolute_path(self, tmp_path: Path):
        absolute_target = tmp_path / "absolute_output.sql"
        step1 = _StaticWorker(
            proposals=[FileProposal(path=str(absolute_target), content="SELECT 2\n")],
        )

        pipeline = WorkerPipeline(
            steps=[(step1, {})],
            project_root=tmp_path,
            dry_run=False,
        )
        pipeline.run(initial_inputs={})

        assert absolute_target.exists()
        assert absolute_target.read_text() == "SELECT 2\n"

    def test_creates_parent_directories(self, tmp_path: Path):
        nested = "deep/nested/dir/output.sql"
        step1 = _StaticWorker(
            proposals=[FileProposal(path=nested, content="SELECT 3\n")],
        )

        pipeline = WorkerPipeline(
            steps=[(step1, {})],
            project_root=tmp_path,
            dry_run=False,
        )
        pipeline.run(initial_inputs={})

        assert (tmp_path / nested).exists()

    def test_writes_multiple_proposals_from_single_step(self, tmp_path: Path):
        step1 = _StaticWorker(
            proposals=[
                FileProposal(path="models/stg_a.sql", content="SELECT 1\n"),
                FileProposal(path="models/stg_b.sql", content="SELECT 2\n"),
            ],
        )

        pipeline = WorkerPipeline(
            steps=[(step1, {})],
            project_root=tmp_path,
            dry_run=False,
        )
        pipeline.run(initial_inputs={})

        assert (tmp_path / "models/stg_a.sql").exists()
        assert (tmp_path / "models/stg_b.sql").exists()


# ---------------------------------------------------------------------------
# WorkerPipeline — failure halting
# ---------------------------------------------------------------------------


class TestWorkerPipelineFailureHandling:
    def test_pipeline_halts_on_failed_step(self, tmp_path: Path):
        step2_ran = []

        class _TrackingWorker(BaseWorker):
            name = "tracking"
            description = "Tracks if it ran."

            def system_prompt(self) -> str:
                return ""

            def format_request(self, **kwargs: Any) -> str:
                return ""

            def run(self, **kwargs: Any) -> WorkerResult:  # type: ignore[override]
                step2_ran.append(True)
                return WorkerResult(success=True, proposals=[], message="", metadata={})

        pipeline = WorkerPipeline(
            steps=[
                (_FailingWorker(), {}),
                (_TrackingWorker(), {}),
            ],
            project_root=tmp_path,
            dry_run=True,
        )
        results = pipeline.run(initial_inputs={})

        assert len(results) == 1
        assert results[0].success is False
        assert step2_ran == []

    def test_failed_step_does_not_write_files(self, tmp_path: Path):
        output_path = "models/should_not_exist.sql"

        class _FailingWithProposals(BaseWorker):
            name = "failing-with-proposals"
            description = "Fails but would have written files."

            def system_prompt(self) -> str:
                return ""

            def format_request(self, **kwargs: Any) -> str:
                return ""

            def run(self, **kwargs: Any) -> WorkerResult:  # type: ignore[override]
                return WorkerResult(
                    success=False,
                    proposals=[FileProposal(path=output_path, content="SELECT 1\n")],
                    message="failed",
                )

        pipeline = WorkerPipeline(
            steps=[(_FailingWithProposals(), {})],
            project_root=tmp_path,
            dry_run=False,
        )
        pipeline.run(initial_inputs={})

        assert not (tmp_path / output_path).exists()

    def test_returns_all_results_up_to_failure(self, tmp_path: Path):
        pipeline = WorkerPipeline(
            steps=[
                (_StaticWorker(proposals=[], metadata={}), {}),
                (_StaticWorker(proposals=[], metadata={}), {}),
                (_FailingWorker(), {}),
                (_StaticWorker(proposals=[], metadata={}), {}),
            ],
            project_root=tmp_path,
            dry_run=True,
        )
        results = pipeline.run(initial_inputs={})

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is True
        assert results[2].success is False


# ---------------------------------------------------------------------------
# WorkerPipeline — two-step composition end-to-end
# ---------------------------------------------------------------------------


class TestWorkerPipelineTwoStepComposition:
    def test_two_step_pipeline_with_context_forwarding(self, tmp_path: Path):
        """Full end-to-end: step 1 produces metadata, step 2 receives it, both write files."""
        step1 = _StaticWorker(
            proposals=[FileProposal(path="models/stg_trips.sql", content="SELECT trip_id FROM raw\n")],
            metadata={"schema_yml_path": "models/staging/schema.yml"},
        )

        captured: dict[str, Any] = {}

        class _SchemaStep(BaseWorker):
            name = "schema-step"
            description = "Second step that receives schema path from step 1."

            def system_prompt(self) -> str:
                return ""

            def format_request(self, **kwargs: Any) -> str:
                return ""

            def run(self, **kwargs: Any) -> WorkerResult:  # type: ignore[override]
                captured.update(kwargs)
                return WorkerResult(
                    success=True,
                    proposals=[FileProposal(path="models/staging/schema.yml", content="version: 2\n")],
                    message="",
                    metadata={},
                )

        pipeline = WorkerPipeline(
            steps=[
                (step1, {}),
                (_SchemaStep(), {"schema_path": "schema_yml_path"}),
            ],
            project_root=tmp_path,
            dry_run=False,
        )
        results = pipeline.run(initial_inputs={})

        assert len(results) == 2
        assert all(r.success for r in results)
        assert captured.get("schema_path") == "models/staging/schema.yml"
        assert (tmp_path / "models/stg_trips.sql").exists()
        assert (tmp_path / "models/staging/schema.yml").exists()
