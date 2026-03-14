"""tycoon check — health check for the local stack."""

from __future__ import annotations

import typer

from tycoon.config import config
from tycoon.constants import PORTS
from tycoon.utils.console import console, status_table, success, warn, error, header
from tycoon.utils.duckdb_utils import db_file_size_mb, get_tables, get_row_count
from tycoon.utils.process import is_port_in_use, command_exists

app = typer.Typer(help="Health check for the local stack.")


@app.callback(invoke_without_command=True)
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info"),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues"),
) -> None:
    """Run health checks on databases, ports, and tools."""
    header("Tycoon Stack Health Check")
    rows: list[tuple[str, str, str]] = []
    issues = 0

    # -- Project root --
    if (config.root / "pyproject.toml").exists():
        rows.append(("Project root", "OK", str(config.root)))
    else:
        rows.append(("Project root", "FAIL", "pyproject.toml not found"))
        issues += 1

    # -- Data directory --
    if config.data_dir.exists():
        rows.append(("Data directory", "OK", str(config.data_dir)))
    else:
        if fix:
            config.ensure_data_dir()
            rows.append(("Data directory", "OK", "created"))
        else:
            rows.append(("Data directory", "WARN", "missing (run tycoon setup or --fix)"))

    # -- Raw database --
    raw_size = db_file_size_mb(config.raw_db)
    if raw_size is not None:
        rows.append(("Raw database", "OK", f"{raw_size:.1f} MB"))
        if verbose:
            for schema, table in get_tables(config.raw_db):
                count = get_row_count(config.raw_db, schema, table)
                rows.append((f"  {schema}.{table}", "OK", f"{count:,} rows" if count else "empty"))
    else:
        rows.append(("Raw database", "WARN", "not found — run tycoon ingest"))

    # -- Local (transformed) database --
    local_size = db_file_size_mb(config.local_db)
    if local_size is not None:
        rows.append(("Local database", "OK", f"{local_size:.1f} MB"))
        if verbose:
            for schema, table in get_tables(config.local_db):
                count = get_row_count(config.local_db, schema, table)
                rows.append((f"  {schema}.{table}", "OK", f"{count:,} rows" if count else "empty"))
    else:
        rows.append(("Local database", "WARN", "not found — run tycoon transform build"))

    # -- Port availability --
    for name, port in PORTS.items():
        if is_port_in_use(port):
            rows.append((f"Port {port} ({name})", "WARN", "in use"))
        else:
            rows.append((f"Port {port} ({name})", "OK", "available"))

    # -- Required tools --
    for tool in ["uv", "duckdb"]:
        if command_exists(tool):
            rows.append((f"Tool: {tool}", "OK", "found"))
        else:
            rows.append((f"Tool: {tool}", "FAIL", "not found"))
            issues += 1

    # -- Optional tools --
    for tool in ["rill"]:
        if command_exists(tool):
            rows.append((f"Tool: {tool}", "OK", "found"))
        else:
            rows.append((f"Tool: {tool}", "WARN", "not found (optional)"))

    # -- dbt project --
    if config.dbt_project_dir.exists():
        rows.append(("dbt project", "OK", str(config.dbt_project_dir)))
    else:
        rows.append(("dbt project", "WARN", "not found"))

    console.print(status_table(rows))

    if issues:
        error(f"{issues} issue(s) found")
        raise typer.Exit(1)
    else:
        success("All checks passed")
