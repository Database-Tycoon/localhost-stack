"""dlt pipeline for MTA bus segment speeds (data.ny.gov Socrata)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import dlt
import httpx

from tycoon.config import config
from tycoon.constants import (
    DATASET_BUS_SPEEDS_2023_2024,
    DATASET_BUS_SPEEDS_2025,
    MTA_BUS_SPEEDS_DOMAIN,
    SOCRATA_PAGE_SIZE,
)


def _socrata_pages(
    domain: str,
    dataset_id: str,
    max_records: int | None,
) -> Iterator[list[dict[str, Any]]]:
    """Paginate through a Socrata JSON endpoint and yield pages of records."""
    url = f"https://{domain}/resource/{dataset_id}.json"
    fetched = 0

    with httpx.Client(timeout=60) as client:
        offset = 0
        while True:
            limit = SOCRATA_PAGE_SIZE
            if max_records is not None:
                remaining = max_records - fetched
                if remaining <= 0:
                    break
                limit = min(limit, remaining)

            params = {
                "$limit": limit,
                "$offset": offset,
                "$order": ":id",
            }
            response = client.get(url, params=params)
            response.raise_for_status()
            page: list[dict[str, Any]] = response.json()

            if not page:
                break

            yield page
            fetched += len(page)
            offset += len(page)

            if len(page) < limit:
                break


@dlt.resource(name="bus_segment_speeds_2023_2024", write_disposition="replace")
def bus_segment_speeds_2023_2024(
    max_records: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield records from the MTA bus segment speeds 2023-2024 dataset (~11.7 M rows)."""
    for page in _socrata_pages(
        MTA_BUS_SPEEDS_DOMAIN, DATASET_BUS_SPEEDS_2023_2024, max_records
    ):
        yield from page


@dlt.resource(name="bus_segment_speeds_2025", write_disposition="replace")
def bus_segment_speeds_2025(
    max_records: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield records from the MTA bus segment speeds 2025 dataset (~6.3 M rows)."""
    for page in _socrata_pages(
        MTA_BUS_SPEEDS_DOMAIN, DATASET_BUS_SPEEDS_2025, max_records
    ):
        yield from page


@dlt.source(name="raw_mta_bus_speeds")
def mta_bus_speeds_source(
    max_records: int | None = None,
    skip_2023_2024: bool = False,
) -> list[Any]:
    """dlt source bundling MTA bus speeds resources."""
    resources: list[Any] = []
    if not skip_2023_2024:
        resources.append(bus_segment_speeds_2023_2024(max_records=max_records))
    resources.append(bus_segment_speeds_2025(max_records=max_records))
    return resources


def run_pipeline(
    max_records: int | None = None,
    skip_2023_2024: bool = False,
) -> tuple[dlt.Pipeline, Any]:
    """Create, run, and return the MTA bus speeds dlt pipeline."""
    config.ensure_data_dir()

    pipeline = dlt.pipeline(
        pipeline_name="mta_bus_speeds",
        destination=dlt.destinations.duckdb(str(config.raw_db)),
        dataset_name="raw_mta_bus_speeds",
    )

    load_info = pipeline.run(
        mta_bus_speeds_source(max_records=max_records, skip_2023_2024=skip_2023_2024)
    )
    return pipeline, load_info
