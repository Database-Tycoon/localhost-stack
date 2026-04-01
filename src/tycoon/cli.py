"""Top-level Typer app — entry point for the `tycoon` CLI."""

from __future__ import annotations

import typer
from typer.core import TyperGroup

import tycoon

_COMMAND_ORDER = ["init", "data", "ai", "start", "stop", "run"]


class _OrderedGroup(TyperGroup):
    def list_commands(self, ctx: object) -> list[str]:
        commands = super().list_commands(ctx)
        return sorted(commands, key=lambda c: _COMMAND_ORDER.index(c) if c in _COMMAND_ORDER else 99)


app = typer.Typer(
    name="tycoon",
    help="Database Tycoon — local-first analytics CLI for exploring any dataset.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode="rich",
    cls=_OrderedGroup,
)


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

app.command(name="init", rich_help_panel="Project")(init_cmd)
app.add_typer(data.app, name="data", rich_help_panel="Data Pipeline")
app.add_typer(ai.app, name="ai", rich_help_panel="AI")
app.command(name="start", rich_help_panel="Services")(start_cmd)
app.command(name="stop", rich_help_panel="Services")(stop_cmd)
app.command(
    name="run",
    rich_help_panel="Tools",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(run_cmd)
