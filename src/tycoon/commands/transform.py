"""tycoon transform — run dbt commands against the local DuckDB warehouse."""

from __future__ import annotations

from typing import Optional

import typer
from dagster_dbt import DbtCliResource

from tycoon.config import config
from tycoon.dbt import dbt_project
from tycoon.utils.console import ai_hint, console, header, next_steps, success, error

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
    """Invoke dbt using dagster-dbt to ensure consistent execution with Dagster."""
    dbt_cli = DbtCliResource(
        project_dir=dbt_project.project_dir,
        profiles_dir=dbt_project.profiles_dir,
        target=target,
    )

    cli_args = [dbt_cmd]
    if select:
        cli_args += ["--select", select]
    if full_refresh:
        cli_args.append("--full-refresh")
    if extra:
        cli_args.extend(extra)

    console.print(f"[dim]Running: dbt {' '.join(cli_args)} --target {target}[/dim]")

    # dagster-dbt runs commands from within the project_dir, which is what we want
    # for relative paths in profiles.yml to work correctly.
    # It also streams stdout/stderr from the subprocess, so we don't need to capture.
    invocation = dbt_cli.cli(cli_args).run()

    return 0 if invocation.is_success else 1


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
        next_steps(
            ("tycoon start --only rill", "explore data in the Rill dashboard"),
            ("tycoon ai pipeline document-staging --model <model>", "document and test a model with AI"),
        )
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
        ai_hint("why did my dbt tests fail?")
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
    dbt_cli = DbtCliResource(
        project_dir=dbt_project.project_dir,
        profiles_dir=dbt_project.profiles_dir,
        target=target,
    )
    cli_args = ["docs", "serve", "--port", str(port)]

    console.print(f"[dim]Running: dbt {' '.join(cli_args)} --target {target}[/dim]")
    console.print(f"[bold green]dbt docs available at http://localhost:{port}[/bold green]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    try:
        # Using .run() will block until completion and stream logs.
        dbt_cli.cli(cli_args).run()
    except KeyboardInterrupt:
        console.print("\n[dim]dbt docs server stopped.[/dim]")
    except Exception as exc:
        # DagsterDbtCliRuntimeError is raised on non-zero exit code
        error(f"dbt docs serve failed: {exc}")
        raise typer.Exit(1)
