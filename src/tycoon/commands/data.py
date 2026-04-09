"""tycoon data — data pipeline management."""

from __future__ import annotations

import typer

app = typer.Typer(help="Data pipeline — sources, ingestion, transforms, and exploration.")


def _register() -> None:
    """Wire sub-commands. Called once at import to avoid circular imports."""
    from tycoon.commands import db, sources, transform
    from tycoon.commands.explore import explore_cmd
    from tycoon.commands.setup import setup_cmd

    app.add_typer(sources.app, name="sources")
    app.add_typer(transform.app, name="transform")
    app.add_typer(db.app, name="db")
    app.command(name="explore")(explore_cmd)
    app.command(name="setup")(setup_cmd)


_register()
