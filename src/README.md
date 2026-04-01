# src/tycoon

This directory contains the `tycoon` Python package. It is installed as the `tycoon` CLI via the entrypoint defined in `pyproject.toml`:

```toml
[project.scripts]
tycoon = "tycoon.cli:app"
```

The package is built with hatchling and requires Python >= 3.12.

---

## Package Structure

| Path | Description |
|---|---|
| `cli.py` | Typer application root — registers all sub-apps and handles global flags |
| `config.py` | Path resolution and project root detection |
| `project.py` | Pydantic models for parsing and validating `tycoon.yml` |
| `nao.py` | Generates Nao configuration from the project's dbt metadata |
| `constants.py` | Package-wide constants (default paths, catalog URL, etc.) |
| `dbt.py` | Helpers for invoking dbt programmatically |
| `commands/` | One module per CLI sub-app (see below) |
| `ingestion/` | dlt pipeline management: catalog, source installer, runner |
| `orchestration/` | Dagster asset definitions and resource configuration |
| `ai/` | AI assistant integration |
| `server/` | FastAPI server backing `tycoon serve` and `tycoon ask` |
| `services/` | Shared service logic (dbt runner, duckdb client, etc.) |
| `scaffolding/` | Project scaffolding logic for `tycoon init` |
| `templates/` | File templates used during project initialization |
| `utils/` | Shared utility functions |

---

## commands/

Each file in `commands/` maps to a top-level CLI sub-app:

| File | CLI Command |
|---|---|
| `init.py` | `tycoon init` |
| `sources.py` | `tycoon sources` |
| `ingest.py` | `tycoon ingest` |
| `transform.py` | `tycoon transform` |
| `ask.py` | `tycoon ask` |
| `serve.py` | `tycoon serve` |
| `db.py` | `tycoon db` |
| `check.py` | `tycoon check` |
| `ai.py` | `tycoon ai` |
| `explore.py` | `tycoon explore` |
| `demo.py` | `tycoon demo` (NYC transit demo dataset) |
| `setup.py` | `tycoon setup` (post-install configuration) |

---

## ingestion/

| File | Description |
|---|---|
| `catalog.py` | Fetches and parses the tycoon source catalog |
| `source_manager.py` | Manages source state in `~/.tycoon/sources/` |
| `source_installer.py` | Runs `dlt init` to download a source on demand |
| `runner.py` | Executes dlt pipelines for configured sources |
| `sources/` | Local source implementations (e.g., MTA, NYC DOT) |

---

## orchestration/

Dagster definitions. Only active when `tycoon[dagster]` is installed.

| File | Description |
|---|---|
| `definitions.py` | Top-level Dagster `Definitions` object |
| `resources.py` | Dagster resource definitions (DuckDB, dbt) |
| `assets/` | Individual Dagster asset definitions per pipeline stage |
