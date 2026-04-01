# rill/

This directory contains the Rill project definition for tycoon dashboards.

Rill is a local-first BI tool that reads directly from DuckDB and renders dashboards defined as YAML files. No server setup or separate database connection is required beyond a running DuckDB file.

---

## Launching

The recommended way to start Rill is via the tycoon CLI:

```bash
tycoon serve
```

You can also start it directly if Rill is installed:

```bash
rill start
```

Rill will be available at `http://localhost:9009` by default.

To install the Rill CLI separately, see `docs/install_rill.sh`.

---

## Directory Structure

| Path | Description |
|---|---|
| `rill.yaml` | Top-level Rill project configuration |
| `connectors/` | DuckDB connector definitions — points to `data/warehouse.duckdb` |
| `models/` | SQL or YAML model definitions that Rill uses as the base for dashboards |
| `dashboards/` | Dashboard definitions (YAML) — one file per dashboard |
| `tmp/` | Rill working directory, auto-generated, gitignored |

---

## How It Works

1. `connectors/duckdb.yaml` defines the connection to `data/warehouse.duckdb`.
2. `models/` defines the metrics layer — dimensions, measures, and the underlying SQL.
3. `dashboards/` defines what the user sees: charts, filters, and time controls.

Models and dashboards reference the mart tables produced by `tycoon transform run`. Run transformations before launching Rill to ensure all tables exist.
