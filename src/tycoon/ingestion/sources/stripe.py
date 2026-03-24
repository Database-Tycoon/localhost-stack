"""Stripe dlt pipeline — customers, subscriptions, invoices, charges, products."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator

import dlt
import httpx

from tycoon.project import SourceConfig

_BASE = "https://api.stripe.com/v1"
_ENDPOINTS = {
    "customers": "/customers",
    "subscriptions": "/subscriptions",
    "invoices": "/invoices",
    "charges": "/charges",
    "products": "/products",
}


def _paginate(
    client: httpx.Client,
    path: str,
    params: dict[str, Any] | None = None,
) -> Generator:
    """Follow Stripe's cursor pagination (starting_after + has_more)."""
    params = dict(params or {})
    params.setdefault("limit", 100)
    while True:
        resp = client.get(f"{_BASE}{path}", params=params)
        resp.raise_for_status()
        body = resp.json()
        items = body.get("data", [])
        yield from items
        if not body.get("has_more") or not items:
            break
        params["starting_after"] = items[-1]["id"]


@dlt.source(name="stripe")
def stripe_source(stripe_secret_key: str):
    """Customers, subscriptions, invoices, charges, and products from Stripe."""
    # Stripe uses HTTP Basic auth: key as username, empty password
    auth = httpx.BasicAuth(username=stripe_secret_key, password="")

    def _make_resource(name: str, path: str):
        @dlt.resource(name=name, primary_key="id", write_disposition="replace")
        def _resource():
            with httpx.Client(auth=auth) as client:
                yield from _paginate(client, path)
        return _resource

    return tuple(_make_resource(name, path) for name, path in _ENDPOINTS.items())


def run_pipeline(
    name: str,
    source_config: SourceConfig,
    raw_db_path: Path,
    max_records: int | None = None,
) -> tuple[dlt.Pipeline, Any]:
    cfg = source_config.config
    source = stripe_source(stripe_secret_key=cfg.get("stripe_secret_key", ""))
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
