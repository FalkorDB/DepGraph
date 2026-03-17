"""Tests for the FastAPI REST API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from depgraph.models import (
    BlastRadiusResult,
    CentralityResult,
    CycleResult,
    DepthResult,
    GraphStats,
    LicenseReport,
    PackageInfo,
)


@pytest.fixture
def mock_engine() -> MagicMock:
    """Create a mock AnalysisEngine."""
    engine = MagicMock()
    engine.get_package.return_value = PackageInfo(
        name="express",
        version="4.18.2",
        license="MIT",
        description="Web framework",
        downloads=50000000,
    )
    engine.list_packages.return_value = [
        PackageInfo(
            name="express",
            version="4.18.2",
            license="MIT",
            description="Web framework",
            downloads=50000000,
        ),
    ]
    engine.search_packages.return_value = []
    engine.blast_radius.return_value = BlastRadiusResult(
        source_package="express", affected_packages=[], total_affected=0, max_depth=0
    )
    engine.find_cycles.return_value = CycleResult(cycles=[], total_cycles=0)
    engine.centrality.return_value = CentralityResult(packages=[])
    engine.license_check.return_value = LicenseReport(
        root_package="express", issues=[], total_dependencies_checked=0
    )
    engine.dependency_depth.return_value = DepthResult(
        package="express", max_depth=0, dependency_count=0, tree={}
    )
    engine.graph_stats.return_value = GraphStats(
        packages=10, dependencies=20, vulnerabilities=2, maintainers=5
    )
    return engine


@pytest.fixture
def client(mock_engine: MagicMock) -> TestClient:
    """Create a test client with mocked engine."""
    import depgraph.api as api_module

    api_module._engine = mock_engine
    api_module._db = MagicMock()
    api_module._db.health_check.return_value = True
    api_module._db._config.graph_name = "test"
    api_module._db.graph.query.return_value = MagicMock(result_set=[[10, 20, 2, 5]])

    from depgraph.api import app

    with patch(
        "depgraph.api.get_stats",
        return_value={"packages": 10, "vulnerabilities": 2, "maintainers": 5, "dependencies": 20},
    ):
        return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client: TestClient) -> None:
        with patch(
            "depgraph.api.get_stats",
            return_value={
                "packages": 10,
                "vulnerabilities": 2,
                "maintainers": 5,
                "dependencies": 20,
            },
        ):
            response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["falkordb_connected"] is True


class TestPackageEndpoints:
    def test_list_packages(self, client: TestClient, mock_engine: MagicMock) -> None:
        response = client.get("/packages")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_package(self, client: TestClient) -> None:
        response = client.get("/packages/express")
        assert response.status_code == 200
        assert response.json()["name"] == "express"

    def test_get_package_not_found(self, client: TestClient, mock_engine: MagicMock) -> None:
        mock_engine.get_package.return_value = None
        response = client.get("/packages/nonexistent")
        assert response.status_code == 404


class TestAnalysisEndpoints:
    def test_blast_radius(self, client: TestClient) -> None:
        response = client.get("/analysis/blast-radius/express")
        assert response.status_code == 200
        assert response.json()["source_package"] == "express"

    def test_cycles(self, client: TestClient) -> None:
        response = client.get("/analysis/cycles")
        assert response.status_code == 200
        assert "cycles" in response.json()

    def test_centrality(self, client: TestClient) -> None:
        response = client.get("/analysis/centrality")
        assert response.status_code == 200

    def test_licenses(self, client: TestClient) -> None:
        response = client.get("/analysis/licenses/express")
        assert response.status_code == 200

    def test_depth(self, client: TestClient) -> None:
        response = client.get("/analysis/depth/express")
        assert response.status_code == 200

    def test_stats(self, client: TestClient) -> None:
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["packages"] == 10
