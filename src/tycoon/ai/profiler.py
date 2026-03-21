"""Lightweight data profiler for the AI worker factory.

Runs targeted SQL queries against DuckDB to produce column-level statistics
that workers use to make informed decisions — null handling, test generation,
column documentation, type validation.

All functions are read-only and safe to run against production databases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb


@dataclass
class ColumnProfile:
    """Statistics for a single column."""

    name: str
    data_type: str
    row_count: int
    null_count: int
    distinct_count: int
    sample_values: list[str] = field(default_factory=list)

    # Numeric stats (None for non-numeric columns)
    min_value: float | None = None
    max_value: float | None = None
    mean_value: float | None = None

    @property
    def null_rate(self) -> float:
        """Fraction of rows that are NULL (0.0 – 1.0)."""
        if self.row_count == 0:
            return 0.0
        return self.null_count / self.row_count

    @property
    def is_likely_pk(self) -> bool:
        """Heuristic: likely a primary key if no nulls and all distinct."""
        return self.null_count == 0 and self.distinct_count == self.row_count and self.row_count > 0

    @property
    def is_low_cardinality(self) -> bool:
        """Heuristic: suitable for accepted_values test if <= 20 distinct values."""
        return 0 < self.distinct_count <= 20

    def summary(self) -> str:
        """One-line human-readable summary for LLM context."""
        parts = [
            f"type={self.data_type}",
            f"nulls={self.null_rate:.0%}",
            f"distinct={self.distinct_count}",
        ]
        if self.is_likely_pk:
            parts.append("likely_pk=true")
        if self.is_low_cardinality and self.sample_values:
            vals = ", ".join(repr(v) for v in self.sample_values[:5])
            parts.append(f"values=[{vals}]")
        elif self.min_value is not None:
            parts.append(f"range={self.min_value}–{self.max_value}")
        return f"{self.name}: {', '.join(parts)}"


@dataclass
class TableProfile:
    """Column-level statistics for an entire table."""

    schema_name: str
    table_name: str
    row_count: int
    columns: list[ColumnProfile]

    def summary(self) -> str:
        """Multi-line summary suitable for inclusion in an LLM prompt."""
        lines = [
            f"Table: {self.schema_name}.{self.table_name} ({self.row_count:,} rows)",
        ]
        for col in self.columns:
            lines.append(f"  {col.summary()}")
        return "\n".join(lines)

    def get_column(self, name: str) -> ColumnProfile | None:
        return next((c for c in self.columns if c.name == name), None)


_NUMERIC_TYPES = {"INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "SMALLINT", "TINYINT"}


def profile_table(
    db_path: Path,
    schema_name: str,
    table_name: str,
    sample_limit: int = 5,
) -> TableProfile | None:
    """Profile a single table in a DuckDB database.

    Returns None if the table does not exist or the database is unreachable.
    """
    if not db_path.exists():
        return None

    try:
        con = duckdb.connect(str(db_path), read_only=True)
        fqn = f'"{schema_name}"."{table_name}"'

        # Total row count
        row_count_row = con.execute(f"SELECT count(*) FROM {fqn}").fetchone()
        row_count = row_count_row[0] if row_count_row else 0

        if row_count == 0:
            con.close()
            return TableProfile(
                schema_name=schema_name,
                table_name=table_name,
                row_count=0,
                columns=[],
            )

        # Column metadata
        col_rows = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
            [schema_name, table_name],
        ).fetchall()

        columns: list[ColumnProfile] = []
        for col_name, data_type in col_rows:
            safe_col = f'"{col_name}"'

            # Null count
            null_row = con.execute(
                f"SELECT count(*) FROM {fqn} WHERE {safe_col} IS NULL"
            ).fetchone()
            null_count = null_row[0] if null_row else 0

            # Distinct count
            try:
                dist_row = con.execute(
                    f"SELECT count(DISTINCT {safe_col}) FROM {fqn}"
                ).fetchone()
                distinct_count = dist_row[0] if dist_row else 0
            except duckdb.Error:
                distinct_count = 0

            # Sample values (non-null)
            try:
                samples = con.execute(
                    f"SELECT DISTINCT CAST({safe_col} AS VARCHAR) FROM {fqn} "
                    f"WHERE {safe_col} IS NOT NULL LIMIT {sample_limit}"
                ).fetchall()
                sample_values = [str(r[0]) for r in samples]
            except duckdb.Error:
                sample_values = []

            # Numeric stats
            min_val = max_val = mean_val = None
            base_type = data_type.upper().split("(")[0].strip()
            if base_type in _NUMERIC_TYPES:
                try:
                    stats = con.execute(
                        f"SELECT min({safe_col}), max({safe_col}), avg({safe_col}) FROM {fqn}"
                    ).fetchone()
                    if stats:
                        min_val = float(stats[0]) if stats[0] is not None else None
                        max_val = float(stats[1]) if stats[1] is not None else None
                        mean_val = float(stats[2]) if stats[2] is not None else None
                except duckdb.Error:
                    pass

            columns.append(ColumnProfile(
                name=col_name,
                data_type=data_type,
                row_count=row_count,
                null_count=null_count,
                distinct_count=distinct_count,
                sample_values=sample_values,
                min_value=min_val,
                max_value=max_val,
                mean_value=mean_val,
            ))

        con.close()
        return TableProfile(
            schema_name=schema_name,
            table_name=table_name,
            row_count=row_count,
            columns=columns,
        )

    except duckdb.Error:
        return None
