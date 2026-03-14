"""tycoon transform — run dbt commands against the local DuckDB warehouse."""

from __future__ import annotations

import subprocess
import sys
from typing import Optional

import typer

from tycoon.config import config
from tycoon.utils.console import console, header, success, error

app = typer.Typer(
    help="Run dbt transformations against the local DuckDB warehouse.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_TARGET_OPTION = typer.Option("local", "--target", "-t", help="dbt target profile (default: local).")
_SELECT_OPTION = typer.Option(None, "--select", "-s", help="dbt model selection syntax (e.g. 'staging+').")
_FULL_REFRESH_FLAG = typer.Option(False, "--full-refresh", help="Drop and recreate incremental models.")


def _run_dbt(
    dbt_cmd: str,
    target: str,
    select: Optional[str],
    full_refresh: bool,
    extra: list[str] | None = None,
) -> int:
    """
    Invoke dbt as a subprocess with the project and profiles directories
    both pointing at dbt_project/ inside the repository root.

    Working directory is set to the project root so that relative paths in
    profiles.yml resolve correctly (e.g. ``../data/nyc_open_data_local.duckdb``).
    """
    cmd: list[str] = [
        "dbt",
        dbt_cmd,
        "--project-dir", str(config.dbt_project_dir),
        "--profiles-dir", str(config.dbt_project_dir),
        "--target", target,
    ]

    if select:
        cmd += ["--select", select]

    if full_refresh:
        cmd.append("--full-refresh")

    if extra:
        cmd.extend(extra)

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=str(config.root))
    return result.returncode


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

@app.command()
def run(
    target: str = _TARGET_OPTION,
    select: Optional[str] = _SELECT_OPTION,
    full_refresh: bool = _FULL_REFRESH_FLAG,
) -> None:
    """Execute dbt run — build all models (or a selection) in the warehouse."""
    header("dbt run")

    if not config.dbt_project_dir.exists():
        error(f"dbt project directory not found: {config.dbt_project_dir}")
        raise typer.Exit(1)

    rc = _run_dbt("run", target=target, select=select, full_refresh=full_refresh)

    if rc == 0:
        success("dbt run completed successfully.")
    else:
        error(f"dbt run exited with code {rc}.")
        raise typer.Exit(rc)


@app.command()
def test(
    target: str = _TARGET_OPTION,
    select: Optional[str] = _SELECT_OPTION,
) -> None:
    """Execute dbt test — run data quality tests against built models."""
    header("dbt test")

    if not config.dbt_project_dir.exists():
        error(f"dbt project directory not found: {config.dbt_project_dir}")
        raise typer.Exit(1)

    rc = _run_dbt("test", target=target, select=select, full_refresh=False)

    if rc == 0:
        success("dbt test completed successfully.")
    else:
        error(f"dbt test exited with code {rc}.")
        raise typer.Exit(rc)


@app.command()
def build(
    target: str = _TARGET_OPTION,
    select: Optional[str] = _SELECT_OPTION,
    full_refresh: bool = _FULL_REFRESH_FLAG,
) -> None:
    """Execute dbt build — run + test all models (or a selection)."""
    header("dbt build")

    if not config.dbt_project_dir.exists():
        error(f"dbt project directory not found: {config.dbt_project_dir}")
        raise typer.Exit(1)

    rc = _run_dbt("build", target=target, select=select, full_refresh=full_refresh)

    if rc == 0:
        success("dbt build completed successfully.")
    else:
        error(f"dbt build exited with code {rc}.")
        raise typer.Exit(rc)


@app.command()
def docs(
    target: str = _TARGET_OPTION,
    port: int = typer.Option(8080, "--port", "-p", help="Port for dbt docs serve."),
) -> None:
    """Generate and serve dbt documentation in the browser."""
    header("dbt docs")

    if not config.dbt_project_dir.exists():
        error(f"dbt project directory not found: {config.dbt_project_dir}")
        raise typer.Exit(1)

    # Step 1: generate docs
    console.print("[bold]Generating dbt docs...[/bold]")
    gen_rc = _run_dbt(
        "docs",
        target=target,
        select=None,
        full_refresh=False,
        extra=["generate"],
    )
    if gen_rc != 0:
        error(f"dbt docs generate failed with code {gen_rc}.")
        raise typer.Exit(gen_rc)

    success("Docs generated. Starting server...")

    # Step 2: serve docs (blocking — user terminates with Ctrl+C)
    serve_cmd: list[str] = [
        "dbt",
        "docs",
        "serve",
        "--project-dir", str(config.dbt_project_dir),
        "--profiles-dir", str(config.dbt_project_dir),
        "--target", target,
        "--port", str(port),
    ]

    console.print(f"[dim]Running: {' '.join(serve_cmd)}[/dim]")
    console.print(f"[bold green]dbt docs available at http://localhost:{port}[/bold green]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    try:
        subprocess.run(serve_cmd, cwd=str(config.root), check=True)
    except KeyboardInterrupt:
        console.print("\n[dim]dbt docs server stopped.[/dim]")
    except subprocess.CalledProcessError as exc:
        error(f"dbt docs serve failed with code {exc.returncode}.")
        raise typer.Exit(exc.returncode)
