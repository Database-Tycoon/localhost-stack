"""tycoon ingest — load raw data from NYC DOT and MTA APIs."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from tycoon.utils.console import error, header, info, success

app = typer.Typer(
    help="Ingest raw data from NYC DOT and MTA open data APIs.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Shared option types
# ---------------------------------------------------------------------------

MaxRecordsOption = Annotated[
    Optional[int],
    typer.Option(
        "--max-records",
        "-n",
        help="Cap the total number of records fetched per resource (useful for testing).",
        show_default=False,
    ),
]


# ---------------------------------------------------------------------------
# dot
# ---------------------------------------------------------------------------


@app.command()
def dot(
    max_records: MaxRecordsOption = None,
) -> None:
    """Ingest NYC DOT traffic speeds, bus lanes, and volume counts."""
    header("NYC DOT Ingestion")

    if max_records is not None:
        info(f"Record cap per resource: {max_records:,}")

    info("Starting NYC DOT pipeline...")
    try:
        from tycoon.ingestion import nyc_dot_pipeline

        _pipeline, load_info = nyc_dot_pipeline.run_pipeline(max_records=max_records)
        success(f"NYC DOT load complete. {load_info}")
    except Exception as exc:
        error(f"NYC DOT pipeline failed: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# mta
# ---------------------------------------------------------------------------


@app.command()
def mta(
    max_records: MaxRecordsOption = None,
) -> None:
    """Ingest MTA GTFS static feeds (routes and stops for all boroughs)."""
    header("MTA GTFS Ingestion")

    if max_records is not None:
        info(f"Record cap per resource: {max_records:,}")

    info("Starting MTA GTFS pipeline...")
    try:
        from tycoon.ingestion import mta_pipeline

        _pipeline, load_info = mta_pipeline.run_pipeline(max_records=max_records)
        success(f"MTA GTFS load complete. {load_info}")
    except Exception as exc:
        error(f"MTA GTFS pipeline failed: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# bus-speeds
# ---------------------------------------------------------------------------


@app.command(name="bus-speeds")
def bus_speeds(
    max_records: MaxRecordsOption = None,
    skip_2023_2024: Annotated[
        bool,
        typer.Option(
            "--skip-2023-2024",
            help="Skip the large 2023-2024 historical dataset (~11.7 M rows).",
        ),
    ] = False,
) -> None:
    """Ingest MTA bus segment speeds (2023-2024 and 2025 datasets)."""
    header("MTA Bus Speeds Ingestion")

    if max_records is not None:
        info(f"Record cap per resource: {max_records:,}")
    if skip_2023_2024:
        info("Skipping 2023-2024 dataset (--skip-2023-2024 set).")

    info("Starting MTA bus speeds pipeline...")
    try:
        from tycoon.ingestion import mta_bus_speeds_pipeline

        _pipeline, load_info = mta_bus_speeds_pipeline.run_pipeline(
            max_records=max_records,
            skip_2023_2024=skip_2023_2024,
        )
        success(f"MTA bus speeds load complete. {load_info}")
    except Exception as exc:
        error(f"MTA bus speeds pipeline failed: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------


@app.command(name="all")
def ingest_all(
    max_records: MaxRecordsOption = None,
    skip_2023_2024: Annotated[
        bool,
        typer.Option(
            "--skip-2023-2024",
            help="Skip the large 2023-2024 bus speeds dataset when running all pipelines.",
        ),
    ] = False,
) -> None:
    """Run all ingestion pipelines sequentially (DOT -> MTA -> Bus Speeds).

    Pipelines run sequentially to respect DuckDB's single-writer constraint.
    """
    header("Full Ingestion (DOT -> MTA -> Bus Speeds)")

    if max_records is not None:
        info(f"Record cap per resource: {max_records:,}")

    # 1. NYC DOT
    info("Step 1/3 — NYC DOT...")
    try:
        from tycoon.ingestion import nyc_dot_pipeline

        _pipeline, load_info = nyc_dot_pipeline.run_pipeline(max_records=max_records)
        success(f"NYC DOT complete. {load_info}")
    except Exception as exc:
        error(f"NYC DOT pipeline failed: {exc}")
        raise typer.Exit(1) from exc

    # 2. MTA GTFS
    info("Step 2/3 — MTA GTFS...")
    try:
        from tycoon.ingestion import mta_pipeline

        _pipeline, load_info = mta_pipeline.run_pipeline(max_records=max_records)
        success(f"MTA GTFS complete. {load_info}")
    except Exception as exc:
        error(f"MTA GTFS pipeline failed: {exc}")
        raise typer.Exit(1) from exc

    # 3. MTA Bus Speeds
    info("Step 3/3 — MTA Bus Speeds...")
    try:
        from tycoon.ingestion import mta_bus_speeds_pipeline

        _pipeline, load_info = mta_bus_speeds_pipeline.run_pipeline(
            max_records=max_records,
            skip_2023_2024=skip_2023_2024,
        )
        success(f"MTA bus speeds complete. {load_info}")
    except Exception as exc:
        error(f"MTA bus speeds pipeline failed: {exc}")
        raise typer.Exit(1) from exc

    success("All ingestion pipelines completed successfully.")
