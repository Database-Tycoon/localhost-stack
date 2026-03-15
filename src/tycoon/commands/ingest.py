"""tycoon ingest — load raw data from registered sources."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from tycoon.config import config
from tycoon.utils.console import error, header, info, success, warn

app = typer.Typer(
    help="Ingest raw data from registered sources.",
    no_args_is_help=True,
)

MaxRecordsOption = Annotated[
    Optional[int],
    typer.Option(
        "--max-records",
        "-n",
        help="Cap the total number of records fetched per resource (useful for testing).",
        show_default=False,
    ),
]


@app.command(name="run")
def run_source(
    source_name: Annotated[str, typer.Argument(help="Name of the registered source to ingest.")],
    max_records: MaxRecordsOption = None,
) -> None:
    """Ingest data from a registered source by name."""
    from tycoon.ingestion.runner import run_source as _run_source

    if not config.has_project_file:
        error("No tycoon.yml found. Run 'tycoon init' first.")
        raise typer.Exit(1)

    sources = config.sources
    if source_name not in sources:
        error(f"Source '{source_name}' not found. Available: {', '.join(sources.keys()) or '(none)'}")
        raise typer.Exit(1)

    source_config = sources[source_name]
    header(f"Ingesting: {source_name}")
    info(f"Type: {source_config.type} | Schema: {source_config.schema_name}")
    if max_records is not None:
        info(f"Record cap: {max_records:,}")

    config.ensure_data_dir()

    try:
        _pipeline, load_info = _run_source(
            name=source_name,
            source_config=source_config,
            raw_db_path=config.raw_db,
            max_records=max_records,
        )
        success(f"{source_name} load complete. {load_info}")
    except Exception as exc:
        error(f"{source_name} pipeline failed: {exc}")
        raise typer.Exit(1) from exc


@app.command(name="all")
def ingest_all(
    max_records: MaxRecordsOption = None,
) -> None:
    """Run all registered source pipelines sequentially.

    Pipelines run sequentially to respect DuckDB's single-writer constraint.
    """
    if not config.has_project_file:
        error("No tycoon.yml found. Run 'tycoon init' first.")
        raise typer.Exit(1)

    sources = config.sources
    if not sources:
        warn("No sources registered. Run 'tycoon sources add' first.")
        raise typer.Exit(0)

    total = len(sources)
    header(f"Full Ingestion ({total} source{'s' if total != 1 else ''})")
    if max_records is not None:
        info(f"Record cap per resource: {max_records:,}")

    config.ensure_data_dir()

    from tycoon.ingestion.runner import run_source as _run_source

    for i, (name, source_config) in enumerate(sources.items(), 1):
        info(f"Step {i}/{total} — {name} ({source_config.type})...")
        try:
            _pipeline, load_info = _run_source(
                name=name,
                source_config=source_config,
                raw_db_path=config.raw_db,
                max_records=max_records,
            )
            success(f"{name} complete. {load_info}")
        except Exception as exc:
            error(f"{name} pipeline failed: {exc}")
            raise typer.Exit(1) from exc

    success("All ingestion pipelines completed successfully.")
