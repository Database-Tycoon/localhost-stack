"""Auto-generate Rill connector configs, models, and explore dashboards.

Given a raw DuckDB database and a warehouse DuckDB path, generates:
- connectors/duckdb.yaml (ATTACH warehouse DB, created only if missing)
- models/<model_name>.yaml (one per staged table)
- dashboards/<model_name>.yaml (one explore dashboard per staged table)
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import yaml


# dlt internal columns excluded from dashboard generation
_DLT_INTERNAL_COLUMNS = {
    "_dlt_load_id",
    "_dlt_id",
    "_dlt_parent_id",
    "_dlt_list_idx",
}

# dlt internal tables excluded entirely
_DLT_INTERNAL_TABLES = {
    "_dlt_loads",
    "_dlt_pipeline_state",
    "_dlt_version",
}

# Column type heuristics
_DIMENSION_TYPES = {
    "VARCHAR",
    "TEXT",
    "CHAR",
    "DATE",
    "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE",
    "TIMESTAMPTZ",
    "BOOLEAN",
    "BOOL",
}

_SUM_MEASURE_TYPES = {
    "INTEGER",
    "INT",
    "INT4",
    "INT2",
    "BIGINT",
    "INT8",
    "SMALLINT",
    "TINYINT",
    "HUGEINT",
    "UBIGINT",
    "UINTEGER",
    "USMALLINT",
    "UTINYINT",
}

_AVG_MEASURE_TYPES = {
    "FLOAT",
    "FLOAT4",
    "FLOAT8",
    "DOUBLE",
    "DOUBLE PRECISION",
    "REAL",
    "DECIMAL",
    "NUMERIC",
    "NUMBER",
}


def _classify_column(data_type: str) -> str:
    """Return 'dimension', 'sum_measure', or 'avg_measure' for a SQL data type."""
    upper = data_type.upper().strip()
    # Handle parameterised types like DECIMAL(10,2), VARCHAR(255)
    base = upper.split("(")[0].strip()
    if base in _DIMENSION_TYPES:
        return "dimension"
    if base in _SUM_MEASURE_TYPES:
        return "sum_measure"
    if base in _AVG_MEASURE_TYPES:
        return "avg_measure"
    # Default unknown types to dimension (safe fallback)
    return "dimension"


def _title_label(name: str) -> str:
    """Convert a snake_case column name to Title Case label."""
    return " ".join(word.capitalize() for word in name.replace("_", " ").split())


def _generate_connector_yaml(warehouse_db_path: Path) -> str:
    """Generate the duckdb.yaml connector content."""
    data = {
        "type": "connector",
        "driver": "duckdb",
        "managed": True,
        "init_sql": f"ATTACH '{warehouse_db_path.resolve()}' AS dbt (READ_ONLY);",
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def _generate_model_yaml(model_name: str, source_name: str, table_name: str) -> str:
    """Generate a Rill model YAML that reads from the dbt staging view."""
    data = {
        "type": "model",
        "connector": "duckdb",
        "sql": f"SELECT * FROM dbt.main_staging.stg_{source_name}__{table_name}",
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def _generate_explore_yaml(
    model_name: str,
    table_name: str,
    source_name: str,
    columns: list[tuple[str, str]],
) -> str:
    """Generate a Rill explore dashboard YAML with auto-detected dimensions/measures."""
    dimensions = []
    measures = []

    # Always include count(*) measure first
    measures.append(
        {
            "expression": "count(*)",
            "label": "Record Count",
            "format": "#,##0",
        }
    )

    for col_name, data_type in columns:
        clean = col_name.lower().replace(" ", "_")
        label = _title_label(clean)
        kind = _classify_column(data_type)

        upper = data_type.upper().strip()
        base = upper.split("(")[0].strip()

        if kind == "dimension":
            entry: dict = {"column": clean, "label": label}
            if base in {"DATE", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ"}:
                entry["type"] = "timestamp"
            dimensions.append(entry)
        elif kind == "sum_measure":
            measures.append(
                {
                    "expression": f"sum({clean})",
                    "label": f"Sum {label}",
                    "format": "#,##0",
                }
            )
        elif kind == "avg_measure":
            measures.append(
                {
                    "expression": f"avg({clean})",
                    "label": f"Avg {label}",
                    "format": "#,##0.00",
                }
            )

    data = {
        "type": "explore",
        "title": table_name,
        "description": f"Auto-generated explore for {source_name}/{table_name}",
        "model": model_name,
        "dimensions": dimensions,
        "measures": measures,
    }

    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def generate_rill_config(
    raw_db_path: Path,
    warehouse_db_path: Path,
    schema_name: str,
    source_name: str,
    output_dir: Path,
) -> list[str]:
    """Generate Rill connector, models, and explore dashboards.

    output_dir should be the rill/ directory.

    Creates:
    - connectors/duckdb.yaml (if not exists) — ATTACH warehouse DB
    - models/<model_name>.yaml — one per staged table
    - dashboards/<model_name>.yaml — one explore dashboard per table

    Returns list of generated file paths (as strings).
    """
    generated: list[str] = []

    # Ensure subdirectories exist
    connectors_dir = output_dir / "connectors"
    models_dir = output_dir / "models"
    dashboards_dir = output_dir / "dashboards"
    for d in (connectors_dir, models_dir, dashboards_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Connector — only create if missing
    connector_path = connectors_dir / "duckdb.yaml"
    if not connector_path.exists():
        connector_path.write_text(_generate_connector_yaml(warehouse_db_path))
        generated.append(str(connector_path))

    # Introspect schema to discover tables and columns
    if not raw_db_path.exists():
        return generated

    con = duckdb.connect(str(raw_db_path), read_only=True)
    try:
        table_rows = con.execute(
            """
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = ?
            ORDER BY table_name
            """,
            [schema_name],
        ).fetchall()
    finally:
        con.close()

    raw_table_names = [
        row[0]
        for row in table_rows
        if row[0] not in _DLT_INTERNAL_TABLES and "__" not in row[0]
    ]

    if not raw_table_names:
        return generated

    con = duckdb.connect(str(raw_db_path), read_only=True)
    try:
        for table_name in raw_table_names:
            col_rows = con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name = ?
                ORDER BY ordinal_position
                """,
                [schema_name, table_name],
            ).fetchall()
            columns = [
                (col_name, data_type)
                for col_name, data_type in col_rows
                if col_name not in _DLT_INTERNAL_COLUMNS
            ]
            if not columns:
                continue

            model_name = f"stg_{source_name}__{table_name}"

            # Model YAML
            model_path = models_dir / f"{model_name}.yaml"
            model_path.write_text(_generate_model_yaml(model_name, source_name, table_name))
            generated.append(str(model_path))

            # Explore dashboard YAML
            dashboard_path = dashboards_dir / f"{model_name}.yaml"
            dashboard_path.write_text(
                _generate_explore_yaml(model_name, table_name, source_name, columns)
            )
            generated.append(str(dashboard_path))
    finally:
        con.close()

    return generated
