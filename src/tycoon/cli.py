"""Top-level Typer app — entry point for the `tycoon` CLI."""

from __future__ import annotations

import typer

import tycoon
from tycoon.commands import ai, ask, check, db, ingest, init, setup, sources, start, transform
from tycoon.commands.demo import demo_cmd
from tycoon.commands.explore import explore_cmd
from tycoon.commands.run import run_cmd
from tycoon.commands.serve import serve_cmd
from tycoon.commands.stop import stop_cmd

app = typer.Typer(
    name="tycoon",
    help="Database Tycoon — local-first analytics CLI for exploring any dataset.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

# Sub-commands
app.add_typer(ai.app, name="ai")
app.add_typer(ask.app, name="ask")
app.add_typer(check.app, name="check")
app.add_typer(ingest.app, name="ingest")
app.add_typer(db.app, name="db")
app.add_typer(sources.app, name="sources")
app.add_typer(transform.app, name="transform")
app.command(name="init")(init.init_cmd)
app.command(name="setup")(setup.setup_cmd)
app.command(name="start")(start.start_cmd)
app.command(name="stop")(stop_cmd)
app.command(name="serve")(serve_cmd)
app.command(name="demo")(demo_cmd)
app.command(name="explore")(explore_cmd)
app.command(
    name="run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(run_cmd)


@app.command()
def version() -> None:
    """Print the tycoon version."""
    typer.echo(f"tycoon {tycoon.__version__}")
