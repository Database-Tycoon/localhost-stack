"""REST API routes for the Tycoon dashboard server."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from tycoon.config import config
from tycoon.constants import PORTS
from tycoon.server.subprocess_manager import subprocess_manager
from tycoon.utils.duckdb_utils import db_file_size_mb, get_tables
from tycoon.utils.process import is_port_in_use

router = APIRouter(prefix="/api")


def _dbt_run_results() -> dict:
    """Parse dbt run_results.json if it exists."""
    results_path = config.dbt_project_dir / "target" / "run_results.json"
    if not results_path.exists():
        return {}
    try:
        data = json.loads(results_path.read_text())
        statuses: dict[str, int] = {}
        for r in data.get("results", []):
            s = r.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "elapsed_time": data.get("elapsed_time"),
            "generated_at": data.get("metadata", {}).get("generated_at"),
            **statuses,
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def _db_info(db_path: Path) -> dict:
    """Return size and table count for a database file."""
    size = db_file_size_mb(db_path)
    tables = get_tables(db_path)
    return {
        "size_mb": round(size, 2) if size is not None else None,
        "table_count": len(tables) if tables else None,
        "tables": [f"{s}.{t}" for s, t in tables],
    }


@router.get("/status")
async def status() -> dict:
    """Live status of services, databases, and dbt results."""
    services = {}
    for name, port in PORTS.items():
        services[name] = {
            "port": port,
            "healthy": is_port_in_use(port),
        }

    databases = {
        "raw_db": _db_info(config.raw_db),
        "local_db": _db_info(config.local_db),
    }

    return {
        "services": services,
        "databases": databases,
        "dbt": _dbt_run_results(),
        "busy": subprocess_manager.is_busy(),
        "active_run_id": subprocess_manager.active_run_id,
    }


@router.post("/run/pipeline/{pipeline_id}")
async def run_pipeline(pipeline_id: str) -> dict:
    """Spawn a dlt pipeline subprocess."""
    if subprocess_manager.is_busy():
        raise HTTPException(
            status_code=409,
            detail=f"Another run is active: {subprocess_manager.active_run_id}",
        )

    run_id = f"pipeline-{pipeline_id}-{uuid.uuid4().hex[:8]}"
    cmd = [
        "dlt",
        "pipeline",
        pipeline_id,
        "run",
    ]

    try:
        await subprocess_manager.start_run(run_id, cmd)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"run_id": run_id, "cmd": cmd}


@router.post("/run/dbt")
async def run_dbt() -> dict:
    """Spawn a dbt build subprocess."""
    if subprocess_manager.is_busy():
        raise HTTPException(
            status_code=409,
            detail=f"Another run is active: {subprocess_manager.active_run_id}",
        )

    run_id = f"dbt-{uuid.uuid4().hex[:8]}"
    cmd = [
        "dbt",
        "build",
        "--project-dir",
        str(config.dbt_project_dir),
        "--profiles-dir",
        str(config.dbt_project_dir),
    ]

    try:
        await subprocess_manager.start_run(run_id, cmd)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"run_id": run_id, "cmd": cmd}
