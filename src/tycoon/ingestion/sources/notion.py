"""Notion dlt pipeline — databases, pages, and users."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator

import dlt
import httpx

from tycoon.project import SourceConfig

_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _get_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _search(client: httpx.Client, filter_type: str) -> Generator:
    """Paginate through POST /search results for a given object type."""
    body: dict[str, Any] = {
        "filter": {"value": filter_type, "property": "object"},
        "page_size": 100,
    }
    while True:
        resp = client.post(f"{_BASE}/search", json=body)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("results", [])
        if not data.get("has_more"):
            break
        body["start_cursor"] = data["next_cursor"]


def _query_database(client: httpx.Client, database_id: str) -> Generator:
    """Paginate through POST /databases/{id}/query."""
    body: dict[str, Any] = {"page_size": 100}
    while True:
        resp = client.post(f"{_BASE}/databases/{database_id}/query", json=body)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("results", [])
        if not data.get("has_more"):
            break
        body["start_cursor"] = data["next_cursor"]


@dlt.source(name="notion")
def notion_source(api_key: str, database_ids: list[str] | None = None):
    """Databases, pages, and users from a Notion workspace."""
    headers = _get_headers(api_key)

    @dlt.resource(primary_key="id", write_disposition="replace")
    def users():
        with httpx.Client(headers=headers) as client:
            resp = client.get(f"{_BASE}/users")
            resp.raise_for_status()
            yield from resp.json().get("results", [])

    @dlt.resource(primary_key="id", write_disposition="replace")
    def databases():
        with httpx.Client(headers=headers) as client:
            if database_ids:
                for db_id in database_ids:
                    resp = client.get(f"{_BASE}/databases/{db_id}")
                    resp.raise_for_status()
                    yield resp.json()
            else:
                yield from _search(client, "database")

    @dlt.resource(primary_key="id", write_disposition="replace")
    def pages():
        """All pages from specified databases, or all accessible databases."""
        with httpx.Client(headers=headers) as client:
            target_ids: list[str]
            if database_ids:
                target_ids = database_ids
            else:
                target_ids = [db["id"] for db in _search(client, "database")]
            for db_id in target_ids:
                yield from _query_database(client, db_id)

    return users, databases, pages


def run_pipeline(
    name: str,
    source_config: SourceConfig,
    raw_db_path: Path,
    max_records: int | None = None,
) -> tuple[dlt.Pipeline, Any]:
    cfg = source_config.config
    raw_ids = cfg.get("database_ids", "")
    database_ids = [d.strip() for d in raw_ids.split(",") if d.strip()] if raw_ids else None

    source = notion_source(
        api_key=cfg.get("api_key", ""),
        database_ids=database_ids,
    )
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
