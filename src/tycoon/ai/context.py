"""Project context gatherer for the AI assistant.

Collects structured context from the tycoon project — database schemas,
dbt models, source configs, test results — so the LLM can give informed
suggestions about the user's actual data pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb


@dataclass
class TableSchema:
    """Schema for a single database table."""

    schema_name: str
    table_name: str
    columns: list[tuple[str, str]]  # (name, type)
    row_count: int | None = None


@dataclass
class DbtModel:
    """Metadata for a dbt model file."""

    name: str
    path: str
    sql: str


@dataclass
class ProjectContext:
    """All context gathered from a tycoon project."""

    project_name: str = ""
    sources: dict[str, str] = field(default_factory=dict)  # name -> type
    raw_tables: list[TableSchema] = field(default_factory=list)
    warehouse_tables: list[TableSchema] = field(default_factory=list)
    dbt_models: list[DbtModel] = field(default_factory=list)
    dbt_test_results: str = ""


def _get_table_schemas(db_path: Path, max_tables: int = 30) -> list[TableSchema]:
    """Introspect a DuckDB database and return table schemas."""
    if not db_path.exists():
        return []
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        tables = con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
            "ORDER BY table_schema, table_name"
        ).fetchall()

        schemas: list[TableSchema] = []
        for schema_name, table_name in tables[:max_tables]:
            cols = con.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
                [schema_name, table_name],
            ).fetchall()
            try:
                count_row = con.execute(
                    f'SELECT count(*) FROM "{schema_name}"."{table_name}"'
                ).fetchone()
                row_count = count_row[0] if count_row else None
            except duckdb.Error:
                row_count = None
            schemas.append(
                TableSchema(
                    schema_name=schema_name,
                    table_name=table_name,
                    columns=cols,
                    row_count=row_count,
                )
            )
        con.close()
        return schemas
    except duckdb.Error:
        return []


def _get_dbt_models(dbt_dir: Path, max_models: int = 20) -> list[DbtModel]:
    """Read dbt .sql model files from a project directory."""
    if not dbt_dir.exists():
        return []
    models: list[DbtModel] = []
    sql_files = sorted(dbt_dir.rglob("models/**/*.sql"))
    for sql_path in sql_files[:max_models]:
        rel_path = str(sql_path.relative_to(dbt_dir))
        sql_text = sql_path.read_text()
        models.append(
            DbtModel(
                name=sql_path.stem,
                path=rel_path,
                sql=sql_text,
            )
        )
    return models


def _get_dbt_test_results(dbt_dir: Path) -> str:
    """Read the most recent dbt test run_results.json summary, if available."""
    results_path = dbt_dir / "target" / "run_results.json"
    if not results_path.exists():
        return ""
    try:
        import json

        data = json.loads(results_path.read_text())
        results = data.get("results", [])
        if not results:
            return ""
        lines = []
        for r in results:
            status = r.get("status", "unknown")
            node = r.get("unique_id", "unknown")
            if status != "pass":
                msg = r.get("message", "")
                lines.append(f"  {status}: {node}" + (f" — {msg}" if msg else ""))
        if not lines:
            return f"All {len(results)} tests passed."
        return f"{len(lines)} failure(s) out of {len(results)} tests:\n" + "\n".join(lines)
    except Exception:
        return ""


def gather_context(
    project_root: Path,
    raw_db: Path,
    warehouse_db: Path,
    dbt_dir: Path,
    sources: dict | None = None,
    project_name: str = "",
) -> ProjectContext:
    """Gather all available project context."""
    source_map = {}
    if sources:
        for name, src in sources.items():
            source_map[name] = getattr(src, "type", str(src))

    return ProjectContext(
        project_name=project_name,
        sources=source_map,
        raw_tables=_get_table_schemas(raw_db),
        warehouse_tables=_get_table_schemas(warehouse_db),
        dbt_models=_get_dbt_models(dbt_dir),
        dbt_test_results=_get_dbt_test_results(dbt_dir),
    )
