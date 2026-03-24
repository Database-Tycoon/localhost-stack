"""GitHub dlt pipeline — issues, pull requests, and commits."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator

import dlt
import httpx

from tycoon.project import SourceConfig


def _paginate(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> Generator:
    """Follow GitHub's Link header pagination."""
    params = params or {}
    while url:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        yield from data
        link = resp.headers.get("Link", "")
        url = next(
            (part.split(";")[0].strip().strip("<>")
             for part in link.split(",")
             if 'rel="next"' in part),
            None,
        )
        params = {}  # Already encoded in next URL


@dlt.source(name="github")
def github_source(access_token: str, owner: str, repo: str):
    """Issues, pull requests, and commits for a GitHub repository."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"https://api.github.com/repos/{owner}/{repo}"

    @dlt.resource(primary_key="id", write_disposition="replace")
    def issues():
        with httpx.Client(headers=headers) as client:
            yield from _paginate(client, f"{base}/issues", {"state": "all", "per_page": 100})

    @dlt.resource(primary_key="id", write_disposition="replace")
    def pull_requests():
        with httpx.Client(headers=headers) as client:
            yield from _paginate(client, f"{base}/pulls", {"state": "all", "per_page": 100})

    @dlt.resource(primary_key="sha", write_disposition="replace")
    def commits():
        with httpx.Client(headers=headers) as client:
            yield from _paginate(client, f"{base}/commits", {"per_page": 100})

    return issues, pull_requests, commits


def run_pipeline(
    name: str,
    source_config: SourceConfig,
    raw_db_path: Path,
    max_records: int | None = None,
) -> tuple[dlt.Pipeline, Any]:
    cfg = source_config.config
    source = github_source(
        access_token=cfg.get("access_token", ""),
        owner=cfg.get("owner", ""),
        repo=cfg.get("repo", ""),
    )
    if max_records:
        source = source.add_limit(max_records)
    pipeline = dlt.pipeline(
        pipeline_name=name,
        destination=dlt.destinations.duckdb(str(raw_db_path)),
        dataset_name=source_config.schema_name,
    )
    return pipeline, pipeline.run(source)
