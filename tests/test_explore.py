"""Tests for `tycoon explore` command, dbt_generator, and rill_generator."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
import yaml

from tycoon.cli import app


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a minimal DuckDB database with a test schema and table."""
    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA test_schema")
    con.execute(
        """
        CREATE TABLE test_schema.my_table (
            id INTEGER,
            name VARCHAR,
            amount DOUBLE,
            created_at TIMESTAMP,
            _dlt_load_id VARCHAR,
            _dlt_id VARCHAR
        )
        """
    )
    con.execute(
        "INSERT INTO test_schema.my_table VALUES "
        "(1, 'test', 99.5, '2024-01-01', 'x', 'y')"
    )
    con.close()
    return db_path


@pytest.fixture
def test_db_with_nested(tmp_path: Path) -> Path:
    """DB that also contains a nested dlt table (name with __) and internal tables."""
    db_path = tmp_path / "nested.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA s")
    con.execute(
        """
        CREATE TABLE s.orders (
            order_id INTEGER,
            customer VARCHAR,
            total FLOAT
        )
        """
    )
    # Nested table — should be excluded
    con.execute("CREATE TABLE s.orders__items (item_id INTEGER)")
    # dlt internal table — should be excluded
    con.execute("CREATE TABLE s._dlt_loads (load_id VARCHAR)")
    con.execute("CREATE TABLE s._dlt_pipeline_state (version_hash VARCHAR)")
    con.execute("CREATE TABLE s._dlt_version (engine_version INTEGER)")
    con.close()
    return db_path


# ---------------------------------------------------------------------------
# CLI: explore --help
# ---------------------------------------------------------------------------


class TestExploreHelp:
    """Verify the explore command is registered and shows help."""

    def test_explore_help_exits_zero(self, cli_runner):
        result = cli_runner.invoke(app, ["explore", "--help"])
        assert result.exit_code == 0

    def test_explore_help_shows_options(self, cli_runner):
        result = cli_runner.invoke(app, ["explore", "--help"])
        assert "--no-rill" in result.stdout
        assert "--no-dbt" in result.stdout
        assert "--build" in result.stdout

    def test_explore_appears_in_top_level_help(self, cli_runner):
        result = cli_runner.invoke(app, ["--help"])
        assert "explore" in result.stdout


# ---------------------------------------------------------------------------
# dbt_generator: generate_staging_models
# ---------------------------------------------------------------------------


class TestGenerateStagingModels:
    """Unit tests for the dbt staging model generator."""

    def test_generates_sql_file(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging" / "my_source"
        generated = generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        sql_files = [f for f in generated if f.endswith(".sql")]
        assert len(sql_files) == 1
        assert "stg_my_source__my_table.sql" in sql_files[0]

    def test_sql_file_contains_source_macro(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        sql_path = output_dir / "stg_my_source__my_table.sql"
        content = sql_path.read_text()
        assert "source('my_source', 'my_table')" in content

    def test_sql_file_contains_cte_structure(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        content = (output_dir / "stg_my_source__my_table.sql").read_text()
        assert "with source as" in content
        assert "cleaned as" in content
        assert "select * from cleaned" in content

    def test_generates_yaml_schema_file(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generated = generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        yaml_files = [f for f in generated if f.endswith(".yml")]
        assert len(yaml_files) == 1
        assert "_my_source__models.yml" in yaml_files[0]

    def test_yaml_has_sources_and_models_sections(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        yaml_path = output_dir / "_my_source__models.yml"
        data = yaml.safe_load(yaml_path.read_text())
        assert "sources" in data
        assert "models" in data
        assert data["version"] == 2

    def test_yaml_sources_reference_correct_schema(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        data = yaml.safe_load((output_dir / "_my_source__models.yml").read_text())
        source = data["sources"][0]
        assert source["name"] == "my_source"
        assert source["schema"] == "test_schema"
        assert source["database"] == "raw"
        table_names = [t["name"] for t in source["tables"]]
        assert "my_table" in table_names

    def test_yaml_model_entry_references_stg_name(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        data = yaml.safe_load((output_dir / "_my_source__models.yml").read_text())
        model_names = [m["name"] for m in data["models"]]
        assert "stg_my_source__my_table" in model_names

    def test_dlt_internal_columns_excluded(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        sql_content = (output_dir / "stg_my_source__my_table.sql").read_text()
        assert "_dlt_load_id" not in sql_content
        assert "_dlt_id" not in sql_content

        yaml_data = yaml.safe_load((output_dir / "_my_source__models.yml").read_text())
        for model in yaml_data["models"]:
            col_names = [c["name"] for c in model.get("columns", [])]
            assert "_dlt_load_id" not in col_names
            assert "_dlt_id" not in col_names

    def test_dlt_internal_columns_not_in_yaml_columns(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )

        yaml_data = yaml.safe_load((output_dir / "_my_source__models.yml").read_text())
        model = yaml_data["models"][0]
        col_names = [c["name"] for c in model["columns"]]
        assert "id" in col_names
        assert "name" in col_names
        assert "amount" in col_names
        assert "created_at" in col_names

    def test_nested_tables_excluded(self, tmp_path: Path, test_db_with_nested: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generated = generate_staging_models(
            raw_db_path=test_db_with_nested,
            schema_name="s",
            source_name="src",
            output_dir=output_dir,
        )

        file_names = [Path(f).name for f in generated]
        # orders should be included, orders__items should not
        assert any("stg_src__orders" in n for n in file_names)
        assert not any("items" in n for n in file_names)

    def test_dlt_internal_tables_excluded(self, tmp_path: Path, test_db_with_nested: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        generated = generate_staging_models(
            raw_db_path=test_db_with_nested,
            schema_name="s",
            source_name="src",
            output_dir=output_dir,
        )

        file_names = [Path(f).name for f in generated]
        assert not any("_dlt_" in n for n in file_names)

    def test_creates_output_directory(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "deep" / "nested" / "path"
        assert not output_dir.exists()
        generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )
        assert output_dir.is_dir()

    def test_returns_list_of_paths(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.dbt_generator import generate_staging_models

        output_dir = tmp_path / "staging"
        result = generate_staging_models(
            raw_db_path=test_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=output_dir,
        )
        assert isinstance(result, list)
        assert all(isinstance(p, str) for p in result)


# ---------------------------------------------------------------------------
# rill_generator: generate_rill_config
# ---------------------------------------------------------------------------


class TestGenerateRillConfig:
    """Unit tests for the Rill config generator."""

    def test_creates_connector_yaml(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        connector_path = rill_dir / "connectors" / "duckdb.yaml"
        assert connector_path.exists()

    def test_connector_yaml_attaches_warehouse(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        data = yaml.safe_load((rill_dir / "connectors" / "duckdb.yaml").read_text())
        assert data["type"] == "connector"
        assert data["driver"] == "duckdb"
        assert "ATTACH" in data["init_sql"]
        assert str(warehouse_db.resolve()) in data["init_sql"]

    def test_connector_not_overwritten_if_exists(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        connectors_dir = rill_dir / "connectors"
        connectors_dir.mkdir(parents=True, exist_ok=True)
        connector_path = connectors_dir / "duckdb.yaml"
        original_content = "type: connector\ndriver: duckdb\n"
        connector_path.write_text(original_content)

        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        # Existing connector should not be overwritten
        assert connector_path.read_text() == original_content

    def test_creates_model_yaml(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        model_path = rill_dir / "models" / "stg_my_source__my_table.yaml"
        assert model_path.exists()

    def test_model_yaml_references_staging_view(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        data = yaml.safe_load(
            (rill_dir / "models" / "stg_my_source__my_table.yaml").read_text()
        )
        assert data["type"] == "model"
        assert "stg_my_source__my_table" in data["sql"]
        assert "dbt.main_staging" in data["sql"]

    def test_creates_dashboard_yaml(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        dashboard_path = rill_dir / "dashboards" / "stg_my_source__my_table.yaml"
        assert dashboard_path.exists()

    def test_dashboard_yaml_has_count_measure(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        data = yaml.safe_load(
            (rill_dir / "dashboards" / "stg_my_source__my_table.yaml").read_text()
        )
        assert data["type"] == "explore"
        measure_exprs = [m["expression"] for m in data["measures"]]
        assert "count(*)" in measure_exprs

    def test_returns_list_of_paths(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        result = generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )
        assert isinstance(result, list)
        assert all(isinstance(p, str) for p in result)


# ---------------------------------------------------------------------------
# Column type heuristics
# ---------------------------------------------------------------------------


class TestColumnTypeHeuristics:
    """Verify _classify_column maps SQL types to dimension/measure correctly."""

    def test_varchar_is_dimension(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("VARCHAR") == "dimension"

    def test_text_is_dimension(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("TEXT") == "dimension"

    def test_date_is_dimension(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("DATE") == "dimension"

    def test_timestamp_is_dimension(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("TIMESTAMP") == "dimension"

    def test_boolean_is_dimension(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("BOOLEAN") == "dimension"

    def test_integer_is_sum_measure(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("INTEGER") == "sum_measure"

    def test_bigint_is_sum_measure(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("BIGINT") == "sum_measure"

    def test_float_is_avg_measure(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("FLOAT") == "avg_measure"

    def test_double_is_avg_measure(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("DOUBLE") == "avg_measure"

    def test_decimal_is_avg_measure(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("DECIMAL") == "avg_measure"

    def test_numeric_is_avg_measure(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("NUMERIC") == "avg_measure"

    def test_parameterised_decimal_is_avg_measure(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        # e.g. DECIMAL(10,2)
        assert _classify_column("DECIMAL(10,2)") == "avg_measure"

    def test_parameterised_varchar_is_dimension(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("VARCHAR(255)") == "dimension"

    def test_case_insensitive(self):
        from tycoon.scaffolding.rill_generator import _classify_column

        assert _classify_column("varchar") == "dimension"
        assert _classify_column("integer") == "sum_measure"
        assert _classify_column("double") == "avg_measure"


# ---------------------------------------------------------------------------
# Explore dashboard column classification integration
# ---------------------------------------------------------------------------


class TestExploreDashboardColumns:
    """Verify dashboard YAML correctly classifies columns from test data."""

    def test_varchar_column_is_dimension(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        data = yaml.safe_load(
            (rill_dir / "dashboards" / "stg_my_source__my_table.yaml").read_text()
        )
        dimension_cols = [d["column"] for d in data.get("dimensions", [])]
        assert "name" in dimension_cols

    def test_double_column_is_avg_measure(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        data = yaml.safe_load(
            (rill_dir / "dashboards" / "stg_my_source__my_table.yaml").read_text()
        )
        measure_exprs = [m["expression"] for m in data.get("measures", [])]
        assert "avg(amount)" in measure_exprs

    def test_timestamp_has_type_field(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        data = yaml.safe_load(
            (rill_dir / "dashboards" / "stg_my_source__my_table.yaml").read_text()
        )
        timestamp_dims = [
            d for d in data.get("dimensions", []) if d.get("column") == "created_at"
        ]
        assert timestamp_dims, "created_at should appear as a dimension"
        assert timestamp_dims[0].get("type") == "timestamp"

    def test_dlt_columns_not_in_dashboard(self, tmp_path: Path, test_db: Path):
        from tycoon.scaffolding.rill_generator import generate_rill_config

        warehouse_db = tmp_path / "warehouse.duckdb"
        rill_dir = tmp_path / "rill"
        generate_rill_config(
            raw_db_path=test_db,
            warehouse_db_path=warehouse_db,
            schema_name="test_schema",
            source_name="my_source",
            output_dir=rill_dir,
        )

        data = yaml.safe_load(
            (rill_dir / "dashboards" / "stg_my_source__my_table.yaml").read_text()
        )
        dimension_cols = [d["column"] for d in data.get("dimensions", [])]
        all_measure_exprs = " ".join(m["expression"] for m in data.get("measures", []))
        assert "_dlt_load_id" not in dimension_cols
        assert "_dlt_id" not in dimension_cols
        assert "_dlt_load_id" not in all_measure_exprs
        assert "_dlt_id" not in all_measure_exprs


# ---------------------------------------------------------------------------
# CLI: explore command errors
# ---------------------------------------------------------------------------


class TestExploreCLIErrors:
    """Verify the explore command fails gracefully when prerequisites are missing."""

    def test_explore_fails_without_tycoon_yml(self, cli_runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = cli_runner.invoke(app, ["explore", "my-source"])
        assert result.exit_code != 0

    def test_explore_fails_for_unknown_source(self, cli_runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tycoon.yml").write_text(
            "name: test\nversion: 0.1.0\nsources: {}\n"
        )
        result = cli_runner.invoke(app, ["explore", "nonexistent-source"])
        assert result.exit_code != 0

    def test_explore_fails_when_raw_db_missing(self, cli_runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tycoon_yml = (
            "name: test\n"
            "version: 0.1.0\n"
            "database:\n"
            "  raw: data/raw.duckdb\n"
            "  warehouse: data/warehouse.duckdb\n"
            "sources:\n"
            "  my-src:\n"
            "    type: rest_api\n"
            "    schema: raw_my_src\n"
        )
        (tmp_path / "tycoon.yml").write_text(tycoon_yml)
        # Do NOT create the raw db
        result = cli_runner.invoke(app, ["explore", "my-src"])
        assert result.exit_code != 0
