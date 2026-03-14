"""Dataset IDs, API URLs, ports, and other constants."""

# NYC DOT datasets (data.cityofnewyork.us)
NYC_DOT_DOMAIN = "data.cityofnewyork.us"
DATASET_TRAFFIC_SPEEDS = "i4gi-tjb9"
DATASET_BUS_LANES = "ycrg-ses3"
DATASET_TRAFFIC_VOLUME = "7ym2-wayt"

# MTA GTFS feeds
MTA_GTFS_BASE_URL = "https://rrgtfsfeeds.s3.amazonaws.com"
MTA_GTFS_FEEDS = {
    "bronx": f"{MTA_GTFS_BASE_URL}/gtfs_bx.zip",
    "brooklyn": f"{MTA_GTFS_BASE_URL}/gtfs_b.zip",
    "manhattan": f"{MTA_GTFS_BASE_URL}/gtfs_m.zip",
    "queens": f"{MTA_GTFS_BASE_URL}/gtfs_q.zip",
    "staten_island": f"{MTA_GTFS_BASE_URL}/gtfs_si.zip",
    "mta_bus": f"{MTA_GTFS_BASE_URL}/gtfs_busco.zip",
}

# MTA Bus Speeds datasets (data.ny.gov)
MTA_BUS_SPEEDS_DOMAIN = "data.ny.gov"
DATASET_BUS_SPEEDS_2023_2024 = "58t6-89vi"
DATASET_BUS_SPEEDS_2025 = "kufs-yh3x"

# Socrata API pagination
SOCRATA_PAGE_SIZE = 50_000

# Service ports
PORTS = {
    "dlt_ui": 2718,
    "duckdb_ui": 4213,
    "dbt_docs": 8080,
    "recce": 8000,
    "rill": 9009,
    "tycoon": 8888,
}

# Database filenames
RAW_DB = "nyc_open_data_raw.duckdb"
LOCAL_DB = "nyc_open_data_local.duckdb"

# dbt schemas
RAW_SCHEMAS = {
    "nyc_dot": "raw_nyc_dot",
    "mta": "raw_mta",
    "mta_bus_speeds": "raw_mta_bus_speeds",
}

# dbt project paths (relative to project root)
DBT_PROJECT_DIR = "dbt_project"
