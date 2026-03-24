"""Slack dlt pipeline — channels, users, and messages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator

import dlt
import httpx

from tycoon.project import SourceConfig

_BASE = "https://slack.com/api"


def _paginate_cursor(
    client: httpx.Client,
    endpoint: str,
    data_key: str,
    params: dict[str, Any] | None = None,
) -> Generator:
    """Follow Slack's cursor-based pagination (response_metadata.next_cursor)."""
    params = dict(params or {})
    while True:
        resp = client.get(f"{_BASE}/{endpoint}", params=params)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            raise RuntimeError(f"Slack API error: {body.get('error', 'unknown')}")
        yield from body.get(data_key, [])
        cursor = body.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        params["cursor"] = cursor


@dlt.source(name="slack")
def slack_source(access_token: str, channel_ids: list[str] | None = None):
    """Channels, users, and messages from a Slack workspace."""
    headers = {"Authorization": f"Bearer {access_token}"}

    @dlt.resource(primary_key="id", write_disposition="replace")
    def channels():
        with httpx.Client(headers=headers) as client:
            yield from _paginate_cursor(
                client,
                "conversations.list",
                "channels",
                {"limit": 200, "types": "public_channel,private_channel"},
            )

    @dlt.resource(primary_key="id", write_disposition="replace")
    def users():
        with httpx.Client(headers=headers) as client:
            yield from _paginate_cursor(client, "users.list", "members", {"limit": 200})

    @dlt.resource(primary_key=["channel", "ts"], write_disposition="append")
    def messages():
        """Fetch message history for each channel (or the specified channel_ids)."""
        with httpx.Client(headers=headers) as client:
            # Resolve which channels to sync
            target_ids: list[str]
            if channel_ids:
                target_ids = channel_ids
            else:
                target_ids = [
                    ch["id"]
                    for ch in _paginate_cursor(
                        client,
                        "conversations.list",
                        "channels",
                        {"limit": 200, "types": "public_channel"},
                    )
                ]
            for channel_id in target_ids:
                for msg in _paginate_cursor(
                    client,
                    "conversations.history",
                    "messages",
                    {"channel": channel_id, "limit": 200},
                ):
                    yield {**msg, "channel": channel_id}

    return channels, users, messages


def run_pipeline(
    name: str,
    source_config: SourceConfig,
    raw_db_path: Path,
    max_records: int | None = None,
) -> tuple[dlt.Pipeline, Any]:
    cfg = source_config.config
    raw_ids = cfg.get("channel_ids", "")
    channel_ids = [c.strip() for c in raw_ids.split(",") if c.strip()] if raw_ids else None

    source = slack_source(
        access_token=cfg.get("access_token", ""),
        channel_ids=channel_ids,
    )
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
