"""Dagster assets wrapping the tycoon dbt project.

Uses dagster-dbt to parse the dbt manifest and expose each model
as a Dagster asset with full lineage.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets, DbtProject

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DBT_PROJECT_DIR = PROJECT_DIR / "dbt_project"

# Parse the dbt project to generate a manifest for Dagster.
# This runs at definition time (import / code-server start).
dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
    target="local",
)
dbt_project.prepare_if_dev()


@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_project_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Materialize all dbt models as Dagster assets."""
    yield from dbt.cli(["build"], context=context).stream()
