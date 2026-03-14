"""Path and configuration resolution."""

from __future__ import annotations

from pathlib import Path

from tycoon.constants import DBT_PROJECT_DIR, LOCAL_DB, RAW_DB


def _find_project_root() -> Path:
    """Walk up from CWD to find the directory containing pyproject.toml."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current


class TycoonConfig:
    """Centralised path / config resolution."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.root = project_root or _find_project_root()
        self.data_dir = self.root / "data"
        self.raw_db = self.data_dir / RAW_DB
        self.local_db = self.data_dir / LOCAL_DB
        self.dbt_project_dir = self.root / DBT_PROJECT_DIR
        self.rill_dir = self.root / "rill"

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Singleton
config = TycoonConfig()
