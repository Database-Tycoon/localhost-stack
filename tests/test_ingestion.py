"""Ingestion module import and decorator tests.

These tests verify that pipeline modules can be imported and that dlt
decorators are properly applied. They do NOT call any external APIs.
"""

from __future__ import annotations

import importlib


class TestNYCDotPipeline:

    def test_module_imports(self):
        mod = importlib.import_module("tycoon.ingestion.nyc_dot_pipeline")
        assert mod is not None

    def test_has_run_pipeline(self):
        from tycoon.ingestion import nyc_dot_pipeline

        assert hasattr(nyc_dot_pipeline, "run_pipeline")
        assert callable(nyc_dot_pipeline.run_pipeline)

    def test_has_dlt_source(self):
        from tycoon.ingestion import nyc_dot_pipeline

        # The source function should exist (name matches the @dlt.source decorator)
        assert hasattr(nyc_dot_pipeline, "nyc_dot_source")

    def test_has_dlt_resources(self):
        from tycoon.ingestion import nyc_dot_pipeline

        for name in ("traffic_speeds_nbe", "bus_lanes", "traffic_volume_counts"):
            assert hasattr(nyc_dot_pipeline, name), f"Missing resource: {name}"


class TestMTAPipeline:

    def test_module_imports(self):
        mod = importlib.import_module("tycoon.ingestion.mta_pipeline")
        assert mod is not None

    def test_has_run_pipeline(self):
        from tycoon.ingestion import mta_pipeline

        assert hasattr(mta_pipeline, "run_pipeline")
        assert callable(mta_pipeline.run_pipeline)

    def test_has_dlt_source(self):
        from tycoon.ingestion import mta_pipeline

        assert hasattr(mta_pipeline, "mta_source")

    def test_has_dlt_resources(self):
        from tycoon.ingestion import mta_pipeline

        for name in ("gtfs_routes", "gtfs_stops"):
            assert hasattr(mta_pipeline, name), f"Missing resource: {name}"


class TestMTABusSpeedsPipeline:

    def test_module_imports(self):
        mod = importlib.import_module("tycoon.ingestion.mta_bus_speeds_pipeline")
        assert mod is not None

    def test_has_run_pipeline(self):
        from tycoon.ingestion import mta_bus_speeds_pipeline

        assert hasattr(mta_bus_speeds_pipeline, "run_pipeline")
        assert callable(mta_bus_speeds_pipeline.run_pipeline)

    def test_has_dlt_source(self):
        from tycoon.ingestion import mta_bus_speeds_pipeline

        assert hasattr(mta_bus_speeds_pipeline, "mta_bus_speeds_source")

    def test_has_dlt_resources(self):
        from tycoon.ingestion import mta_bus_speeds_pipeline

        for name in ("bus_segment_speeds_2023_2024", "bus_segment_speeds_2025"):
            assert hasattr(mta_bus_speeds_pipeline, name), f"Missing resource: {name}"
