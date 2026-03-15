"""tycoon setup — orchestrate full environment setup."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Annotated

import typer

from tycoon.config import config
from tycoon.utils.console import console, header, info, success, error, warn
from tycoon.utils.duckdb_utils import db_file_size_mb, remove_wal


def _run(cmd: list[str], description: str) -> None:
    """Run a subprocess command, streaming output. Abort on failure."""
    info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        error(f"{description} failed (exit code {result.returncode})")
        raise typer.Exit(1)
    success(f"{description} complete")


def setup_cmd(
    quick: Annotated[
        bool,
        typer.Option(
            "--quick",
            help="Ingest only 5000 records per dataset; skip 2023-2024 bus speeds.",
        ),
    ] = False,
    full: Annotated[
        bool,
        typer.Option(
            "--full",
            help="Ingest all records (default behavior).",
        ),
    ] = False,
    skip_ingest: Annotated[
        bool,
        typer.Option(
            "--skip-ingest",
            help="Skip ingestion; only run dbt.",
        ),
    ] = False,
) -> None:
    """Orchestrate a full environment setup: ingest data, then build dbt models."""
    header("Tycoon Environment Setup")
    start = time.time()

    if quick and full:
        error("Cannot specify both --quick and --full.")
        raise typer.Exit(1)

    mode = "quick" if quick else "full"
    info(f"Mode: {mode}" + (" (skip-ingest)" if skip_ingest else ""))

    # 1. Ensure data directory exists
    info("Ensuring data directory exists...")
    config.ensure_data_dir()
    success(f"Data directory: {config.data_dir}")

    # 2. Remove stale WAL files
    for db_path, label in [(config.raw_db, "raw"), (config.local_db, "local")]:
        if remove_wal(db_path):
            warn(f"Removed stale WAL file for {label} database")

    tycoon_bin = [sys.executable, "-m", "tycoon"]

    # 3. Ingestion
    if not skip_ingest:
        if not config.has_project_file or not config.sources:
            error("No tycoon.yml or no sources registered. Run 'tycoon init' and 'tycoon sources add' first.")
            raise typer.Exit(1)

        sources = config.sources
        total = len(sources)
        ingest_flags: list[str] = []
        if quick:
            ingest_flags = ["--max-records", "5000"]

        for i, name in enumerate(sources, 1):
            console.rule(f"[bold cyan]Step {i}/{total} — {name}")
            _run(
                [*tycoon_bin, "ingest", "run", name, *ingest_flags],
                f"{name} ingestion",
            )
    else:
        info("Skipping ingestion (--skip-ingest)")

    # 4. dbt build
    if config.dbt_project_dir.exists():
        console.rule("[bold cyan]dbt Build")
        _run(
            [
                "dbt",
                "build",
                "--project-dir",
                str(config.dbt_project_dir),
                "--profiles-dir",
                str(config.dbt_project_dir),
            ],
            "dbt build",
        )
    else:
        info("No dbt project found, skipping transform step.")

    # 5. Summary
    elapsed = time.time() - start
    console.rule("[bold green]Setup Complete")

    raw_size = db_file_size_mb(config.raw_db)
    local_size = db_file_size_mb(config.local_db)
    info(f"Raw database:   {raw_size:.1f} MB" if raw_size else "Raw database:   not found")
    info(f"Local database: {local_size:.1f} MB" if local_size else "Local database: not found")
    success(f"Setup finished in {elapsed:.1f}s")
