"""AI workers for dlt ingestion diagnostics.

Two workers are provided:

PipelineDebugger
    Given a failing dlt pipeline (stack trace + source config + optional schema
    info), diagnoses the root cause and proposes a targeted fix.  It understands
    the dlt → DuckDB → dbt stack and distinguishes between config issues, auth
    failures, rate limits, schema mismatches, and type errors.

SchemaDriftDetector
    Given two schema snapshots (expected vs. actual), identifies column
    additions, removals, type changes, and potential renames, then proposes a
    migration plan.  It will suggest dbt model changes when structural drift
    requires SQL updates, but will never propose changes that drop data.
"""

from __future__ import annotations

from typing import Any

from tycoon.ai.workers.base import BaseWorker, WorkerResult


class PipelineDebugger(BaseWorker):
    """Diagnose a failing dlt pipeline and propose a fix."""

    name = "pipeline-debugger"
    description = "Diagnoses dlt ingestion failures and proposes targeted fixes."

    def system_prompt(self) -> str:
        return (
            "You are a dlt ingestion expert. A dlt pipeline has failed and your job "
            "is to diagnose the root cause and propose the minimal fix.\n"
            "\n"
            "The stack you are working with is: dlt (ingestion) → DuckDB (storage) "
            "→ dbt (transforms). The failure is in the dlt ingestion stage.\n"
            "\n"
            "Failure modes you must recognise:\n"
            "- Schema mismatches: column type conflicts between the source schema and "
            "  the existing DuckDB table.\n"
            "- API authentication failures: missing or expired credentials, wrong "
            "  header format, OAuth token issues.\n"
            "- Rate limits: HTTP 429 or back-off required; propose retry config.\n"
            "- File not found: missing source file, wrong path, or glob pattern that "
            "  matches nothing.\n"
            "- Type errors: Python type mismatch when dlt normalises a field.\n"
            "- Config issues: wrong pipeline name, destination, or dataset name in "
            "  tycoon.yml.\n"
            "\n"
            "Diagnosis format:\n"
            "1. Quote the exact line or lines in the stack trace that identify the "
            "   failure point.\n"
            "2. State the failure mode in one sentence.\n"
            "3. Explain why it is happening.\n"
            "4. Propose the fix as one or more fenced code blocks. Use the target "
            "   file path as the info string (e.g. tycoon.yml, "
            "   pipelines/my_source.py). Output the complete corrected file content "
            "   inside each block — not just a diff or snippet.\n"
            "5. If the issue is a DuckDB schema conflict that requires manual "
            "   intervention (e.g. DROP and recreate a table), explain what the user "
            "   must do manually instead of proposing a file change.\n"
            "6. Do not propose changes that are unrelated to the diagnosed failure.\n"
        )

    def format_request(self, **kwargs: Any) -> str:
        pipeline_name: str = kwargs["pipeline_name"]
        error_output: str = kwargs["error_output"]
        source_config: str = kwargs["source_config"]
        schema_info: str = kwargs.get("schema_info", "")

        parts = [
            f"Pipeline name: {pipeline_name}",
            "",
            "Error output (stack trace):",
            error_output,
            "",
            "Source config (from tycoon.yml):",
            f"```yaml\n{source_config}\n```",
        ]

        if schema_info.strip():
            parts += [
                "",
                "DuckDB schema info:",
                schema_info,
            ]
        else:
            parts.append("")
            parts.append("DuckDB schema info: (not available)")

        parts += ["", "Diagnose the failure and propose a fix now."]

        return "\n".join(parts)

    def validate(self, result: WorkerResult) -> bool:
        # Debugging responses are always valid — text-only diagnosis without
        # file proposals is a legitimate outcome when the fix is manual.
        return True

    def extract_metadata(self, response: str, **inputs: Any) -> dict[str, Any]:
        from tycoon.ai.file_proposals import parse_proposals

        proposals = parse_proposals(response)
        return {
            "diagnosed": True,
            "has_fix": bool(proposals),
        }


class SchemaDriftDetector(BaseWorker):
    """Detect schema drift between expected and actual column sets."""

    name = "schema-drift-detector"
    description = (
        "Identifies column additions, removals, type changes, and renames "
        "between two schema snapshots and proposes a migration plan."
    )

    def system_prompt(self) -> str:
        return (
            "You are a schema migration expert for a dlt → DuckDB → dbt stack. "
            "You have been given two schema snapshots for the same source table: "
            "the expected schema (from a prior profile or specification) and the "
            "actual schema currently present in DuckDB.\n"
            "\n"
            "Your job is to:\n"
            "1. Compare the two snapshots and identify every type of drift:\n"
            "   - Added columns: present in actual but not in expected.\n"
            "   - Removed columns: present in expected but not in actual.\n"
            "   - Type changes: same column name but different data type.\n"
            "   - Potential renames: a column that disappeared AND a new column "
            "     appeared with a similar name and a compatible or changed type "
            "     — flag these as suspected renames (heuristic, not certain).\n"
            "2. Produce a structured drift report as a single fenced code block "
            "   with info string 'schema_drift.md'. Use markdown with clear "
            "   sections: Added, Removed, Type Changes, Suspected Renames. "
            "   If there is no drift in a category, write 'None'.\n"
            "3. If any drift requires changes to a dbt staging model (e.g. a "
            "   column was removed and is referenced in a SELECT, or a type change "
            "   requires an explicit CAST), propose the updated SQL as a second "
            "   fenced code block whose info string is the model's relative path "
            "   (e.g. models/staging/stg_my_source.sql). Output the complete "
            "   corrected SQL — not a diff.\n"
            "4. If there is no drift at all, write 'No schema drift detected.' and "
            "   output no fenced blocks.\n"
            "5. NEVER propose changes that would drop data (e.g. dropping columns "
            "   that still exist in the actual schema or truncating tables).\n"
            "6. Do not emit any text outside the fenced blocks except for the "
            "   'No schema drift detected.' message.\n"
        )

    def format_request(self, **kwargs: Any) -> str:
        source_name: str = kwargs["source_name"]
        expected_schema: str = kwargs["expected_schema"]
        actual_schema: str = kwargs["actual_schema"]

        return (
            f"Source name: {source_name}\n"
            "\n"
            "Expected schema (prior profile or specification):\n"
            f"{expected_schema}\n"
            "\n"
            "Actual schema (current DuckDB columns from TableProfile.summary()):\n"
            f"{actual_schema}\n"
            "\n"
            "Produce the drift report now."
        )

    def validate(self, result: WorkerResult) -> bool:
        # Always valid — an empty proposal list is the correct output when
        # no drift is detected.
        return True

    def extract_metadata(self, response: str, **inputs: Any) -> dict[str, Any]:
        from tycoon.ai.file_proposals import parse_proposals

        proposals = parse_proposals(response)
        source_name: str = inputs.get("source_name", "")
        return {
            "drift_detected": bool(proposals),
            "source_name": source_name,
        }
