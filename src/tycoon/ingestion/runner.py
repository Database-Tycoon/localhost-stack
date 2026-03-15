"""Generic dlt pipeline runner for registered sources.

Runs a dlt pipeline for any source type registered in tycoon.yml.
For known source types (rest_api, sql_database, filesystem), it
dynamically constructs the appropriate dlt source. For NYC-transit
legacy pipelines, it delegates to the existing pipeline modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dlt

from tycoon.project import SourceConfig


# Legacy pipeline modules keyed by source name (NYC transit demo)
_LEGACY_PIPELINES: dict[str, str] = {
    "nyc-dot": "tycoon.ingestion.nyc_dot_pipeline",
    "mta-gtfs": "tycoon.ingestion.mta_pipeline",
    "mta-bus-speeds": "tycoon.ingestion.mta_bus_speeds_pipeline",
}


def _build_rest_api_source(source_config: SourceConfig) -> Any:
    """Build a dlt source for a generic REST API."""
    from dlt.sources.rest_api import rest_api_source

    cfg = source_config.config
    return rest_api_source(cfg)


def _build_sql_database_source(source_config: SourceConfig) -> Any:
    """Build a dlt source for a SQL database."""
    from dlt.sources.sql_database import sql_database

    cfg = source_config.config
    connection_string = cfg.get("connection_string", "")
    tables = source_config.tables
    if tables:
        return sql_database(connection_string, table_names=tables)
    return sql_database(connection_string)


def _build_filesystem_source(source_config: SourceConfig) -> Any:
    """Build a dlt source for filesystem (local, S3, GCS)."""
    from dlt.sources.filesystem import filesystem

    cfg = source_config.config
    bucket_url = cfg.get("bucket_url", cfg.get("path", "."))
    file_glob = cfg.get("file_glob", "**/*")
    return filesystem(bucket_url=bucket_url, file_glob=file_glob)


def run_source(
    name: str,
    source_config: SourceConfig,
    raw_db_path: Path,
    max_records: int | None = None,
    **kwargs: Any,
) -> tuple[dlt.Pipeline, Any]:
    """Run a dlt pipeline for a registered source.

    For legacy NYC pipelines, delegates to the existing pipeline modules.
    For generic sources, dynamically constructs the dlt source.

    Returns (pipeline, load_info).
    """
    # Legacy pipeline delegation
    if name in _LEGACY_PIPELINES:
        return _run_legacy(name, max_records=max_records, **kwargs)

    # Generic pipeline
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )

    source_type = source_config.type
    builders = {
        "rest_api": _build_rest_api_source,
        "sql_database": _build_sql_database_source,
        "filesystem": _build_filesystem_source,
    }

    builder = builders.get(source_type)
    if builder is None:
        # Try dynamic import: dlt.sources.<source_type>
        try:
            import importlib

            mod = importlib.import_module(f"dlt.sources.{source_type}")
            source_fn = getattr(mod, source_type, None)
            if source_fn is None:
                raise ImportError(f"No callable '{source_type}' in dlt.sources.{source_type}")
            dlt_source = source_fn(**source_config.config)
        except ImportError as exc:
            raise RuntimeError(
                f"Unknown source type '{source_type}'. "
                f"Install with: tycoon sources add {source_type}"
            ) from exc
    else:
        dlt_source = builder(source_config)

    load_info = pipeline.run(dlt_source)
    return pipeline, load_info


def _run_legacy(
    name: str,
    max_records: int | None = None,
    **kwargs: Any,
) -> tuple[dlt.Pipeline, Any]:
    """Run a legacy NYC transit pipeline by importing its module."""
    import importlib

    module_path = _LEGACY_PIPELINES[name]
    mod = importlib.import_module(module_path)
    return mod.run_pipeline(max_records=max_records, **kwargs)
