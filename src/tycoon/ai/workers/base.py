"""Base worker infrastructure for the tycoon AI worker factory.

Design principles:
- Each worker has a focused system prompt scoped only to its domain
- Workers take typed, minimal inputs — only what they actually need
- WorkerResult carries structured metadata forward to downstream workers
- WorkerPipeline composes workers into ordered sequences with validation gates
- Workers are stateless — all context is passed explicitly
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tycoon.ai.client import chat
from tycoon.ai.file_proposals import FileProposal, parse_proposals


@dataclass
class WorkerResult:
    """Output from a single worker execution."""

    success: bool
    proposals: list[FileProposal]
    message: str                          # full LLM response text
    metadata: dict[str, Any] = field(default_factory=dict)  # structured data for downstream workers

    @property
    def text(self) -> str:
        """Alias for message — the raw LLM response."""
        return self.message


class BaseWorker:
    """Base class for all AI pipeline workers.

    Subclasses must implement:
    - name: str            — short identifier (e.g. "test-writer")
    - description: str     — one-line description of what this worker does
    - system_prompt()      — focused system prompt for this worker's domain
    - format_request(**kw) — formats the user message from typed inputs

    Subclasses may override:
    - validate(result)     — return False to reject the result (default: always valid)
    - extract_metadata(response, **inputs) — pull structured data from response for downstream use
    """

    name: str = "base"
    description: str = "Base worker"

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def system_prompt(self) -> str:
        raise NotImplementedError(f"{self.__class__.__name__} must implement system_prompt()")

    def format_request(self, **kwargs: Any) -> str:
        raise NotImplementedError(f"{self.__class__.__name__} must implement format_request()")

    def validate(self, result: WorkerResult) -> bool:
        """Return False to reject a result. Override for domain-specific validation."""
        return True

    def extract_metadata(self, response: str, **inputs: Any) -> dict[str, Any]:
        """Extract structured metadata from the response for downstream workers."""
        return {}

    def run(self, **kwargs: Any) -> WorkerResult:
        """Execute the worker against LM Studio. Returns a WorkerResult."""
        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": self.format_request(**kwargs)},
        ]

        try:
            response = chat(messages, model=self.model)
        except Exception as exc:
            return WorkerResult(
                success=False,
                proposals=[],
                message=str(exc),
            )

        proposals = parse_proposals(response)
        metadata = self.extract_metadata(response, **kwargs)

        result = WorkerResult(
            success=True,
            proposals=proposals,
            message=response,
            metadata=metadata,
        )

        if not self.validate(result):
            return WorkerResult(
                success=False,
                proposals=[],
                message=f"{self.name}: validation failed — response did not meet quality gate",
                metadata=metadata,
            )

        return result


class WorkerPipeline:
    """Composes workers into an ordered sequence with automatic file writing.

    Each step receives the inputs passed to run() merged with metadata
    accumulated from all previous steps, allowing workers to pass structured
    data forward without tight coupling.

    If any step fails, the pipeline halts and returns results up to that point.
    Files are written after each successful step (not batched at the end) so
    downstream workers see the updated files if they need to re-read them.
    """

    def __init__(
        self,
        steps: list[tuple[BaseWorker, dict[str, str]]],
        project_root: Path,
        dry_run: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        steps:
            List of (worker, input_map) pairs. input_map maps the worker's
            keyword argument names to keys in the accumulated context dict.
            Use a static value by mapping to a non-existent key and providing
            it in initial_inputs.
        project_root:
            Root directory for resolving relative file paths in proposals.
        dry_run:
            If True, proposals are parsed but files are not written.
        """
        self.steps = steps
        self.project_root = project_root
        self.dry_run = dry_run

    def run(self, initial_inputs: dict[str, Any]) -> list[WorkerResult]:
        """Run all steps in order. Returns list of WorkerResult, one per step."""
        results: list[WorkerResult] = []
        context = dict(initial_inputs)

        for worker, input_map in self.steps:
            # Resolve inputs: keys are worker kwargs, values are context keys
            resolved = {kwarg: context[ctx_key] for kwarg, ctx_key in input_map.items() if ctx_key in context}

            result = worker.run(**resolved)
            results.append(result)

            if not result.success:
                break

            # Write proposals unless dry_run
            if not self.dry_run:
                for proposal in result.proposals:
                    target = Path(proposal.path)
                    if not target.is_absolute():
                        target = self.project_root / target
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(proposal.content)

            # Merge metadata into context for downstream workers
            context.update(result.metadata)

        return results
