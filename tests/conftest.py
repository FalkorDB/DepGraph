"""Shared fixtures for tests."""

from __future__ import annotations

from typing import Any

import pytest

from depgraph.config import FalkorDBConfig
from depgraph.graph.engine import AnalysisEngine


class MockQueryResult:
    """Mock FalkorDB query result."""

    def __init__(self, result_set: list[list[Any]] | None = None) -> None:
        self.result_set = result_set or []


class MockGraph:
    """Mock FalkorDB graph for unit testing."""

    def __init__(self) -> None:
        self._data: dict[str, list[list[Any]]] = {}
        self._call_log: list[tuple[str, dict[str, Any] | None]] = []

    def set_response(self, query_prefix: str, result_set: list[list[Any]]) -> None:
        """Set canned responses for queries starting with a given prefix."""
        self._data[query_prefix] = result_set

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> MockQueryResult:
        """Execute a mock query, returning canned response if available."""
        self._call_log.append((cypher, params))
        for prefix, result_set in self._data.items():
            if prefix in cypher:
                return MockQueryResult(result_set)
        return MockQueryResult([])

    @property
    def call_log(self) -> list[tuple[str, dict[str, Any] | None]]:
        return self._call_log


@pytest.fixture
def mock_graph() -> MockGraph:
    """Provide a mock FalkorDB graph."""
    return MockGraph()


@pytest.fixture
def engine(mock_graph: MockGraph) -> AnalysisEngine:
    """Provide an AnalysisEngine backed by a mock graph."""
    return AnalysisEngine(mock_graph, max_depth=10)  # type: ignore[arg-type]


@pytest.fixture
def config() -> FalkorDBConfig:
    """Provide a test config."""
    return FalkorDBConfig(host="localhost", port=6379, graph_name="depgraph_test")


@pytest.fixture
def sample_ecosystem() -> dict[str, Any]:
    """Provide a small sample ecosystem for testing."""
    return {
        "packages": [
            {
                "name": "app",
                "version": "1.0.0",
                "license": "MIT",
                "description": "Main app",
                "downloads": 1000,
            },
            {
                "name": "lib-a",
                "version": "2.0.0",
                "license": "MIT",
                "description": "Library A",
                "downloads": 50000,
            },
            {
                "name": "lib-b",
                "version": "3.0.0",
                "license": "GPL-3.0",
                "description": "Library B",
                "downloads": 30000,
            },
            {
                "name": "lib-c",
                "version": "1.5.0",
                "license": "Apache-2.0",
                "description": "Library C",
                "downloads": 20000,
            },
            {
                "name": "core",
                "version": "4.0.0",
                "license": "MIT",
                "description": "Core lib",
                "downloads": 100000,
            },
        ],
        "dependencies": [
            {
                "source": "app",
                "target": "lib-a",
                "version_constraint": "^2.0.0",
                "dep_type": "runtime",
            },
            {
                "source": "app",
                "target": "lib-b",
                "version_constraint": "^3.0.0",
                "dep_type": "runtime",
            },
            {
                "source": "lib-a",
                "target": "core",
                "version_constraint": "^4.0.0",
                "dep_type": "runtime",
            },
            {
                "source": "lib-b",
                "target": "core",
                "version_constraint": "^4.0.0",
                "dep_type": "runtime",
            },
            {
                "source": "lib-c",
                "target": "lib-a",
                "version_constraint": "^2.0.0",
                "dep_type": "runtime",
            },
        ],
        "vulnerabilities": [
            {
                "vuln_id": "CVE-2024-9999",
                "severity": "critical",
                "description": "RCE in core",
                "affected_package": "core",
            },
        ],
        "maintainers": [
            {"name": "alice", "email": "alice@test.com", "package": "core"},
            {"name": "alice", "email": "alice@test.com", "package": "lib-a"},
            {"name": "bob", "email": "bob@test.com", "package": "lib-b"},
        ],
    }
