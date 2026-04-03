"""Top-level Typer app — entry point for the `tycoon` CLI."""

from __future__ import annotations

import typer
import requests
import packaging.version
from typing import Optional, cast
from __future__ import annotations

import typer
from typer.core import TyperGroup

import tycoon

_COMMAND_ORDER = ["init", "data", "ai", "start", "stop", "run", "check-updates"]

_SECTIONS = {
    "init":  "Project",
    "data":  "Data Pipeline",
    "ai":    "AI",
    "start": "Services",
    "stop":  "Services",
    "run":   "Tools",
    "check-updates": "Utilities"
}


class _OrderedGroup(TyperGroup):
    def list_commands(self, ctx: object) -> list[str]:
        commands = super().list_commands(ctx)
        return sorted(commands, key=lambda c: _COMMAND_ORDER.index(c) if c in _COMMAND_ORDER else 99)

    def format_commands(self, ctx: object, formatter: object) -> None:
        seen: dict[str, list[tuple[str, str]]] = {}
        for name in self.list_commands(ctx):
            cmd = self.commands.get(name)
            if cmd is None or getattr(cmd, "hidden", False):
                continue
            section = _SECTIONS.get(name, "Commands")
            seen.setdefault(section, []).append(
                (name, cmd.get_short_help_str(limit=formatter.width))
            )
        for section, rows in seen.items():
            with formatter.section(section):
                formatter.write_dl(rows)


app = typer.Typer(
    name="tycoon",
    help="Database Tycoon — local-first analytics CLI for exploring any dataset.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    cls=_OrderedGroup,
)


def check_updates() -> None:
    """
    Check if there's a newer version of Tycoon available on PyPI.
    """
    try:
        response = requests.get("https://pypi.org/pypi/tycoon/json")
        response.raise_for_status()
        latest_version = packaging.version.parse(response.json()["info"]["version"])
        current_version = packaging.version.parse(tycoon.__version__)
        
        if latest_version > current_version:
            typer.echo(f"A newer version of Tycoon is available: {latest_version}")
        else:
            typer.echo("You're already running the latest version.")
    except Exception as e:
        typer.secho(f"Failed to check updates: {e}", fg=typer.colors.RED)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tycoon {tycoon.__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Print version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    pass


from tycoon.commands import ai, data
from tycoon.commands.init import init_cmd
from tycoon.commands.run import run_cmd
from tycoon.commands.start import start_cmd
from tycoon.commands.stop import stop_cmd


app.command(name="init")(init_cmd)
app.add_typer(data.app, name="data")
app.add_typer(ai.app, name="ai")
app.command(name="start")(start_cmd)
app.command(name="stop")(stop_cmd)
app.command(
    name="run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(run_cmd)
app.command(name="check-updates")(check_updates)
