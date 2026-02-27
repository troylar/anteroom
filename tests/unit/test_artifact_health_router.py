"""Tests for artifact health check API endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anteroom.routers.artifact_health import router
from anteroom.services.artifact_health import HealthIssue, HealthReport, HealthSeverity


@pytest.fixture()
def app() -> FastAPI:
    app = FastAPI()
    app.state.db = MagicMock()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestArtifactHealthEndpoint:
    def test_healthy_report(self, client: TestClient) -> None:
        report = HealthReport(artifact_count=3, total_size_bytes=500, estimated_tokens=125)
        with patch("anteroom.routers.artifact_health.artifact_health") as mock:
            mock.run_health_check.return_value = report
            resp = client.get("/api/artifacts/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is True
        assert data["artifact_count"] == 3
        assert data["issues"] == []

    def test_unhealthy_report(self, client: TestClient) -> None:
        report = HealthReport(
            artifact_count=5,
            issues=[
                HealthIssue(
                    severity=HealthSeverity.ERROR,
                    category="config_conflict",
                    message="Config conflict on 'key'",
                    details={"field": "key"},
                )
            ],
        )
        with patch("anteroom.routers.artifact_health.artifact_health") as mock:
            mock.run_health_check.return_value = report
            resp = client.get("/api/artifacts/check")
        data = resp.json()
        assert data["healthy"] is False
        assert data["error_count"] == 1
        assert len(data["issues"]) == 1
        assert data["issues"][0]["category"] == "config_conflict"

    def test_called_with_db(self, client: TestClient, app: FastAPI) -> None:
        report = HealthReport()
        with patch("anteroom.routers.artifact_health.artifact_health") as mock:
            mock.run_health_check.return_value = report
            client.get("/api/artifacts/check")
            mock.run_health_check.assert_called_once_with(app.state.db)

    def test_source_path_stripped_from_details(self, client: TestClient) -> None:
        report = HealthReport(
            issues=[
                HealthIssue(
                    severity=HealthSeverity.WARN,
                    category="test",
                    message="test",
                    details={"source_path": "/secret/path", "other": "ok"},
                )
            ],
        )
        with patch("anteroom.routers.artifact_health.artifact_health") as mock:
            mock.run_health_check.return_value = report
            resp = client.get("/api/artifacts/check")
        data = resp.json()
        assert "source_path" not in data["issues"][0]["details"]
        assert data["issues"][0]["details"]["other"] == "ok"

    def test_report_structure(self, client: TestClient) -> None:
        report = HealthReport(
            artifact_count=2,
            pack_count=1,
            total_size_bytes=100,
            estimated_tokens=25,
            issues=[
                HealthIssue(HealthSeverity.WARN, "test", "msg", {"key": "val"}, fixable=True),
            ],
        )
        with patch("anteroom.routers.artifact_health.artifact_health") as mock:
            mock.run_health_check.return_value = report
            resp = client.get("/api/artifacts/check")
        data = resp.json()
        assert set(data.keys()) == {
            "healthy",
            "artifact_count",
            "pack_count",
            "total_size_bytes",
            "estimated_tokens",
            "error_count",
            "warn_count",
            "info_count",
            "issues",
        }
        issue = data["issues"][0]
        assert set(issue.keys()) == {"severity", "category", "message", "details", "fixable"}
        assert issue["fixable"] is True
