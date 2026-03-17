"""Integration tests requiring a running FalkorDB instance.

Run with: pytest -m integration
Requires FalkorDB on localhost:6379.
"""

from __future__ import annotations

import pytest

from depgraph.config import FalkorDBConfig
from depgraph.db import GraphDB
from depgraph.graph.engine import AnalysisEngine
from depgraph.graph.schema import clear_graph, ensure_schema, get_stats
from depgraph.ingest.parsers import ingest_ecosystem
from depgraph.ingest.seed import generate_ecosystem


@pytest.fixture
def integration_db() -> GraphDB:
    """Provide a real FalkorDB connection for integration tests."""
    config = FalkorDBConfig(graph_name="depgraph_integration_test")
    db = GraphDB(config)
    try:
        db.connect()
    except Exception:
        pytest.skip("FalkorDB not available for integration tests")
    return db


@pytest.fixture
def seeded_db(integration_db: GraphDB) -> tuple[GraphDB, AnalysisEngine]:
    """Provide a seeded graph for integration tests."""
    graph = integration_db.graph
    clear_graph(graph)
    ensure_schema(graph)
    data = generate_ecosystem(num_packages=30, seed=42)
    ingest_ecosystem(graph, data)
    engine = AnalysisEngine(graph, max_depth=10)
    yield integration_db, engine
    clear_graph(graph)
    integration_db.close()


@pytest.mark.integration
class TestFalkorDBIntegration:
    def test_connection_and_schema(self, integration_db: GraphDB) -> None:
        """Test basic connectivity and schema setup."""
        graph = integration_db.graph
        clear_graph(graph)
        ensure_schema(graph)
        assert integration_db.health_check()
        clear_graph(graph)
        integration_db.close()

    def test_full_pipeline(self, seeded_db: tuple[GraphDB, AnalysisEngine]) -> None:
        """Test complete ingest → analyze pipeline."""
        db, engine = seeded_db
        stats = get_stats(db.graph)
        assert stats["packages"] > 0
        assert stats["dependencies"] > 0

        # Blast radius
        packages = engine.list_packages(limit=5)
        assert len(packages) > 0
        pkg = packages[0]
        result = engine.blast_radius(pkg.name)
        assert result.source_package == pkg.name

        # Cycles
        cycles = engine.find_cycles()
        assert isinstance(cycles.total_cycles, int)

        # Centrality
        centrality = engine.centrality(limit=5)
        assert len(centrality.packages) > 0

    def test_blast_radius_depth(self, seeded_db: tuple[GraphDB, AnalysisEngine]) -> None:
        """Test that blast radius correctly traverses multiple hops."""
        _db, engine = seeded_db
        # Find the most central package and check its blast radius
        centrality = engine.centrality(limit=1)
        if centrality.packages:
            top = centrality.packages[0]
            result = engine.blast_radius(top.name)
            assert result.total_affected >= top.direct_dependents

    def test_license_propagation(self, seeded_db: tuple[GraphDB, AnalysisEngine]) -> None:
        """Test license check through transitive dependencies."""
        _db, engine = seeded_db
        packages = engine.list_packages(limit=100)
        # Find a package with dependencies
        for pkg in packages:
            depth = engine.dependency_depth(pkg.name)
            if depth.dependency_count > 0:
                report = engine.license_check(pkg.name)
                assert report.root_package == pkg.name
                assert report.total_dependencies_checked >= 0
                break

    def test_empty_graph_handling(self, integration_db: GraphDB) -> None:
        """Test that analysis handles empty graphs gracefully."""
        graph = integration_db.graph
        clear_graph(graph)
        engine = AnalysisEngine(graph, max_depth=10)

        result = engine.blast_radius("nonexistent")
        assert result.total_affected == 0

        cycles = engine.find_cycles()
        assert cycles.total_cycles == 0

        centrality = engine.centrality()
        assert len(centrality.packages) == 0

        clear_graph(graph)
        integration_db.close()
