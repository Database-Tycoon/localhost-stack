"""``tycoon demo`` — start all services for the local analytics environment."""

from __future__ import annotations

import signal
import threading
from typing import Optional

import typer

from tycoon.utils.console import console, error, header, info, status_table, warn


def demo_cmd(
    skip: Optional[list[str]] = typer.Option(
        None, "--skip", help="Services to skip (repeatable)."
    ),
    only: Optional[list[str]] = typer.Option(
        None, "--only", help="Only start these services (repeatable)."
    ),
) -> None:
    """Start all Tycoon services (or a subset) for local development."""
    from tycoon.services.manager import ServiceManager

    manager = ServiceManager()
    all_names = manager.service_names

    # Determine which services to start.
    if only:
        targets = [n for n in only if n in all_names]
        unknown = [n for n in only if n not in all_names]
        for u in unknown:
            warn(f"Unknown service: {u}")
    elif skip:
        targets = [n for n in all_names if n not in skip]
    else:
        targets = list(all_names)

    # Always include tycoon in targets for status display, but it is
    # started separately via uvicorn below.
    start_tycoon = "tycoon" in targets
    service_targets = [t for t in targets if t != "tycoon"]

    if not service_targets and not start_tycoon:
        error("No services to start.")
        raise typer.Exit(1)

    header("Tycoon Demo Environment")

    # Start non-tycoon services.
    for name in service_targets:
        manager.start(name)

    # Start the Tycoon dashboard server in a background thread.
    if start_tycoon:
        _start_tycoon_background(port=8888, host="0.0.0.0")

    # Print status table.
    rows = []
    for name in targets:
        healthy = manager.health(name)
        status = "OK" if healthy else "DOWN"
        svc = manager._definitions.get(name)
        port_str = str(svc.port) if svc else "?"
        rows.append((name, status, f":{port_str}"))

    console.print()
    console.print(status_table(rows, title="Services"))
    console.print()
    info("Press Ctrl-C to shut down all services.")

    # Block until interrupted.
    shutdown_event = threading.Event()

    def _on_signal(signum: int, frame: object) -> None:
        shutdown_event.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    shutdown_event.wait()

    console.print()
    info("Shutting down...")
    manager.stop_all()
    info("All services stopped.")


def _start_tycoon_background(port: int, host: str) -> None:
    """Run the Tycoon FastAPI server in a daemon thread."""
    import uvicorn

    from tycoon.utils.console import info

    uvi_config = uvicorn.Config(
        "tycoon.server.app:create_app",
        host=host,
        port=port,
        factory=True,
        log_level="warning",
    )
    server = uvicorn.Server(uvi_config)

    thread = threading.Thread(target=server.run, daemon=True, name="tycoon-server")
    thread.start()
    info(f"Tycoon dashboard starting on {host}:{port}")
