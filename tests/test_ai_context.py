"""Tests for tycoon ai context gathering and prompt construction."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from tycoon.ai.context import (
    DbtModel,
    ProjectContext,
    TableSchema,
    _get_dbt_models,
    _get_dbt_test_results,
    _get_table_schemas,
    gather_context,
)
from tycoon.ai.prompts import _MAX_CHARS, build_system_prompt


# ---------------------------------------------------------------------------
# TableSchema
# ---------------------------------------------------------------------------


class TestTableSchema:
    def test_basic_fields(self):
        ts = TableSchema(
            schema_name="raw",
            table_name="events",
            columns=[("id", "BIGINT"), ("name", "VARCHAR")],
            row_count=100,
        )
        assert ts.schema_name == "raw"
        assert ts.table_name == "events"
        assert len(ts.columns) == 2
        assert ts.row_count == 100

    def test_row_count_defaults_none(self):
        ts = TableSchema(schema_name="s", table_name="t", columns=[])
        assert ts.row_count is None


# ---------------------------------------------------------------------------
# DbtModel
# ---------------------------------------------------------------------------


class TestDbtModel:
    def test_basic_fields(self):
        m = DbtModel(name="stg_events", path="models/staging/stg_events.sql", sql="SELECT 1")
        assert m.name == "stg_events"
        assert m.sql == "SELECT 1"


# ---------------------------------------------------------------------------
# ProjectContext
# ---------------------------------------------------------------------------


class TestProjectContext:
    def test_defaults(self):
        ctx = ProjectContext()
        assert ctx.project_name == ""
        assert ctx.sources == {}
        assert ctx.raw_tables == []
        assert ctx.warehouse_tables == []
        assert ctx.dbt_models == []
        assert ctx.dbt_test_results == ""


# ---------------------------------------------------------------------------
# _get_table_schemas
# ---------------------------------------------------------------------------


class TestGetTableSchemas:
    def test_reads_schema_from_duckdb(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("CREATE SCHEMA raw")
        con.execute("CREATE TABLE raw.events (id BIGINT, name VARCHAR)")
        con.execute("INSERT INTO raw.events VALUES (1, 'a'), (2, 'b')")
        con.close()

        schemas = _get_table_schemas(db_path)
        assert len(schemas) == 1
        assert schemas[0].schema_name == "raw"
        assert schemas[0].table_name == "events"
        assert schemas[0].row_count == 2
        assert ("id", "BIGINT") in schemas[0].columns
        assert ("name", "VARCHAR") in schemas[0].columns

    def test_returns_empty_for_missing_db(self, tmp_path):
        assert _get_table_schemas(tmp_path / "missing.duckdb") == []

    def test_respects_max_tables(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        con = duckdb.connect(str(db_path))
        for i in range(10):
            con.execute(f"CREATE TABLE t{i:02d} (x INT)")
        con.close()

        schemas = _get_table_schemas(db_path, max_tables=3)
        assert len(schemas) == 3

    def test_multiple_schemas(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("CREATE SCHEMA alpha")
        con.execute("CREATE SCHEMA beta")
        con.execute("CREATE TABLE alpha.a (x INT)")
        con.execute("CREATE TABLE beta.b (y VARCHAR)")
        con.close()

        schemas = _get_table_schemas(db_path)
        schema_names = {s.schema_name for s in schemas}
        assert "alpha" in schema_names
        assert "beta" in schema_names


# ---------------------------------------------------------------------------
# _get_dbt_models
# ---------------------------------------------------------------------------


class TestGetDbtModels:
    def test_reads_sql_files(self, tmp_path):
        models_dir = tmp_path / "models" / "staging"
        models_dir.mkdir(parents=True)
        (models_dir / "stg_events.sql").write_text("SELECT * FROM {{ source('raw', 'events') }}")
        (models_dir / "stg_trips.sql").write_text("SELECT * FROM {{ source('raw', 'trips') }}")

        models = _get_dbt_models(tmp_path)
        assert len(models) == 2
        names = {m.name for m in models}
        assert "stg_events" in names
        assert "stg_trips" in names

    def test_returns_empty_for_missing_dir(self, tmp_path):
        assert _get_dbt_models(tmp_path / "nonexistent") == []

    def test_respects_max_models(self, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir(parents=True)
        for i in range(10):
            (models_dir / f"m{i:02d}.sql").write_text(f"SELECT {i}")

        models = _get_dbt_models(tmp_path, max_models=3)
        assert len(models) == 3

    def test_ignores_non_sql_files(self, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "schema.yml").write_text("version: 2")
        (models_dir / "stg_events.sql").write_text("SELECT 1")

        models = _get_dbt_models(tmp_path)
        assert len(models) == 1
        assert models[0].name == "stg_events"


# ---------------------------------------------------------------------------
# _get_dbt_test_results
# ---------------------------------------------------------------------------


class TestGetDbtTestResults:
    def test_reads_passing_results(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        data = {
            "results": [
                {"unique_id": "test.not_null", "status": "pass"},
                {"unique_id": "test.unique", "status": "pass"},
            ]
        }
        (target / "run_results.json").write_text(json.dumps(data))

        result = _get_dbt_test_results(tmp_path)
        assert "All 2 tests passed" in result

    def test_reads_failing_results(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        data = {
            "results": [
                {"unique_id": "test.not_null", "status": "pass"},
                {"unique_id": "test.unique_id", "status": "fail", "message": "duplicate found"},
            ]
        }
        (target / "run_results.json").write_text(json.dumps(data))

        result = _get_dbt_test_results(tmp_path)
        assert "1 failure(s)" in result
        assert "test.unique_id" in result
        assert "duplicate found" in result

    def test_returns_empty_when_no_results(self, tmp_path):
        assert _get_dbt_test_results(tmp_path) == ""

    def test_returns_empty_for_empty_results(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        (target / "run_results.json").write_text(json.dumps({"results": []}))

        assert _get_dbt_test_results(tmp_path) == ""


# ---------------------------------------------------------------------------
# gather_context
# ---------------------------------------------------------------------------


class TestGatherContext:
    def test_gathers_full_context(self, tmp_path):
        # Create a raw database
        raw_db = tmp_path / "raw.duckdb"
        con = duckdb.connect(str(raw_db))
        con.execute("CREATE SCHEMA src")
        con.execute("CREATE TABLE src.users (id INT, name VARCHAR)")
        con.execute("INSERT INTO src.users VALUES (1, 'Alice')")
        con.close()

        # Create a dbt project with a model
        dbt_dir = tmp_path / "dbt_project"
        models_dir = dbt_dir / "models" / "staging"
        models_dir.mkdir(parents=True)
        (models_dir / "stg_users.sql").write_text("SELECT * FROM {{ source('src', 'users') }}")

        ctx = gather_context(
            project_root=tmp_path,
            raw_db=raw_db,
            warehouse_db=tmp_path / "warehouse.duckdb",
            dbt_dir=dbt_dir,
            project_name="test-project",
        )

        assert ctx.project_name == "test-project"
        assert len(ctx.raw_tables) == 1
        assert ctx.raw_tables[0].table_name == "users"
        assert ctx.warehouse_tables == []
        assert len(ctx.dbt_models) == 1
        assert ctx.dbt_models[0].name == "stg_users"

    def test_handles_empty_project(self, tmp_path):
        ctx = gather_context(
            project_root=tmp_path,
            raw_db=tmp_path / "raw.duckdb",
            warehouse_db=tmp_path / "warehouse.duckdb",
            dbt_dir=tmp_path / "dbt",
        )
        assert ctx.raw_tables == []
        assert ctx.dbt_models == []


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_includes_header(self):
        ctx = ProjectContext()
        prompt = build_system_prompt(ctx)
        assert "data pipeline assistant" in prompt
        assert "dlt" in prompt
        assert "dbt" in prompt

    def test_includes_project_name(self):
        ctx = ProjectContext(project_name="my-project")
        prompt = build_system_prompt(ctx)
        assert "my-project" in prompt

    def test_includes_sources(self):
        ctx = ProjectContext(sources={"events": "rest_api", "files": "filesystem"})
        prompt = build_system_prompt(ctx)
        assert "events" in prompt
        assert "rest_api" in prompt

    def test_includes_test_results(self):
        ctx = ProjectContext(dbt_test_results="1 failure(s): test.unique_id")
        prompt = build_system_prompt(ctx)
        assert "1 failure(s)" in prompt

    def test_includes_raw_tables(self):
        ctx = ProjectContext(
            raw_tables=[
                TableSchema(
                    schema_name="raw",
                    table_name="events",
                    columns=[("id", "BIGINT"), ("name", "VARCHAR")],
                    row_count=42,
                )
            ]
        )
        prompt = build_system_prompt(ctx)
        assert "raw.events" in prompt
        assert "42" in prompt
        assert "BIGINT" in prompt

    def test_includes_dbt_models(self):
        ctx = ProjectContext(
            dbt_models=[
                DbtModel(
                    name="stg_events",
                    path="models/staging/stg_events.sql",
                    sql="SELECT * FROM {{ source('raw', 'events') }}",
                )
            ]
        )
        prompt = build_system_prompt(ctx)
        assert "stg_events" in prompt
        assert "source('raw', 'events')" in prompt

    def test_respects_budget(self):
        # Create a context with lots of data
        big_tables = [
            TableSchema(
                schema_name="raw",
                table_name=f"table_{i}",
                columns=[(f"col_{j}", "VARCHAR") for j in range(50)],
                row_count=1000,
            )
            for i in range(50)
        ]
        ctx = ProjectContext(raw_tables=big_tables)
        prompt = build_system_prompt(ctx)
        assert len(prompt) <= _MAX_CHARS + 100  # small overflow tolerance for truncation message

    def test_empty_context_still_produces_prompt(self):
        ctx = ProjectContext()
        prompt = build_system_prompt(ctx)
        assert len(prompt) > 100
        assert "data pipeline assistant" in prompt
