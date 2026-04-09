"""tycoon setup — orchestrate full environment setup."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Annotated

import typer

from tycoon.config import config
from tycoon.utils.console import console, header, info, next_steps, success, error, warn
from tycoon.utils.duckdb_utils import remove_wal


def _run(cmd: list[str], description: str) -> None:
    """Run a subprocess command, streaming output. Abort on failure."""
    info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        error(f"{description} failed (exit code {result.returncode})")
        raise typer.Exit(1)
    success(f"{description} complete")


def setup_cmd(
    max_records: Annotated[
        int,
        typer.Option(
            "--max-records",
            help="Limit ingestion to N records per dataset. Omit for all records.",
        ),
    ] = 0,
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

    mode = f"max {max_records:,} records" if max_records else "full"
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
        ingest_flags = ["--max-records", str(max_records)] if max_records else []

        for i, name in enumerate(sources, 1):
            console.rule(f"[bold cyan]Step {i}/{total} — {name}")
            _run(
                [*tycoon_bin, "data", "sources", "run", name, *ingest_flags],
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

    # 5. Health check
    elapsed = time.time() - start
    console.rule("[bold green]Setup Complete")
    success(f"Setup finished in {elapsed:.1f}s")
    console.print()
    _run([*tycoon_bin, "check"], "Stack health check")
    next_steps(
        ("tycoon start", "launch Rill, Dagster, and the web UI"),
        ("tycoon ask init", "set up the AI analytics agent"),
    )
