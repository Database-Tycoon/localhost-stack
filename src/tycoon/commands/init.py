"""tycoon init -- scaffold a new tycoon project."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from tycoon.scaffolding.templates import (
    list_templates,
    scaffold_blank_project,
    scaffold_from_template,
)
from tycoon.utils.console import console, error, header, info, success, warn


def init_cmd(
    template: Annotated[
        Optional[str],
        typer.Option(
            "--template",
            "-t",
            help="Template name to scaffold from.",
        ),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option(
            "--name",
            "-n",
            help="Project name (defaults to current directory name).",
        ),
    ] = None,
    list_templates_flag: Annotated[
        bool,
        typer.Option(
            "--list-templates",
            help="List available templates and exit.",
        ),
    ] = False,
) -> None:
    """Initialize a new tycoon project in the current directory."""
    # --list-templates
    if list_templates_flag:
        templates = list_templates()
        if not templates:
            info("No templates available.")
        else:
            header("Available Templates")
            for t in templates:
                console.print(f"  - {t}")
        raise typer.Exit(0)

    target = Path.cwd()
    project_name = name or target.name

    # Refuse to overwrite existing tycoon.yml
    if (target / "tycoon.yml").exists():
        warn("tycoon.yml already exists in this directory.")
        error("Use a different directory or remove the existing tycoon.yml first.")
        raise typer.Exit(1)

    header(f"Initializing tycoon project: {project_name}")

    if template:
        try:
            scaffold_from_template(target, template)
        except FileNotFoundError as exc:
            error(str(exc))
            raise typer.Exit(1)
    else:
        scaffold_blank_project(target, project_name)

    console.print()
    success(f"Project '{project_name}' initialized successfully!")
    info("Next steps:")
    info("  1. Edit tycoon.yml to add your data sources")
    info("  2. Run 'tycoon setup' to ingest data and build models")
