"""Download and manage dlt verified sources on demand.

Sources are installed into ~/.tycoon/sources/ via `dlt init`, then a thin
_run.py shim is written alongside the source package to bridge dlt's native
API with tycoon's run_pipeline(name, source_config, raw_db_path, max_records)
interface.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

SOURCES_DIR = Path.home() / ".tycoon" / "sources"

# Per-source shim: imports from the dlt-init'd package, maps tycoon config keys
# to the dlt source function's parameters, and exposes run_pipeline().
_SHIMS: dict[str, str] = {
    "github": """\
from __future__ import annotations
from pathlib import Path
from typing import Any
import dlt
from github import github_reactions

def run_pipeline(name, source_config, raw_db_path, max_records=None):
    cfg = source_config.config
    source = github_reactions(
        owner=cfg.get("owner", ""),
        name=cfg.get("repo", ""),
        access_token=cfg.get("access_token", ""),
    )
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
""",
    "slack": """\
from __future__ import annotations
from pathlib import Path
from typing import Any
import dlt
from slack_source import slack_source

def run_pipeline(name, source_config, raw_db_path, max_records=None):
    cfg = source_config.config
    channel_ids = cfg.get("channel_ids", "")
    channels = [c.strip() for c in channel_ids.split(",") if c.strip()] or None
    source = slack_source(
        access_token=cfg.get("access_token", ""),
        channels=channels,
    )
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
""",
    "stripe_analytics": """\
from __future__ import annotations
from pathlib import Path
from typing import Any
import dlt
from stripe_analytics import stripe_source

def run_pipeline(name, source_config, raw_db_path, max_records=None):
    cfg = source_config.config
    source = stripe_source(
        stripe_secret_key=cfg.get("stripe_secret_key", ""),
    )
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
""",
    "hubspot": """\
from __future__ import annotations
from pathlib import Path
from typing import Any
import dlt
from hubspot import hubspot

def run_pipeline(name, source_config, raw_db_path, max_records=None):
    cfg = source_config.config
    source = hubspot(api_key=cfg.get("api_key", ""))
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
""",
    "notion": """\
from __future__ import annotations
from pathlib import Path
from typing import Any
import dlt
from notion import notion_databases

def run_pipeline(name, source_config, raw_db_path, max_records=None):
    cfg = source_config.config
    raw_ids = cfg.get("database_ids", "")
    database_ids = [d.strip() for d in raw_ids.split(",") if d.strip()] or None
    source = notion_databases(
        database_ids=database_ids,
        api_key=cfg.get("api_key", ""),
    )
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
""",
}

# Maps catalog source type → dlt init source name (they sometimes differ)
_DLT_INIT_NAME: dict[str, str] = {
    "github": "github",
    "slack": "slack",
    "stripe": "stripe_analytics",
    "hubspot": "hubspot",
    "notion": "notion",
}


def is_source_installed(source_type: str) -> bool:
    """Return True if the source package exists in SOURCES_DIR."""
    dlt_name = _DLT_INIT_NAME.get(source_type, source_type)
    source_pkg = SOURCES_DIR / dlt_name
    return source_pkg.is_dir() and (source_pkg / "__init__.py").exists()


def install_source(source_type: str) -> bool:
    """Run `dlt init <source> duckdb` into SOURCES_DIR, then write a _run.py shim.

    Returns True on success, False on failure.
    """
    dlt_name = _DLT_INIT_NAME.get(source_type, source_type)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [sys.executable, "-m", "dlt", "init", dlt_name, "duckdb"],
        cwd=SOURCES_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return False

    # Write the _run.py shim into the downloaded source package
    shim = _SHIMS.get(dlt_name)
    if shim:
        shim_path = SOURCES_DIR / dlt_name / "_run.py"
        shim_path.write_text(shim)

    return True


def get_run_module_path(source_type: str) -> str:
    """Return the dotted module path for the _run shim, e.g. 'github._run'."""
    dlt_name = _DLT_INIT_NAME.get(source_type, source_type)
    return f"{dlt_name}._run"
