"""tycoon sources — manage registered data sources."""

from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

from tycoon.config import config
from tycoon.project import SourceConfig, load_project, save_project
from tycoon.utils.console import console, error, header, info, success, warn

app = typer.Typer(help="Manage registered data sources.")


def _require_project() -> None:
    """Abort if no tycoon.yml exists."""
    if not config.has_project_file:
        error("No tycoon.yml found. Run [bold]tycoon init[/bold] first.")
        raise typer.Exit(1)


@app.command("list")
def list_sources() -> None:
    """List all registered data sources."""
    _require_project()

    sources = config.sources
    if not sources:
        info("No sources registered yet.")
        info("Add one with [bold]tycoon sources add <type>[/bold]")
        return

    table = Table(title="Registered Sources", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="bold")
    table.add_column("Schema", style="green")
    table.add_column("Tables", style="dim")

    for name, src in sources.items():
        tables_str = ", ".join(src.tables) if src.tables else "(all)"
        table.add_row(name, src.type, src.schema_name, tables_str)

    console.print(table)


@app.command("show")
def show_source(
    name: str = typer.Argument(help="Name of the source to show"),
) -> None:
    """Show detailed configuration for a specific source."""
    _require_project()

    sources = config.sources
    if name not in sources:
        error(f"Source [bold]{name}[/bold] not found.")
        info(f"Available sources: {', '.join(sources.keys()) if sources else '(none)'}")
        raise typer.Exit(1)

    src = sources[name]
    header(f"Source: {name}")
    console.print(f"  [bold]Type:[/bold]   {src.type}")
    console.print(f"  [bold]Schema:[/bold] {src.schema_name}")

    if src.tables:
        console.print(f"  [bold]Tables:[/bold] {', '.join(src.tables)}")
    else:
        console.print("  [bold]Tables:[/bold] (all)")

    if src.dbt_package:
        console.print(f"  [bold]dbt package:[/bold] {src.dbt_package}")

    if src.config:
        console.print("  [bold]Config:[/bold]")
        for key, value in src.config.items():
            console.print(f"    {key}: {value}")


def _prompt_rest_api_config() -> dict[str, Any]:
    """Prompt for rest_api source configuration."""
    base_url = typer.prompt("Base URL for the REST API")
    return {"base_url": base_url}


def _prompt_sql_database_config() -> dict[str, Any]:
    """Prompt for sql_database source configuration."""
    info("Hint: use ${ENV_VAR} syntax for secrets (e.g. ${DATABASE_URL})")
    connection_string = typer.prompt("Connection string")
    return {"connection_string": connection_string}


def _prompt_filesystem_config() -> dict[str, Any]:
    """Prompt for filesystem source configuration."""
    path = typer.prompt("Path or URL to the data files")
    return {"path": path}


def _prompt_generic_config() -> dict[str, Any]:
    """Prompt for generic key=value configuration pairs."""
    info("Enter config as key=value pairs. Empty line to finish.")
    cfg: dict[str, Any] = {}
    while True:
        pair = typer.prompt("  key=value (or empty to finish)", default="", show_default=False)
        if not pair:
            break
        if "=" not in pair:
            warn(f"Skipping invalid entry (no '=' found): {pair}")
            continue
        key, value = pair.split("=", 1)
        cfg[key.strip()] = value.strip()
    return cfg


_CONFIG_PROMPTERS = {
    "rest_api": _prompt_rest_api_config,
    "sql_database": _prompt_sql_database_config,
    "filesystem": _prompt_filesystem_config,
}


@app.command("add")
def add_source(
    source_type: str = typer.Argument(help="dlt source type (rest_api, sql_database, filesystem, etc.)"),
) -> None:
    """Interactively register a new data source."""
    _require_project()

    header(f"Add source: {source_type}")

    # Prompt for name and schema
    source_name = typer.prompt("Source name", default=source_type)
    schema_name = typer.prompt("Schema name", default=f"raw_{source_name.replace('-', '_')}")

    # Type-specific config prompts
    prompter = _CONFIG_PROMPTERS.get(source_type, _prompt_generic_config)
    source_config = prompter()

    # Build the SourceConfig
    new_source = SourceConfig(
        type=source_type,
        schema=schema_name,
        config=source_config,
    )

    # Load, modify, save
    project = load_project(config.root)
    assert project is not None  # guarded by _require_project

    if source_name in project.sources:
        overwrite = typer.confirm(
            f"Source '{source_name}' already exists. Overwrite?", default=False
        )
        if not overwrite:
            info("Cancelled.")
            raise typer.Exit(0)

    project.sources[source_name] = new_source
    save_project(project, config.root)
    config.reload()

    success(f"Source [bold]{source_name}[/bold] added to tycoon.yml")

    # Offer to install dlt extra
    _maybe_install_dlt_extra(source_type)


def _maybe_install_dlt_extra(source_type: str) -> None:
    """Check if the dlt extra is available and offer to install if not."""
    from tycoon.ingestion.source_installer import (
        DLT_EXTRAS,
        install_dlt_extra,
        is_dlt_extra_available,
    )

    if source_type not in DLT_EXTRAS:
        return

    if is_dlt_extra_available(source_type):
        info(f"dlt[{source_type}] is already available.")
        return

    install = typer.confirm(
        f"dlt[{source_type}] is not installed. Install it now?", default=True
    )
    if install:
        if install_dlt_extra(source_type):
            success(f"dlt[{source_type}] installed successfully.")
        else:
            warn(f"Failed to install dlt[{source_type}]. You can install it manually.")
    else:
        info(f"Skipped. Install later with: uv pip install 'dlt[{source_type}]'")


@app.command("remove")
def remove_source(
    name: str = typer.Argument(help="Name of the source to remove"),
) -> None:
    """Remove a registered data source."""
    _require_project()

    project = load_project(config.root)
    assert project is not None

    if name not in project.sources:
        error(f"Source [bold]{name}[/bold] not found.")
        info(f"Available sources: {', '.join(project.sources.keys()) if project.sources else '(none)'}")
        raise typer.Exit(1)

    typer.confirm(f"Remove source '{name}'?", abort=True)

    del project.sources[name]
    save_project(project, config.root)
    config.reload()

    success(f"Source [bold]{name}[/bold] removed from tycoon.yml")
