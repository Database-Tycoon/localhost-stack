"""tycoon doctor — check the environment for potential issues."""

from __future__ import annotations

import shutil

from rich.console import Console
from rich.panel import Panel

from tycoon.config import config
from tycoon.utils.console import error, header, info, success, warn

console = Console()


def _check_dbt_fusion():
    """Check if dbt-fusion is installed and warn the user."""
    if shutil.which("dbtf"):
        warn(
            "Found `dbtf` executable, which can conflict with `dbt`."
            " If you are not using dbt Fusion, you may want to uninstall it."
        )
    else:
        success("`dbtf` not found.")


def _check_tycoon_yml():
    """Check if tycoon.yml exists."""
    if config.has_project_file:
        success("`tycoon.yml` found.")
    else:
        error("`tycoon.yml` not found. Run `tycoon init` to create a new project.")


def _check_dbt_project():
    """Check if the dbt project exists and is configured correctly."""
    if config.dbt_project_dir.exists() and (config.dbt_project_dir / "dbt_project.yml").exists():
        success("dbt project found.")
    else:
        error("dbt project not found or is missing `dbt_project.yml`.")


def _check_rill_project():
    """Check if the rill project exists."""
    if config.rill_dir.exists():
        success("Rill project found.")
    else:
        warn("Rill project not found. `tycoon explore` will create it.")


def doctor_cmd() -> None:
    """Check the environment for potential issues."""
    header("Tycoon Doctor")

    with console.status("[bold green]Running checks...[/bold green]"):
        console.print(Panel("Checking for dbt-fusion...", expand=False))
        _check_dbt_fusion()

        console.print(Panel("Checking for tycoon.yml...", expand=False))
        _check_tycoon_yml()

        console.print(Panel("Checking for dbt project...", expand=False))
        _check_dbt_project()

        console.print(Panel("Checking for Rill project...", expand=False))
        _check_rill_project()

    info("All checks complete.")
