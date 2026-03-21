"""Top-level Dagster Definitions for the tycoon code location."""

from __future__ import annotations

from dagster import (
    Definitions,
    define_asset_job,
)

from dagster_pipeline.assets.ingestion import ingestion_assets
from dagster_pipeline.assets.transforms import dbt_project_assets
from dagster_pipeline.resources import get_dbt_resource, get_dlt_resource


# Job: run all ingestion assets sequentially (DuckDB single-writer)
ingestion_job = define_asset_job(
    name="ingestion_job",
    selection=[a.key for a in ingestion_assets] if ingestion_assets else [],
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

# Job: run all dbt transformations
transform_job = define_asset_job(
    name="transform_job",
    selection=[dbt_project_assets],
    description="Build all dbt models.",
)

# Job: full pipeline (ingest → transform)
full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=([a.key for a in ingestion_assets] if ingestion_assets else [])
    + [dbt_project_assets],
    description="Run full pipeline: ingest all sources then build dbt models.",
)


defs = Definitions(
    assets=[*ingestion_assets, dbt_project_assets],
    jobs=[ingestion_job, transform_job, full_pipeline_job],
    resources={
        "dbt": get_dbt_resource(),
        "dlt": get_dlt_resource(),
    },
)
