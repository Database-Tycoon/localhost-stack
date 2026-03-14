"""Tests for the FastAPI server app and routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tycoon.server.app import create_app
from tycoon.server.subprocess_manager import SubprocessManager


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    application = create_app()
    return TestClient(application)


class TestSPARoot:

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_html(self, client):
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_root_contains_dashboard_title(self, client):
        response = client.get("/")
        assert "Tycoon Dashboard" in response.text


class TestStatusEndpoint:

    def test_status_returns_200(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_status_returns_json(self, client):
        response = client.get("/api/status")
        data = response.json()
        assert isinstance(data, dict)

    def test_status_has_expected_keys(self, client):
        response = client.get("/api/status")
        data = response.json()
        for key in ("services", "databases", "busy", "active_run_id"):
            assert key in data, f"Expected key '{key}' in status response"

    def test_status_services_has_port_entries(self, client):
        response = client.get("/api/status")
        services = response.json()["services"]
        assert isinstance(services, dict)
        # Each service should have port and healthy keys
        for name, svc_info in services.items():
            assert "port" in svc_info, f"Service {name} missing 'port'"
            assert "healthy" in svc_info, f"Service {name} missing 'healthy'"

    def test_status_databases_has_raw_and_local(self, client):
        response = client.get("/api/status")
        databases = response.json()["databases"]
        assert "raw_db" in databases
        assert "local_db" in databases


class TestSubprocessManager:

    def test_initial_not_busy(self):
        manager = SubprocessManager()
        assert manager.is_busy() is False

    def test_initial_no_active_run(self):
        manager = SubprocessManager()
        assert manager.active_run_id is None

    def test_get_run_returns_none_for_unknown(self):
        manager = SubprocessManager()
        assert manager.get_run("nonexistent") is None
