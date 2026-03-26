"""tycoon start — launch the three long-running servers."""

from __future__ import annotations

import signal
import threading

import typer

from tycoon.config import config
from tycoon.utils.console import console, error, header, info, success, warn

# The three servers that run continuously and are not Dagster assets.
_SERVER_NAMES = ["rill", "dagster", "nao"]


def start_cmd(
    skip: list[str] = typer.Option(
        [], "--skip", help="Server(s) to skip. Repeatable: --skip nao --skip dagster"
    ),
    only: list[str] = typer.Option(
        [], "--only", help="Only start these server(s). Repeatable: --only rill"
    ),
) -> None:
    """Start the Rill dashboard, Dagster orchestrator, and Nao AI agent.

    All three run as background processes in this session.
    Press Ctrl-C to stop everything.
    """
    from tycoon.services.manager import ServiceManager

    targets = _resolve_targets(skip, only)
    if not targets:
        error("No servers to start.")
        raise typer.Exit(1)

    _preflight_checks(targets)

    manager = ServiceManager()
    header("Tycoon")

    for name in targets:
        manager.start(name)

    console.print()
    _print_urls(targets)
    console.print()
    info("Press [bold]Ctrl-C[/bold] to stop all servers.")

    shutdown = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    shutdown.wait()

    console.print()
    info("Shutting down...")
    manager.stop_all()
    info("Done.")


def _resolve_targets(skip: list[str], only: list[str]) -> list[str]:
    if only:
        unknown = [n for n in only if n not in _SERVER_NAMES]
        for u in unknown:
            warn(f"Unknown server: {u} (choices: {', '.join(_SERVER_NAMES)})")
        return [n for n in only if n in _SERVER_NAMES]
    return [n for n in _SERVER_NAMES if n not in skip]


def _preflight_checks(targets: list[str]) -> None:
    """Warn if required config or binaries are missing before starting."""
    if "nao" in targets:
        try:
            import nao_core  # noqa: F401
        except ImportError:
            warn("nao-core is not installed — skipping Nao.")
            targets.remove("nao")
            return
        if not (config.nao_dir / "nao_config.yaml").exists():
            warn("Nao has not been initialised. Run [bold]tycoon ask init && tycoon ask sync[/bold] first.")
            targets.remove("nao")

    if "dagster" in targets:
        import shutil
        if not shutil.which("dagster"):
            warn("dagster not found — skipping. Install with: [bold]pip install tycoon\\[dagster][/bold]")
            targets.remove("dagster")


def _print_urls(targets: list[str]) -> None:
    from tycoon.constants import PORTS
    lines = {
        "rill":    ("Rill dashboards", f"http://localhost:{PORTS['rill']}"),
        "dagster": ("Dagster UI",       f"http://localhost:{PORTS['dagster']}"),
        "nao":     ("Nao AI queries",   f"http://localhost:{PORTS['nao']}"),
    }
    for name in targets:
        if name in lines:
            label, url = lines[name]
            success(f"{label}: [bold]{url}[/bold]")
