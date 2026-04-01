# tests/

pytest test suite for the tycoon package.

---

## Running Tests

```bash
uv run pytest
```

Run a specific file:

```bash
uv run pytest tests/test_cli.py
```

Run with verbose output:

```bash
uv run pytest -v
```

---

## Test Coverage

| File | What It Tests |
|---|---|
| `test_cli.py` | CLI entrypoint, command registration, help output |
| `test_config.py` | Path resolution, project root detection, config loading |
| `test_project.py` | Pydantic model parsing and validation for `tycoon.yml` |
| `test_ingestion.py` | dlt pipeline runner, source loading, ingestion execution |
| `test_sources.py` | Catalog fetching, source install/remove, source manager state |
| `test_init.py` | Project scaffolding — directory structure and file generation |
| `test_check.py` | Project validation checks (config, dbt state, source connectivity) |
| `test_db_command.py` | DuckDB shell command invocation |
| `test_explore.py` | Table and schema browsing logic |
| `test_services.py` | Shared service layer (dbt runner, duckdb client) |
| `test_server.py` | FastAPI server routes and responses |
| `test_utils.py` | Shared utility functions |
| `test_constants.py` | Package constant values |
| `test_ai.py` | AI assistant integration |
| `test_ai_context.py` | AI context building from project state |
| `test_ai_fix.py` | AI-assisted fix suggestions |
| `test_ai_memory.py` | AI session memory handling |
| `test_ai_proposals.py` | AI proposal generation and parsing |
| `test_ai_repl.py` | AI REPL interaction loop |
| `conftest.py` | Shared fixtures (temp project directories, mock configs) |
