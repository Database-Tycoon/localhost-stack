"""AI workers for dbt test generation and repair.

Two workers are provided:

TestWriter
    Given a table profile and a dbt model path, generates a schema.yml file
    populated with dbt generic tests (not_null, unique, accepted_values,
    relationships).  It uses the is_likely_pk and is_low_cardinality heuristics
    from the profile summary to choose which tests to apply to each column.

TestFixer
    Given a specific failing dbt test along with the model SQL and schema YAML,
    proposes the minimal change needed to fix that one test.  It will modify
    either schema.yml (e.g. wrong accepted_values list) or the model SQL (e.g.
    a column that is legitimately nullable) — but never both unless absolutely
    required, and never rewrites anything beyond the specific failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tycoon.ai.workers.base import BaseWorker, WorkerResult


class TestWriter(BaseWorker):
    """Generate a dbt schema.yml with generic tests from a table profile."""

    name = "test-writer"
    description = "Generates dbt schema.yml generic tests from a TableProfile summary."

    def system_prompt(self) -> str:
        return (
            "You are a dbt test engineer. Your only job is to produce a valid dbt "
            "schema.yml file containing generic column tests for one model.\n"
            "\n"
            "Rules:\n"
            "1. Output exactly one fenced code block whose info string is the full "
            "   relative path to the schema.yml file (same directory as the model SQL "
            "   file, e.g. models/staging/schema.yml). No other fenced blocks.\n"
            "2. Use only dbt built-in generic tests: not_null, unique, "
            "   accepted_values, relationships.\n"
            "3. Apply tests using these heuristics derived from the profile summary:\n"
            "   - If a column is marked likely_pk=true → add both not_null and unique.\n"
            "   - If a column has a values=[...] list in the summary (low cardinality, "
            "     <= 20 distinct values) → add accepted_values with every listed value.\n"
            "   - Do not add tests that the profile does not justify.\n"
            "4. Do not include SQL, prose explanations, or any text outside the single "
            "   fenced block.\n"
            "5. The YAML must be valid and indented with 2 spaces.\n"
            "6. Include a top-level 'version: 2' key.\n"
            "7. Only emit tests for columns that actually need them — omit columns "
            "   with no applicable tests rather than listing them with an empty tests: [].\n"
        )

    def format_request(self, **kwargs: Any) -> str:
        model_name: str = kwargs["model_name"]
        model_path: str = kwargs["model_path"]
        profile_summary: str = kwargs["profile_summary"]

        schema_dir = str(Path(model_path).parent)

        return (
            f"Model name: {model_name}\n"
            f"Model SQL path: {model_path}\n"
            f"Schema YAML output path (use this as the fenced block info string): "
            f"{schema_dir}/schema.yml\n"
            f"\n"
            f"Table profile:\n"
            f"{profile_summary}\n"
            f"\n"
            f"Generate the schema.yml now."
        )

    def validate(self, result: WorkerResult) -> bool:
        return len(result.proposals) > 0

    def extract_metadata(self, response: str, **inputs: Any) -> dict[str, Any]:
        proposals = __import__(
            "tycoon.ai.file_proposals", fromlist=["parse_proposals"]
        ).parse_proposals(response)
        if proposals:
            return {"schema_yml_path": proposals[0].path}
        return {}


class TestFixer(BaseWorker):
    """Fix one specific failing dbt test with the minimal possible change."""

    name = "test-fixer"
    description = "Proposes the minimal fix for a single failing dbt generic test."

    def system_prompt(self) -> str:
        return (
            "You are a dbt debugger. A single dbt test is failing. Your job is to "
            "fix it with the smallest change possible.\n"
            "\n"
            "Rules:\n"
            "1. Fix only the specific failing test — do not touch unrelated tests, "
            "   columns, or SQL logic.\n"
            "2. Do not rename columns, add new tests, or restructure any file.\n"
            "3. Prefer fixing schema.yml over modifying SQL. Only change the model "
            "   SQL if the failure genuinely cannot be resolved in the schema "
            "   (e.g. the column is legitimately nullable in source data).\n"
            "4. Each changed file must be output as a complete fenced code block "
            "   whose info string is the file's relative path "
            "   (e.g. models/staging/schema.yml or models/staging/stg_trips.sql).\n"
            "5. Output only the fenced blocks for files that actually change. "
            "   Do not output unchanged files.\n"
            "6. No prose outside the fenced blocks — only the fixed file content.\n"
            "7. The YAML and SQL you emit must be syntactically valid and complete "
            "   (include the full file content, not just the changed lines).\n"
        )

    def format_request(self, **kwargs: Any) -> str:
        test_name: str = kwargs["test_name"]
        failure_output: str = kwargs["failure_output"]
        model_sql: str = kwargs["model_sql"]
        schema_yaml: str = kwargs["schema_yaml"]

        return (
            f"Failing test: {test_name}\n"
            f"\n"
            f"Failure output:\n"
            f"{failure_output}\n"
            f"\n"
            f"Current schema.yml:\n"
            f"```yaml\n{schema_yaml}\n```\n"
            f"\n"
            f"Current model SQL:\n"
            f"```sql\n{model_sql}\n```\n"
            f"\n"
            f"Propose the minimal fix now."
        )

    def validate(self, result: WorkerResult) -> bool:
        return len(result.proposals) > 0
