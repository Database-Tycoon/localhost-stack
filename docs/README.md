# docs/

Developer documentation and setup scripts for the tycoon project.

---

## Contents

### `install_rill.sh`

Shell script for installing the Rill CLI on macOS or Linux. Run this once to get the `rill` binary available on your PATH. The tycoon CLI uses `rill start` under the hood when you run `tycoon serve`, so Rill must be installed for that command to work.

```bash
bash docs/install_rill.sh
```

### `rebuild_local_stack.md`

Step-by-step instructions for tearing down and rebuilding the full local stack from scratch. Covers resetting DuckDB files, re-running ingestion, re-running dbt, and restarting Rill. Useful when switching between demo data and real sources, or when recovering from a broken pipeline state.
