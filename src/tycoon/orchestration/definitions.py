"""Top-level Dagster Definitions for the tycoon code location."""

from __future__ import annotations

from dagster import (
    Definitions,
    define_asset_job,
)

from tycoon.orchestration.assets.ingestion import ingestion_assets
from tycoon.orchestration.assets.rill import rill_fct_bus_segment_speeds
from tycoon.orchestration.assets.transforms import dbt_project_assets
from tycoon.orchestration.resources import get_dbt_resource, get_dlt_resource


all_assets = [dbt_project_assets, rill_fct_bus_segment_speeds]
all_jobs = []

if ingestion_assets:
    all_assets.extend(ingestion_assets)

    ingestion_job = define_asset_job(
        name="ingestion_job",
        selection=[a.key for a in ingestion_assets],
        description="Ingest all registered sources sequentially.",
        config={
            "execution": {
                "config": {
                    "multiprocess": {
                        "max_concurrent": 1,
                    }
                }
            }
        },
    )
    all_jobs.append(ingestion_job)

    transform_job = define_asset_job(
        name="transform_job",
        selection=[dbt_project_assets],
        description="Build all dbt models.",
    )
    all_jobs.append(transform_job)

    full_pipeline_job = define_asset_job(
        name="full_pipeline_job",
        selection=ingestion_assets + [dbt_project_assets, rill_fct_bus_segment_speeds],
        description="Run full pipeline: ingest all sources then build dbt models.",
    )
    all_jobs.append(full_pipeline_job)


defs = Definitions(
    assets=all_assets,
    jobs=all_jobs,
    resources={
        "dbt": get_dbt_resource(),
        "dlt": get_dlt_resource(),
    },
)
