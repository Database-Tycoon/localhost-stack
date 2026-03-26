"""tycoon stop — kill running tycoon servers."""

from __future__ import annotations

import os
import signal

import typer

from tycoon.utils.console import error, info, success, warn

_SERVER_PORTS = {"rill": 9009, "dagster": 3000, "nao": 5005}


def stop_cmd(
    services: list[str] = typer.Argument(
        default=None,
        help="Specific server(s) to stop. Defaults to all (rill, dagster, nao).",
    ),
) -> None:
    """Stop tycoon servers started by `tycoon start`."""
    from tycoon.commands.start import _pid_file, clear_pids

    targets = list(services) if services else list(_SERVER_PORTS.keys())

    pid_file = _pid_file()
    if pid_file.exists():
        _stop_via_pid_file(pid_file, targets)
    else:
        # Fallback: find processes by port using lsof
        info("No PID file found — finding processes by port...")
        _stop_via_ports(targets)

    if not services:
        clear_pids()


def _stop_via_pid_file(pid_file, targets: list[str]) -> None:
    import json

    pids: dict[str, int] = json.loads(pid_file.read_text())
    stopped_any = False

    for name in targets:
        pid = pids.get(name)
        if pid is None:
            warn(f"{name}: not in PID file")
            continue
        stopped_any = True
        _kill_pid(name, pid)

    if not stopped_any:
        info("Nothing to stop.")


def _stop_via_ports(targets: list[str]) -> None:
    import subprocess

    stopped_any = False
    for name in targets:
        port = _SERVER_PORTS.get(name)
        if port is None:
            continue
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )
        pids = [int(p) for p in result.stdout.strip().splitlines() if p.strip()]
        if not pids:
            info(f"{name}: nothing on port {port}")
            continue
        for pid in pids:
            _kill_pid(name, pid)
            stopped_any = True

    if not stopped_any:
        info("Nothing to stop.")


def _kill_pid(name: str, pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
        success(f"Stopped {name} (PID {pid})")
    except ProcessLookupError:
        warn(f"{name}: process {pid} not found (already stopped?)")
    except PermissionError:
        error(f"{name}: no permission to kill PID {pid}")
