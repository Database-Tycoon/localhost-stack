"""Template discovery and project scaffolding.

Discovers bundled templates from the ``src/tycoon/templates/`` directory and
provides helpers to scaffold new tycoon projects -- either blank or from a
named template.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tycoon.utils.console import info, success, warn


# ---------------------------------------------------------------------------
# Template directory resolution
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def list_templates() -> list[str]:
    """Return names of available templates.

    Each subdirectory under ``src/tycoon/templates/`` that contains a
    ``tycoon.yml`` file is considered a template.
    """
    if not _TEMPLATES_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in _TEMPLATES_DIR.iterdir()
        if d.is_dir() and (d / "tycoon.yml").exists()
    )


def get_template_path(name: str) -> Path:
    """Return the path to a template directory.

    Raises ``FileNotFoundError`` if the template does not exist or has no
    ``tycoon.yml``.
    """
    path = _TEMPLATES_DIR / name
    if not path.is_dir() or not (path / "tycoon.yml").exists():
        available = list_templates()
        raise FileNotFoundError(
            f"Template '{name}' not found. "
            f"Available templates: {', '.join(available) or '(none)'}"
        )
    return path


# ---------------------------------------------------------------------------
# Blank project scaffolding
# ---------------------------------------------------------------------------

_GITIGNORE_CONTENT = """\
# Tycoon
data/*.duckdb
data/*.duckdb.wal
*.duckdb.wal

# Python
__pycache__/
*.pyc
.venv/

# dbt
dbt_project/target/
dbt_project/dbt_packages/
dbt_project/logs/

# OS
.DS_Store
"""


def scaffold_blank_project(target: Path, name: str) -> None:
    """Create a minimal tycoon project with an empty ``tycoon.yml``.

    Creates:
    - ``tycoon.yml`` with the given project name and default database paths
    - ``data/`` directory
    - ``dbt_project/`` with minimal ``dbt_project.yml`` and ``profiles.yml``
    - ``.gitignore``

    The generated ``profiles.yml`` uses the database paths declared in the
    project config (``database.raw`` and ``database.warehouse``) so that dbt
    targets are consistent with tycoon's own path resolution.
    """
    raw_db_path = "data/raw.duckdb"
    warehouse_db_path = "data/warehouse.duckdb"

    # tycoon.yml
    project_data = {
        "name": name,
        "version": "0.1.0",
        "database": {
            "raw": raw_db_path,
            "warehouse": warehouse_db_path,
        },
        "dbt_project_dir": "dbt_project",
        "rill_dir": "rill",
        "sources": {},
    }
    yml_path = target / "tycoon.yml"
    yml_path.write_text(yaml.dump(project_data, default_flow_style=False, sort_keys=False))
    success(f"Created {yml_path.relative_to(target)}")

    # data/
    (target / "data").mkdir(parents=True, exist_ok=True)
    info("Created data/")

    # dbt_project/
    dbt_dir = target / "dbt_project"
    dbt_dir.mkdir(parents=True, exist_ok=True)

    profile_name = name.replace("-", "_")

    dbt_project_yml = {
        "name": profile_name,
        "version": "1.0.0",
        "config-version": 2,
        "profile": profile_name,
    }
    (dbt_dir / "dbt_project.yml").write_text(
        yaml.dump(dbt_project_yml, default_flow_style=False, sort_keys=False)
    )

    # profiles.yml: warehouse DB is the dbt target; raw DB is attached read-only
    # Paths are relative to dbt_project_dir (one level above data/)
    warehouse_rel = f"../{warehouse_db_path}"
    raw_rel = f"../{raw_db_path}"

    profiles_data = {
        profile_name: {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": warehouse_rel,
                    "attach": [
                        {
                            "path": raw_rel,
                            "alias": "raw",
                            "read_only": True,
                        }
                    ],
                }
            },
        }
    }
    (dbt_dir / "profiles.yml").write_text(
        yaml.dump(profiles_data, default_flow_style=False, sort_keys=False)
    )
    info("Created dbt_project/ with dbt_project.yml and profiles.yml")

    # .gitignore
    _write_gitignore(target)


# ---------------------------------------------------------------------------
# Template-based scaffolding
# ---------------------------------------------------------------------------


def scaffold_from_template(target: Path, template_name: str) -> None:
    """Copy a template into the target directory.

    Copies ``tycoon.yml`` from the template. For directories like
    ``dbt_project/`` and ``rill/``, checks whether they already exist in the
    target (e.g. when running inside the localhost-stack repo) and skips if so.

    Also creates ``data/`` and ``.gitignore`` if not present.
    """
    template_path = get_template_path(template_name)

    # Copy tycoon.yml
    src_yml = template_path / "tycoon.yml"
    dst_yml = target / "tycoon.yml"
    if dst_yml.exists():
        warn(f"tycoon.yml already exists, skipping")
    else:
        shutil.copy2(src_yml, dst_yml)
        success(f"Created tycoon.yml from template '{template_name}'")

    # Copy any subdirectories from the template (e.g. dbt_project/, rill/)
    for item in template_path.iterdir():
        if item.name == "tycoon.yml" or item.name == "README":
            continue
        dst = target / item.name
        if item.is_dir():
            if dst.exists():
                warn(f"{item.name}/ already exists, skipping")
            else:
                shutil.copytree(item, dst)
                success(f"Created {item.name}/ from template")
        elif item.is_file():
            if dst.exists():
                warn(f"{item.name} already exists, skipping")
            else:
                shutil.copy2(item, dst)
                success(f"Created {item.name} from template")

    # data/
    (target / "data").mkdir(parents=True, exist_ok=True)
    info("Ensured data/ directory exists")

    # .gitignore
    _write_gitignore(target)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_gitignore(target: Path) -> None:
    """Write ``.gitignore`` if it does not already exist."""
    gitignore = target / ".gitignore"
    if gitignore.exists():
        warn(".gitignore already exists, skipping")
    else:
        gitignore.write_text(_GITIGNORE_CONTENT)
        info("Created .gitignore")
