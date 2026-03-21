"""System prompt construction for the AI assistant.

Builds a context-rich system prompt from gathered project context,
staying within a ~4K token budget (~16K chars).
"""

from __future__ import annotations

from tycoon.ai.context import ProjectContext

_MAX_CHARS = 16_000  # ~4K tokens


def _format_table_schema(tables: list, label: str) -> str:
    """Format table schemas into a compact text block."""
    if not tables:
        return ""
    lines = [f"\n## {label}\n"]
    for t in tables:
        row_info = f" ({t.row_count:,} rows)" if t.row_count is not None else ""
        lines.append(f"### {t.schema_name}.{t.table_name}{row_info}")
        for col_name, col_type in t.columns:
            lines.append(f"  - {col_name}: {col_type}")
    return "\n".join(lines)


def _format_dbt_models(models: list) -> str:
    """Format dbt model SQL into a compact text block."""
    if not models:
        return ""
    lines = ["\n## dbt Models\n"]
    for m in models:
        lines.append(f"### {m.name} ({m.path})")
        lines.append(f"```sql\n{m.sql.strip()}\n```")
    return "\n".join(lines)


def build_system_prompt(ctx: ProjectContext) -> str:
    """Build the system prompt from project context, respecting the token budget."""
    sections: list[str] = []

    # Header
    header = "You are a data pipeline assistant for a local-first analytics project"
    if ctx.project_name:
        header += f" called '{ctx.project_name}'"
    header += "."
    header += (
        "\n\nThe stack uses: dlt (ingestion) → DuckDB (storage) → dbt (transforms). "
        "You help maintain and improve the data pipeline — writing dbt models, "
        "dlt pipeline code, diagnosing test failures, and suggesting schema changes."
        "\n\nAlways respond with specific, actionable suggestions based on the "
        "project context below. When proposing file changes, use fenced code blocks "
        "with the target file path as the language identifier."
    )
    sections.append(header)

    # Project memory (persistent decisions — high value for the LLM)
    if ctx.ai_memory:
        sections.append(
            "\n## Project Memory (persistent decisions and notes)\n\n" + ctx.ai_memory.strip()
        )

    # Sources
    if ctx.sources:
        source_lines = ["\n## Registered Sources\n"]
        for name, stype in ctx.sources.items():
            source_lines.append(f"- **{name}**: {stype}")
        sections.append("\n".join(source_lines))

    # Test results (high priority — failures need attention)
    if ctx.dbt_test_results:
        sections.append(f"\n## dbt Test Results\n\n{ctx.dbt_test_results}")

    # Build remaining sections, trimming if needed
    raw_schema = _format_table_schema(ctx.raw_tables, "Raw Database Schema")
    warehouse_schema = _format_table_schema(ctx.warehouse_tables, "Warehouse Database Schema")
    dbt_section = _format_dbt_models(ctx.dbt_models)

    # Assemble within budget
    prompt = "\n".join(sections)
    remaining = _MAX_CHARS - len(prompt)

    # Add schemas (prioritize raw over warehouse)
    if raw_schema and remaining > len(raw_schema):
        prompt += raw_schema
        remaining -= len(raw_schema)

    if warehouse_schema and remaining > len(warehouse_schema):
        prompt += warehouse_schema
        remaining -= len(warehouse_schema)

    # Add dbt models last (they can be large)
    if dbt_section and remaining > len(dbt_section):
        prompt += dbt_section
    elif dbt_section and remaining > 200:
        # Truncate dbt models to fit
        prompt += dbt_section[:remaining - 50] + "\n\n(... truncated for context budget)"

    return prompt
