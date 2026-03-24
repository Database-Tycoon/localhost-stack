"""HubSpot dlt pipeline — contacts, companies, deals, tickets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator

import dlt
import httpx

from tycoon.project import SourceConfig

_BASE = "https://api.hubapi.com"
_CRM_OBJECTS = {
    "contacts": "/crm/v3/objects/contacts",
    "companies": "/crm/v3/objects/companies",
    "deals": "/crm/v3/objects/deals",
    "tickets": "/crm/v3/objects/tickets",
}


def _paginate(
    client: httpx.Client,
    path: str,
    params: dict[str, Any] | None = None,
) -> Generator:
    """Follow HubSpot's cursor pagination (paging.next.after)."""
    params = dict(params or {})
    params.setdefault("limit", 100)
    while True:
        resp = client.get(f"{_BASE}{path}", params=params)
        resp.raise_for_status()
        body = resp.json()
        yield from body.get("results", [])
        after = body.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        params["after"] = after


@dlt.source(name="hubspot")
def hubspot_source(api_key: str):
    """Contacts, companies, deals, and tickets from HubSpot CRM."""
    headers = {"Authorization": f"Bearer {api_key}"}

    def _make_resource(name: str, path: str):
        @dlt.resource(name=name, primary_key="id", write_disposition="replace")
        def _resource():
            with httpx.Client(headers=headers) as client:
                yield from _paginate(client, path)
        return _resource

    return tuple(_make_resource(name, path) for name, path in _CRM_OBJECTS.items())


def run_pipeline(
    name: str,
    source_config: SourceConfig,
    raw_db_path: Path,
    max_records: int | None = None,
) -> tuple[dlt.Pipeline, Any]:
    cfg = source_config.config
    source = hubspot_source(api_key=cfg.get("api_key", ""))
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
