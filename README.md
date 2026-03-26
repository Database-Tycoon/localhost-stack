# tycoon

A pip-installable CLI for local-first data analytics. No Docker, no cloud account required. Point it at a data source, run three commands, and get a working dashboard.

**Pipeline**: dlt (ingestion) → DuckDB (raw) → dbt (transformation) → DuckDB (warehouse) → Rill (dashboards) + Nao (AI queries)

---

## Install

```bash
pip install tycoon
# or
uv add tycoon
```

For Dagster orchestration:

```bash
pip install "tycoon[dagster]"
```

For AI natural language queries:

```bash
pip install "tycoon[ask]"
```

Requirements: Python >= 3.12

---

## Quickstart

```bash
# 1. Initialize a new project
tycoon init my-project
cd my-project

# 2. Add a data source
tycoon sources add github

# 3. Ingest data
tycoon ingest run github

# 4. Transform with dbt
tycoon transform run

# 5. Open dashboards
tycoon serve
```

---

## CLI Reference

| Command | Description |
|---|---|
| `tycoon init` | Scaffold a new tycoon project with tycoon.yml and directory structure |
| `tycoon sources catalog` | List all available sources in the catalog |
| `tycoon sources add <name>` | Download a source via `dlt init` into `~/.tycoon/sources/` |
| `tycoon sources install` | Install Python dependencies for all configured sources |
| `tycoon sources list` | List sources configured in the current project |
| `tycoon sources show <name>` | Show configuration details for a source |
| `tycoon sources remove <name>` | Remove a source from the project |
| `tycoon ingest run <name>` | Run ingestion pipeline for a named source |
| `tycoon ingest all` | Run ingestion for all configured sources |
| `tycoon transform run` | Run dbt transformations against the warehouse DuckDB |
| `tycoon ask init` | Initialize Nao configuration for AI queries |
| `tycoon ask sync` | Sync dbt metadata to Nao |
| `tycoon ask chat` | Start an interactive AI query session |
| `tycoon serve` | Launch Rill dashboard server |
| `tycoon db` | Open an interactive DuckDB shell on the warehouse |
| `tycoon check` | Validate project config, source connectivity, and dbt state |
| `tycoon ai` | Open the tycoon AI assistant (project-aware) |
| `tycoon explore` | Browse available tables and schemas interactively |

---

## tycoon.yml Reference

```yaml
name: my-project
version: 0.1.0

database:
  raw: data/raw.duckdb         # dlt output — one file per source by default
  warehouse: data/warehouse.duckdb  # dbt output — read by Rill and Nao

dbt_project_dir: dbt_project   # path to the dbt project directory
rill_dir: rill                 # path to Rill dashboard definitions

sources:
  my-github:
    type: github               # matches a catalog source name
    schema: raw_github         # schema name in the raw DuckDB file
    config:
      access_token: ${GITHUB_TOKEN}   # env vars are interpolated
      owner: my-org
      repo: my-repo

ask:                           # optional — requires tycoon[ask]
  llm:
    provider: ollama           # fully local, no API key required
  port: 5005
```

Each source produces its own raw DuckDB file: `data/raw_<source>.duckdb`. All sources write into `data/warehouse.duckdb` after transformation.

---

## Catalog Sources

These sources are available via `tycoon sources add <name>`. They are downloaded on demand via `dlt init` and not bundled in the package.

| Source | Category | Key Tables |
|---|---|---|
| `github` | Developer | commits, issues, pull_requests, repositories |
| `slack` | Communication | channels, messages, users |
| `stripe` | Finance | customers, invoices, products, subscriptions |
| `hubspot` | CRM | companies, contacts, deals, tickets |
| `notion` | Knowledge | databases, pages, users |

---

## Optional Extras

### Dagster orchestration (`tycoon[dagster]`)

Installs Dagster, dagster-dbt, and dagster-dlt. Provides a full asset graph covering ingestion and transformation. Run the Dagster UI with:

```bash
dagster dev
```

The workspace is defined in `workspace.yaml` at the project root.

### AI queries (`tycoon[ask]`)

Installs Nao and Ibis for natural language querying of the warehouse. Requires a running LLM — Ollama (local) is supported out of the box with no API key.

```bash
tycoon ask init
tycoon ask sync
tycoon ask chat
```

---

## Contributing / Dev Setup

```bash
git clone <repo>
cd localhost-stack
uv sync
uv run pytest
```

The dev group includes pytest. Source code lives in `src/tycoon/`. The CLI entrypoint is `tycoon.cli:app` as defined in `pyproject.toml`.

To test a local install:

```bash
uv run tycoon --help
```
