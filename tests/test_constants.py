"""Tests for constants module — dataset IDs, ports, feeds."""

from __future__ import annotations

from tycoon import constants


class TestDatasetIDs:

    def test_traffic_speeds_non_empty(self):
        assert isinstance(constants.DATASET_TRAFFIC_SPEEDS, str)
        assert len(constants.DATASET_TRAFFIC_SPEEDS) > 0

    def test_bus_lanes_non_empty(self):
        assert isinstance(constants.DATASET_BUS_LANES, str)
        assert len(constants.DATASET_BUS_LANES) > 0

    def test_traffic_volume_non_empty(self):
        assert isinstance(constants.DATASET_TRAFFIC_VOLUME, str)
        assert len(constants.DATASET_TRAFFIC_VOLUME) > 0

    def test_bus_speeds_2023_2024_non_empty(self):
        assert isinstance(constants.DATASET_BUS_SPEEDS_2023_2024, str)
        assert len(constants.DATASET_BUS_SPEEDS_2023_2024) > 0

    def test_bus_speeds_2025_non_empty(self):
        assert isinstance(constants.DATASET_BUS_SPEEDS_2025, str)
        assert len(constants.DATASET_BUS_SPEEDS_2025) > 0


class TestPorts:

    def test_ports_are_integers(self):
        for name, port in constants.PORTS.items():
            assert isinstance(port, int), f"Port for {name} should be int"

    def test_ports_are_unique(self):
        values = list(constants.PORTS.values())
        assert len(values) == len(set(values)), "All ports must be unique"

    def test_expected_keys_present(self):
        expected_keys = {"dlt_ui", "duckdb_ui", "dbt_docs", "recce", "rill", "tycoon"}
        assert expected_keys.issubset(set(constants.PORTS.keys()))


class TestMTAGTFSFeeds:

    def test_has_expected_boroughs(self):
        expected = {"bronx", "brooklyn", "manhattan", "queens", "staten_island", "mta_bus"}
        assert expected.issubset(set(constants.MTA_GTFS_FEEDS.keys()))

    def test_feed_urls_non_empty(self):
        for borough, url in constants.MTA_GTFS_FEEDS.items():
            assert isinstance(url, str)
            assert url.startswith("https://"), f"Feed URL for {borough} must start with https://"


class TestDatabaseFilenames:

    def test_raw_db_filename(self):
        assert constants.RAW_DB == "nyc_open_data_raw.duckdb"

    def test_local_db_filename(self):
        assert constants.LOCAL_DB == "nyc_open_data_local.duckdb"
