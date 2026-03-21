"""Staging layer AI workers for the tycoon worker factory.

Four focused workers that operate on dbt staging models:

- StagingImprover    — refactor a staging model to follow dbt conventions
- NullHandler        — add COALESCE / NULLIF for columns with high null rates
- ColumnDocumenter   — generate dbt column descriptions for schema.yml
- ColumnRenamer      — propose and apply a snake_case rename plan

All workers are stateless. Inputs are passed explicitly on every call.
"""

from __future__ import annotations

from typing import Any

from tycoon.ai.file_proposals import parse_proposals
from tycoon.ai.workers.base import BaseWorker, WorkerResult


class StagingImprover(BaseWorker):
    """Review and improve a staging model SQL.

    Applies dbt staging conventions: type casting, null coalescing,
    consistent snake_case naming, and clean SELECT structure without
    introducing any business logic.
    """

    name = "staging-improver"
    description = "Refactor a staging model to follow dbt staging conventions."

    def system_prompt(self) -> str:
        return """\
You are a dbt SQL expert specializing in staging layer models.

Your job is to improve an existing staging model SQL to follow dbt best practices.

Rules:
- Staging models are 1:1 with their source table. Do NOT add business logic.
- Do NOT change the model grain (no aggregations, no joins to other sources).
- Apply these conventions:
  - Prefix the model with `stg_` (already handled by the file path).
  - Rename columns to snake_case.
  - Cast columns to appropriate types (e.g. VARCHAR → TEXT, NUMERIC → DECIMAL).
  - Add COALESCE for non-nullable columns with sensible defaults.
  - Remove duplicate SELECT items or SELECT *.
  - Use consistent indentation: 4 spaces per level.
- Do NOT add window functions, CTEs for business logic, or derived metrics.
- Keep comments minimal: only add a comment if a transform is non-obvious.

Output format:
- Return the complete improved SQL in a single fenced block.
- Use the model path as the info string: `models/staging/stg_{model_name}.sql`
- Do not output anything after the fenced block.
"""

    def format_request(self, **kwargs: Any) -> str:
        model_name: str = kwargs["model_name"]
        model_sql: str = kwargs["model_sql"]
        profile_summary: str = kwargs["profile_summary"]
        return f"""\
Model name: {model_name}

Source table profile:
{profile_summary}

Current SQL:
```sql
{model_sql}
```

Improve this staging model following the conventions in the system prompt. \
Return the complete updated SQL in a fenced block with path \
`models/staging/stg_{model_name}.sql` as the info string.
"""

    def validate(self, result: WorkerResult) -> bool:
        return len(result.proposals) > 0

    def extract_metadata(self, response: str, **inputs: Any) -> dict[str, Any]:
        proposals = parse_proposals(response)
        if proposals:
            return {"improved_model_path": proposals[0].path}
        return {}


class NullHandler(BaseWorker):
    """Add null-handling expressions to columns that exceed a null-rate threshold.

    Only modifies the SELECT clause. FROM / JOIN structure is left untouched.
    """

    name = "null-handler"
    description = "Add COALESCE / NULLIF for high-null columns in a staging model."

    def system_prompt(self) -> str:
        return """\
You are a dbt SQL expert focused on data quality in staging models.

Your job is to add null handling to a staging model for columns whose null rate \
exceeds the threshold provided by the user.

Rules:
- Only modify columns whose null_rate exceeds the given threshold.
- Prefer COALESCE with sensible defaults:
  - Numeric columns → COALESCE(col, 0)
  - String columns  → COALESCE(col, '')
  - Boolean columns → COALESCE(col, false)
  - Timestamp / date columns → leave nullable unless context is clear.
- For columns that are intentionally nullable (e.g. optional foreign keys, \
  reason codes), keep them as-is and add a line comment `-- nullable by design`.
- Minimal change: only touch the SELECT clause. Do NOT rewrite FROM, JOIN, \
  WHERE, GROUP BY, or any CTE structure.
- Preserve indentation and column order.

Output format:
- Return the full updated SQL in a single fenced block.
- Use the model path as the info string: `models/staging/stg_{model_name}.sql`
- Do not output anything after the fenced block.
"""

    def format_request(self, **kwargs: Any) -> str:
        model_name: str = kwargs["model_name"]
        model_sql: str = kwargs["model_sql"]
        profile_summary: str = kwargs["profile_summary"]
        null_threshold: float = kwargs.get("null_threshold", 0.1)
        threshold_pct = f"{null_threshold:.0%}"
        return f"""\
Model name: {model_name}
Null rate threshold: {threshold_pct} (handle columns above this rate)

Source table profile:
{profile_summary}

Current SQL:
```sql
{model_sql}
```

Add null handling for every column whose null rate exceeds {threshold_pct}. \
Return the complete updated SQL in a fenced block with path \
`models/staging/stg_{model_name}.sql` as the info string.
"""

    def validate(self, result: WorkerResult) -> bool:
        return len(result.proposals) > 0


class ColumnDocumenter(BaseWorker):
    """Generate dbt column-level descriptions and write them into schema.yml.

    Merges with an existing schema.yml if one is provided.
    """

    name = "column-documenter"
    description = "Generate dbt column descriptions and produce an updated schema.yml."

    def system_prompt(self) -> str:
        return """\
You are a dbt documentation expert.

Your job is to write clear, accurate column descriptions for a dbt staging model \
and produce a complete schema.yml file.

Rules:
- Write exactly one sentence per column description. Be concise.
- Use column name, data type, and sample values to infer meaning.
- Do NOT guess or hallucinate meaning. If the column purpose is unclear, \
  use the placeholder: "Column description pending."
- If an existing schema.yml is provided, merge your descriptions into it. \
  Preserve any existing descriptions that are already accurate.
- Descriptions must be plain text — no markdown formatting inside the YAML string.
- The output schema.yml must be valid YAML.

Output path rules:
- Use `models/staging/schema.yml` unless you can infer a different path from \
  the existing YAML content (e.g. it already lives at a different location).

Output format:
- Return the complete schema.yml in a single fenced block.
- Use the resolved path as the info string (e.g. `models/staging/schema.yml`).
- Do not output anything after the fenced block.
"""

    def format_request(self, **kwargs: Any) -> str:
        model_name: str = kwargs["model_name"]
        profile_summary: str = kwargs["profile_summary"]
        existing_schema_yaml: str = kwargs.get("existing_schema_yaml", "")

        existing_section = (
            f"Existing schema.yml:\n```yaml\n{existing_schema_yaml}\n```"
            if existing_schema_yaml.strip()
            else "No existing schema.yml provided — create one from scratch."
        )

        return f"""\
Model name: {model_name}

Source table profile:
{profile_summary}

{existing_section}

Write column descriptions for the `{model_name}` model and return a complete \
schema.yml in a fenced block using the appropriate path as the info string.
"""

    def validate(self, result: WorkerResult) -> bool:
        return len(result.proposals) > 0

    def extract_metadata(self, response: str, **inputs: Any) -> dict[str, Any]:
        proposals = parse_proposals(response)
        return {"documented_columns": len(proposals)}


class ColumnRenamer(BaseWorker):
    """Propose and apply a column rename plan for a staging model.

    Outputs two fenced blocks: a markdown rename plan and the updated SQL.
    """

    name = "column-renamer"
    description = "Propose snake_case renames and apply them to a staging model."

    def system_prompt(self) -> str:
        return """\
You are a dbt SQL expert focused on consistent, readable column naming.

Your job is to review a staging model and propose renames for columns that are \
abbreviated, ambiguous, or inconsistently named.

Rename targets:
- Convert all column names to snake_case.
- Expand abbreviations: `amt` → `amount`, `dt` → `date`, `cnt` → `count`, etc.
- Disambiguate generic names: `id` → `{entity}_id`, `name` → `{entity}_name`, etc.
- Only rename if genuinely necessary. If a name is already clear, leave it alone.

Output format — always two fenced blocks in this order:

1. A markdown table summarising the rename plan:
   | old_name | new_name | reason |
   Use info string: `rename_plan.md`

2. The updated SQL with all renames applied as column aliases (AS new_name):
   Use info string: `models/staging/stg_{model_name}.sql`

If no renames are needed:
- State that clearly in prose before the blocks.
- Still output both blocks: an empty rename table and the SQL unchanged.

Do not output anything after the second fenced block.
"""

    def format_request(self, **kwargs: Any) -> str:
        model_name: str = kwargs["model_name"]
        model_sql: str = kwargs["model_sql"]
        profile_summary: str = kwargs["profile_summary"]
        return f"""\
Model name: {model_name}

Source table profile:
{profile_summary}

Current SQL:
```sql
{model_sql}
```

Review the column names and propose renames following the rules in the system prompt. \
Output a `rename_plan.md` fenced block followed by the updated SQL fenced block \
with path `models/staging/stg_{model_name}.sql`.
"""

    def validate(self, result: WorkerResult) -> bool:
        return len(result.proposals) > 0

    def extract_metadata(self, response: str, **inputs: Any) -> dict[str, Any]:
        proposals = parse_proposals(response)
        # subtract 1 for the rename_plan.md doc; floor at 0
        rename_count = max(0, len(proposals) - 1)
        return {"rename_count": rename_count}
