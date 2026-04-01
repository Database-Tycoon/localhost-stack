"""Top-level Typer app — entry point for the `tycoon` CLI."""

from __future__ import annotations

import typer

import tycoon

app = typer.Typer(
    name="tycoon",
    help="Database Tycoon — local-first analytics CLI for exploring any dataset.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
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

app.add_typer(data.app, name="data")
app.add_typer(ai.app, name="ai")
app.command(name="init")(init_cmd)
app.command(name="start")(start_cmd)
app.command(
    name="stop",
)(stop_cmd)
app.command(
    name="run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(run_cmd)
