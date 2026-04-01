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

# 2. Add a data source (no auth — uses PokeAPI by default)
tycoon data sources add rest_api

# 3. Ingest data
tycoon data ingest run pokeapi

# 4. Transform with dbt
tycoon data transform run

# 5. Start dashboards, Dagster, Nao, and the web UI
tycoon start
```

---

## CLI Reference

| Command | Description |
|---|---|
| `tycoon init` | Scaffold a new project |
| `tycoon data sources catalog` | Browse available source integrations |
| `tycoon data sources add <type>` | Register a new data source |
| `tycoon data sources install <name>` | Download and install a source's dlt package |
| `tycoon data sources list` | List sources configured in this project |
| `tycoon data ingest run <name>` | Run ingestion for a named source |
| `tycoon data ingest all` | Run ingestion for all sources |
| `tycoon data transform run` | Run dbt transformations |
| `tycoon data explore <source>` | Scaffold dbt models and Rill dashboards for a source |
| `tycoon data db query <sql>` | Run a SQL query against the warehouse |
| `tycoon data setup` | Run the built-in NYC demo setup |
| `tycoon start` | Start Rill, Dagster, Nao, and the web UI |
| `tycoon stop` | Stop all services |
| `tycoon ai fix` | Auto-fix failing dbt tests with AI |
| `tycoon ai pipeline <name>` | Run a named AI worker pipeline |
| `tycoon ai ask chat` | Query your data in natural language (Nao) |
| `tycoon run <tool>` | Passthrough to dbt, dlt, rill, dagster |

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

These sources are available via `tycoon data sources add <name>`. They are downloaded on demand via `dlt init` and not bundled in the package.

| Source | Category | Key Tables |
|---|---|---|
| `github` | Developer | commits, issues, pull_requests, repositories |
| `slack` | Communication | channels, messages, users |
| `stripe` | Finance | customers, invoices, products, subscriptions |
| `hubspot` | CRM | companies, contacts, deals, tickets |
| `notion` | Knowledge | databases, pages, users |

---

## Data Directory

Raw DuckDB files follow the naming convention `raw_<source>.duckdb` (written by ingestion) while `warehouse.duckdb` is the single transformed database read by Rill and Nao. See `data/README.md` for details.

---

## Rill Dashboards

Rill is a local-first BI tool that reads directly from DuckDB. Dashboard definitions are YAML files in the `rill/` directory. Launch Rill via `tycoon start` or `tycoon start --only rill`.

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
tycoon ai ask init
tycoon ai ask sync
tycoon ai ask chat
```
