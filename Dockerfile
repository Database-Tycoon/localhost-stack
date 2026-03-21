FROM python:3.12-slim AS base

# System deps for duckdb, dbt, and building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project metadata first for layer caching
COPY pyproject.toml ./
COPY src/ src/

# Install the package and all dependencies
RUN uv pip install --system --no-cache ".[dagster]"

# Copy the rest of the project
COPY tycoon.yml ./
COPY dbt_project/ dbt_project/
COPY rill/ rill/

# Ensure data directory exists
RUN mkdir -p data

EXPOSE 8888

CMD ["tycoon", "serve", "--host", "0.0.0.0"]
