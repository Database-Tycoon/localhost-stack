from __future__ import annotations

import subprocess
from pathlib import Path

from dagster import AssetExecutionContext, asset

# Define the project directory
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
RILL_PROJECT_DIR = PROJECT_DIR / "rill"


@asset(
    group_name="rill",
    deps=["fct_bus_segment_speeds"], # Depends on the dbt model
)
def rill_fct_bus_segment_speeds(context):
    """
    Builds the Rill project to refresh the dashboards.
    """
    context.log.info("Building Rill project...")
    try:
        result = subprocess.run(
            ["rill", "build"],
            cwd=RILL_PROJECT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        context.log.info(f"""Rill build successful:
{result.stdout}""")
    except subprocess.CalledProcessError as e:
        context.log.error(f"""Rill build failed:
{e.stderr}""")
        raise
