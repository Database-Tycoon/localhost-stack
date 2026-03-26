"""tycoon ask — AI analytics agent powered by Nao."""

from __future__ import annotations

import os
import subprocess
import sys

import typer

from tycoon.config import config
from tycoon.utils.console import error, info, success

app = typer.Typer(help="AI analytics agent — query your data in natural language.")


def _require_nao() -> None:
    try:
        import nao_core  # noqa: F401
    except ImportError:
        error("Nao is not installed. Run: [bold]pip install tycoon\\[ask][/bold]")
        raise typer.Exit(1)


def _require_project() -> None:
    if not config.has_project_file:
        error("No tycoon.yml found. Run [bold]tycoon init[/bold] first.")
        raise typer.Exit(1)


def _nao_env() -> dict[str, str]:
    """Environment for nao subprocess — sets NAO_DEFAULT_PROJECT_PATH."""
    return {**os.environ, "NAO_DEFAULT_PROJECT_PATH": str(config.nao_dir)}


@app.command("init")
def ask_init() -> None:
    """Generate .tycoon/nao/nao_config.yaml from tycoon.yml."""
    _require_project()
    _require_nao()

    from tycoon.nao import write_nao_project

    write_nao_project(config)

    success(f"Nao config written to [bold]{config.nao_dir}[/bold]")
    info("Next steps:")
    info("  1. [bold]tycoon ask sync[/bold]  — build DB + dbt context (~30s first run)")
    info("  2. [bold]tycoon ask chat[/bold]  — launch the query UI")


@app.command("sync")
def ask_sync(
    reinit: bool = typer.Option(False, "--reinit", help="Regenerate nao_config.yaml before syncing"),
) -> None:
    """Sync DB schema and dbt context into Nao."""
    _require_project()
    _require_nao()

    if reinit:
        from tycoon.nao import write_nao_project
        write_nao_project(config)
        info("Config regenerated.")

    if not (config.nao_dir / "nao_config.yaml").exists():
        error("No nao_config.yaml found. Run [bold]tycoon ask init[/bold] first.")
        raise typer.Exit(1)

    info("Syncing Nao context...")
    result = subprocess.run(
        [sys.executable, "-m", "nao_core", "sync"],
        cwd=str(config.nao_dir),
        env=_nao_env(),
    )
    if result.returncode != 0:
        error("nao sync failed.")
        raise typer.Exit(result.returncode)

    success("Context synced. Run [bold]tycoon ask chat[/bold] to start querying.")


@app.command("chat")
def ask_chat(
    port: int = typer.Option(0, help="Port override (default: from tycoon.yml or 5005)"),
) -> None:
    """Launch the Nao chat UI in your browser.

    Automatically runs init and sync on first use if not already done.
    """
    _require_project()
    _require_nao()

    # Auto-init if no config exists yet
    nao_config = config.nao_dir / "nao_config.yaml"
    if not nao_config.exists():
        info("No nao_config.yaml found — running [bold]tycoon ask init[/bold] automatically...")
        from tycoon.nao import write_nao_project
        write_nao_project(config)
        success(f"Nao config written to [bold]{config.nao_dir}[/bold]")

    # Auto-sync if context DB hasn't been built yet
    context_ready = (config.nao_dir / "databases").exists()
    if not context_ready:
        info("Context not yet synced — running [bold]tycoon ask sync[/bold] automatically...")
        result = subprocess.run(
            [sys.executable, "-m", "nao_core", "sync"],
            cwd=str(config.nao_dir),
            env=_nao_env(),
        )
        if result.returncode != 0:
            error("nao sync failed. Run [bold]tycoon ask sync[/bold] to debug.")
            raise typer.Exit(result.returncode)

    # Resolve port: CLI flag > tycoon.yml > default
    resolved_port = port
    if not resolved_port and config.project and config.project.ask:
        resolved_port = config.project.ask.port
    if not resolved_port:
        resolved_port = 5005

    info(f"Starting Nao chat at [bold]http://localhost:{resolved_port}[/bold]")
    subprocess.run(
        [sys.executable, "-m", "nao_core", "chat", "--port", str(resolved_port)],
        cwd=str(config.nao_dir),
        env=_nao_env(),
    )
