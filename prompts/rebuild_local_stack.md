# Prompt: Rebuild the NYC Open Data Local-First Analytics Stack

You are an expert data engineer tasked with rebuilding a **fully local, zero-cloud-dependency analytics stack** for NYC public transit and traffic data. This stack was originally built for a conference talk ("A (More) Modern Data Stack" — DataTune Nashville 2026) under the brand **Database Tycoon**. The entire system runs on a single laptop with no cloud accounts, no SaaS subscriptions, and no authentication tokens required.

---

## Philosophy

The core principle is **local-first**: every tool in the stack runs as a local process, reads/writes local files, and requires zero network access after the initial data fetch from public APIs. Cloud storage (S3) exists as an optional upgrade path but is never the default. The stack proves that modern data engineering tooling — ingestion, transformation, testing, semantic layers, dashboards, and a control plane — can all operate at professional quality on a laptop.

---

## Architecture Overview

```
Public APIs  →  dlt (Python)  →  DuckDB (raw)  →  dbt (SQL)  →  DuckDB (transformed)  →  Rill (dashboards)
                                                                                          ↑
                                                                               Tycoon UI (FastAPI control plane)
```

### Tool Selection Rationale

| Layer | Tool | Why This Tool |
|-------|------|---------------|
| **Ingestion** | dlt (data load tool) | Python-native, declarative resources, handles pagination/schema evolution, writes directly to DuckDB or DuckLake |
| **Raw Storage** | DuckDB (plain file) | Single-file database, no server process, read-only attachable from dbt |
| **Transformation** | dbt-core + dbt-duckdb | SQL-based transformations, 154 tests, MetricFlow semantic layer, mature ecosystem |
| **Analytics DB** | DuckDB (second file) | In-process OLAP, columnar, fast aggregations on 18M+ rows |
| **Dashboards** | Rill | Open-source BI that reads DuckDB natively, no SaaS dependency |
| **Control Plane** | Tycoon (FastAPI + embedded SPA) | Unified UI for launching pipelines, running dbt, monitoring service health, streaming logs via WebSocket |
| **Package Manager** | uv | Fast Python dependency resolution, replaces pip/poetry, runs everything via `uv run` |
| **Data Validation** | Recce (OSS) | Schema diff and row count comparison between dbt target branches |

---

## Data Sources (All Free, Public APIs)

### 1. NYC DOT Traffic Data
- **Traffic Speeds NBE** (dataset `i4gi-tjb9`): Real-time expressway sensor data from NYC Open Data (`data.cityofnewyork.us`)
- **Bus Lanes** (dataset `ycrg-ses3`): Dedicated bus lane locations
- **Traffic Volume Counts** (dataset `7ym2-wayt`): Historical traffic volume at specific segments

### 2. MTA GTFS Static Feeds
- **Source**: `https://rrgtfsfeeds.s3.amazonaws.com` (publicly hosted S3)
- **Feeds**: Bronx, Brooklyn, Manhattan, Queens, Staten Island, MTA Bus Company
- **Tables**: `gtfs_routes`, `gtfs_stops` (core); `gtfs_trips`, `gtfs_shapes` (optional, large)

### 3. MTA Bus Segment Speeds (The Big Dataset)
- **Source**: NY State Open Data (`data.ny.gov`) — note: different domain from NYC Open Data
- **2023–2024** (dataset `58t6-89vi`): ~11.7M rows
- **2025** (dataset `kufs-yh3x`): ~6.3M rows
- **Grain**: route × segment × month × day_of_week × hour_of_day
- **Content**: Actual bus speeds between timepoints (major stops), not just expressway sensors

---

## Project Structure

```
nyc_data/
├── pyproject.toml                         # uv-managed Python deps
├── CLAUDE.md                              # Project documentation
├── recce.yml                              # Data validation preset checks
│
├── ingestion/nyc_open_data/               # dlt pipelines (Python)
│   ├── nyc_dot_pipeline.py                # Traffic speeds, bus lanes, volume counts
│   ├── mta_pipeline.py                    # GTFS routes & stops
│   ├── mta_bus_speeds_pipeline.py         # Bus segment speeds (18M rows)
│   └── ducklake_config.py                 # S3/DuckLake config (optional cloud path)
│
├── transformation/                        # dbt project
│   ├── dbt_project.yml                    # Project config, materialization settings
│   ├── profiles.yml                       # 4 targets: local, s3, offline, recce
│   └── models/
│       ├── staging/                       # 5 models — clean raw data
│       │   ├── mta_bus_speeds/            # stg_mta_bus_speeds__segment_speeds
│       │   ├── mta/                       # stg_mta__bus_routes, stg_mta__bus_stops
│       │   └── nyc_dot/                   # stg_nyc_dot__bus_lanes, stg_nyc_dot__traffic_volume_counts
│       ├── intermediate/                  # 3 models — business logic
│       │   └── bus_analytics/             # int_representative_dates, int_segment_bus_lane_match, int_traffic_volume_hourly
│       ├── marts/
│       │   ├── core/                      # 4 dimensions: dim_date, dim_time_of_day, dim_bus_segments, dim_bus_lanes
│       │   ├── bus_analytics/             # 4 facts + 12 reports
│       │   └── reports/                   # Additional report models
│       └── semantic/                      # MetricFlow semantic models + time spine
│
├── rill/                                  # Rill BI dashboards
│   ├── rill.yaml                          # Project config
│   ├── connectors/duckdb.yaml             # DuckDB connection (absolute path to local DB)
│   ├── models/                            # Source definitions (8 models)
│   └── dashboards/                        # 4 interactive dashboards
│
├── scripts/                               # Orchestration
│   ├── setup_local.sh                     # One-command full setup
│   ├── start_demo.sh                      # Launch all 6 services
│   ├── check_stack.sh                     # Pre-demo health check
│   ├── tycoon_server.py                   # FastAPI control plane (port 8888)
│   ├── benchmark.sh                       # Performance profiling
│   └── recce_validate.sh                  # Data validation workflow
│
├── nyc_open_data_raw.duckdb               # Raw data (written by dlt)
├── nyc_open_data_local.duckdb             # Transformed data (written by dbt)
└── ducklake_data/                         # Parquet files (DuckLake local mode)
```

---

## Layer 1: Ingestion (dlt Pipelines)

### Design Pattern

Each pipeline follows the same pattern:
1. Define `@dlt.resource` functions that yield records from public APIs
2. Group resources into a `@dlt.source`
3. In `run_pipeline()`, select destination based on `--local` flag:
   - **Local**: `dlt.destinations.duckdb("nyc_open_data_raw.duckdb")` — plain DuckDB, no catalog overhead
   - **S3**: `get_ducklake_destination()` — DuckLake with S3 Parquet backend
4. CLI with argparse: `--local`, `--max-records N`, `--skip-2023-2024`, etc.

### Socrata API Pagination

The bus speeds pipeline implements pagination for Socrata's SODA API:
- Page size: 50,000 records
- Ordered by `:id` for consistency
- Yields individual records (dlt handles batching)
- Progress printed to stdout every page
- `--max-records` flag caps total for testing

### Pipeline Execution Order (CRITICAL)

DuckDB allows **only one writer** at a time per file. Pipelines MUST run sequentially:

```bash
uv run python ingestion/nyc_open_data/nyc_dot_pipeline.py --local         # Step 1
uv run python ingestion/nyc_open_data/mta_pipeline.py --local             # Step 2
uv run python ingestion/nyc_open_data/mta_bus_speeds_pipeline.py --local  # Step 3
```

### Raw Database Schema

All three pipelines write to `nyc_open_data_raw.duckdb` with separate schemas:
- `raw_nyc_dot`: `traffic_speeds_nbe`, `bus_lanes`, `traffic_volume_counts`
- `raw_mta`: `gtfs_routes`, `gtfs_stops`
- `raw_mta_bus_speeds`: `bus_segment_speeds_2023_2024`, `bus_segment_speeds_2025`

---

## Layer 2: Transformation (dbt)

### Profile Configuration

The key architectural decision is the **dual-database pattern**: dbt reads from the raw DuckDB (attached read-only) and writes to a separate local DuckDB.

```yaml
# transformation/profiles.yml
nyc_open_data:
  target: local
  outputs:
    local:
      type: duckdb
      path: "nyc_open_data_local.duckdb"       # dbt writes here
      extensions:
        - parquet
      attach:
        - path: "nyc_open_data_raw.duckdb"      # raw data, read-only
          alias: raw
          read_only: true
```

**Critical path resolution note**: `dbt-duckdb` resolves the `path` field relative to the **CWD where dbt is invoked**, NOT relative to `--profiles-dir`. Since we run dbt from the project root, all paths in `profiles.yml` are relative to the project root.

### Materialization Strategy

| Layer | Materialized As | Schema | Rationale |
|-------|----------------|--------|-----------|
| Staging | `view` | `main_staging` | Lightweight, always reads fresh raw data |
| Intermediate | `view` | `main_intermediate` | Business logic, doesn't need persistence |
| Marts (dims + facts) | `table` | `main_marts` | Core analytics tables, need performance |
| Semantic | `table` | `main_semantic` | MetricFlow requires materialized tables |

### Dimensional Model

**Facts** are lean — measures + foreign keys only. Descriptive attributes live in dimensions.

**Core Dimensions:**
- `dim_date`: Generated calendar (2022–2026) with holidays, seasons, NYC school calendar, fiscal year
- `dim_time_of_day`: 24 hours with named periods (am_peak, midday, pm_peak, evening, overnight)
- `dim_bus_segments`: Route segments between timepoints, with coordinates
- `dim_bus_lanes`: Bus lane infrastructure with location metadata
- `dim_bus_routes`: MTA route definitions with borough derivation
- `dim_bus_stops`: MTA stop locations

**Fact Tables:**
- `fct_bus_segment_speeds`: The central fact — route × segment × metric_date × time_period. Measures: avg/min/max/median speed, speed variability, travel time, trip counts
- `fct_route_daily_performance`: Route-level reliability grades (A–F)
- `fct_corridor_performance`: Corridor aggregates with bus lane matching
- `fct_traffic_volume_patterns`: Traffic volume by segment and time period
- `fct_segment_speeds_hourly`: Hourly grain for detailed analysis

**Report Models (12):** Pre-joined, analysis-ready views that combine facts + dimensions for specific analyses (bottlenecks, equity, seasonal patterns, bus lane effectiveness, etc.)

### Key Data Quality Patterns

1. **Deduplication**: Source bus speeds data has duplicate rows. Staging deduplicates with:
   ```sql
   qualify row_number() over (
     partition by segment_speed_id
     order by data_source desc
   ) = 1
   ```

2. **Representative Dates**: Source data is pre-aggregated by day_of_week (not actual calendar dates). `metric_date` in facts maps to the first occurrence of that day_of_week in the month, enabling MetricFlow time-based aggregation.

3. **Borough Derivation**: Borough extracted from route name prefix (e.g., "Q46" → Queens, "Bx1" → Bronx).

4. **Surrogate Keys**: MD5 hashes from natural key columns for fact table grain enforcement.

### Running dbt

```bash
uv run dbt run --project-dir transformation --profiles-dir transformation
uv run dbt test --project-dir transformation --profiles-dir transformation
uv run dbt run -s fct_bus_segment_speeds+ --project-dir transformation --profiles-dir transformation
```

---

## Layer 3: Dashboards (Rill)

Rill connects directly to the transformed DuckDB file via an `init_sql` that ATTACHes it:

```yaml
# rill/connectors/duckdb.yaml
type: connector
driver: duckdb
managed: true
init_sql: |
  ATTACH '/absolute/path/to/nyc_open_data_local.duckdb' AS dbt (READ_ONLY);
```

**4 Dashboards:**
1. Bus Segment Speeds — speed analysis by route, borough, time of day
2. Route Performance — reliability grades, bottleneck identification
3. Corridor Performance — street-level analysis with bus lane impact
4. Traffic Volume — traffic counts by segment and time period

```bash
~/.rill/rill start rill/    # http://localhost:9009
```

---

## Layer 4: Control Plane (Tycoon)

Tycoon is a **FastAPI server with an embedded single-page application** that serves as the unified control plane for the entire stack.

### Architecture

```
FastAPI (port 8888)
├── GET  /              → Serves the SPA (single HTML page with embedded CSS/JS)
├── GET  /api/status    → Live status of all services, databases, dbt results
├── POST /api/run/pipeline/{id}  → Spawn a dlt pipeline subprocess
├── POST /api/run/dbt   → Spawn a dbt command subprocess
└── WS   /ws/logs/{run_id}  → Real-time log streaming from subprocess stdout
```

### Key Design Decisions

1. **Single-writer enforcement**: The `_runs` dict tracks active subprocesses. Only one pipeline or dbt command can run at a time (DuckDB constraint).

2. **Subprocess + asyncio**: Pipelines run as `uv run python ...` subprocesses. Stdout is piped through an async iterator and streamed to the browser via WebSocket.

3. **Status polling**: The SPA polls `/api/status` every 5 seconds. Status includes:
   - Service health (port checks for all 5 services)
   - Database file sizes (raw DB, local DB, Parquet directory)
   - Row counts from key raw and transformed tables
   - dbt last-run results (parsed from `transformation/target/run_results.json`)

4. **Embedded SPA**: The entire frontend is a single HTML string in `tycoon_server.py` — no build step, no npm, no bundler. Dark mode UI with sidebar navigation, dashboard grid, pipeline cards, terminal output, and service iframe viewer.

5. **Service embedding**: Services like dlt UI, dbt docs, Recce, and Rill load in an iframe. DuckDB UI opens in a new tab (it blocks iframes). X-Frame-Options detection with graceful fallback.

---

## Layer 5: Orchestration Scripts

### `setup_local.sh` — Full Setup From Scratch

```bash
./scripts/setup_local.sh              # Full: all 18M rows
./scripts/setup_local.sh --quick      # Demo: 5K records, skip 2023-24
```

Steps: dlt DOT → dlt MTA → dlt Bus Speeds → dbt run. Removes stale DuckDB WAL before dbt.

### `start_demo.sh` — Launch All Services

Starts 6 processes, stores PIDs in `.demo_pids`, waits for each port, prints status:
1. dlt UI (port 2718) — `dlt pipeline show`
2. DuckDB UI (port 4213) — `CALL start_ui_server()` via DuckDB CLI
3. dbt docs (port 8080) — `dbt docs serve`
4. Recce (port 8000) — `recce server` (only if `target-base/` exists)
5. Rill (port 9009) — `rill start rill/`
6. Tycoon (port 8888) — `uvicorn tycoon_server.py`

Trap on SIGINT/SIGTERM kills all processes and cleans up ports.

### `check_stack.sh` — Pre-Demo Health Check

Validates: database files exist and exceed minimum sizes, required tables have minimum row counts, service ports are available. Exit code 0 = ready to present.

---

## Dependencies

```toml
# pyproject.toml
[project]
requires-python = ">=3.12"
dependencies = [
    "dbt-core>=1.9.0",
    "dbt-duckdb>=1.9.0",
    "dlt[ducklake,workspace]>=1.0.0",
    "dbt-metricflow[dbt-duckdb]>=0.11.0",
    "recce>=0.46.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
]

[dependency-groups]
dev = ["pytest>=8.0.0", "sqlfluff>=3.0.0"]

[tool.uv]
prerelease = "if-necessary-or-explicit"
```

---

## Storage Targets

| Target | Write DB | Read From | Cloud? | Use Case |
|--------|----------|-----------|--------|----------|
| `local` (default) | `nyc_open_data_local.duckdb` | `nyc_open_data_raw.duckdb` (attached read-only) | No | Development, demos |
| `s3` | `nyc_open_data_local.duckdb` | `ducklake:ducklake_catalog.duckdb` (DuckLake → S3 Parquet) | AWS | Durable storage |
| `offline` | `nyc_open_data_local.duckdb` | Self (no attach) | No | Read-only analysis after any dbt run |
| `recce` | `nyc_open_data_local.duckdb` | Self (no attach) | No | Data validation tool |

---

## Critical Constraints

1. **DuckDB single-writer**: Only one process can write to a DuckDB file at a time. Never run parallel pipelines. The Tycoon control plane enforces this.

2. **Path resolution**: dbt-duckdb resolves paths from CWD, not from `--profiles-dir`. All profile paths must be relative to the project root.

3. **Sequential pipeline execution**: DOT → MTA → Bus Speeds, always in that order when targeting the same raw DuckDB file.

4. **MotherDuck lock conflict**: If MotherDuck MCP server (Claude Desktop) has attached a local DuckDB file, it holds a persistent read-write lock. Detach or close before running pipelines or dbt.

5. **DuckLake attach syntax**: DuckLake stores absolute DATA_PATH internally — omit `DATA_PATH` when re-attaching; let it use the stored path. DuckLake extension loads from the main repo (`LOAD ducklake`), NOT community.

---

## Rebuild Checklist

1. **Environment**: Install uv, Python 3.12+, DuckDB CLI, Rill CLI
2. **Dependencies**: `uv sync` from project root
3. **Ingestion**: Run all 3 dlt pipelines with `--local` flag sequentially
4. **Transformation**: `uv run dbt run` + `uv run dbt test` from project root
5. **Dashboards**: Update Rill connector with correct absolute path, then `rill start rill/`
6. **Control plane**: `uv run python scripts/tycoon_server.py`
7. **Full demo**: `./scripts/start_demo.sh` (starts all 6 services)
8. **Validation**: `./scripts/check_stack.sh` (verifies everything is healthy)

---

## Statistics (Reference)

- Raw source rows: **18.2M** (11.7M bus speeds 2023–24 + 6.3M bus speeds 2025 + 216K reference)
- Parquet on disk: **3.4 GB**
- DuckDB transformed: **3.9 GB**
- dbt models: **33** (5 staging, 3 intermediate, 6 dims, 5 facts, 12 reports, 2 semantic)
- dbt tests: **154**
- Build time: **~75 seconds** on Apple M4 Pro
- Data range: 2023-01-01 to 2026-01-07
