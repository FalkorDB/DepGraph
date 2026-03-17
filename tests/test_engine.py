"""Tests for graph analysis engine with mock graph."""

from __future__ import annotations

from conftest import MockGraph
from depgraph.graph.engine import AnalysisEngine


class TestBlastRadius:
    def test_blast_radius_with_dependents(
        self, mock_graph: MockGraph, engine: AnalysisEngine
    ) -> None:
        mock_graph.set_response(
            "MATCH path",
            [
                ["app", 2, ["app", "lib-a", "core"]],
                ["lib-a", 1, ["lib-a", "core"]],
                ["lib-b", 1, ["lib-b", "core"]],
            ],
        )
        result = engine.blast_radius("core")
        assert result.source_package == "core"
        assert result.total_affected == 3
        assert result.max_depth == 2
        names = {ap.name for ap in result.affected_packages}
        assert names == {"app", "lib-a", "lib-b"}

    def test_blast_radius_no_dependents(
        self, mock_graph: MockGraph, engine: AnalysisEngine
    ) -> None:
        result = engine.blast_radius("leaf-package")
        assert result.total_affected == 0
        assert result.max_depth == 0

    def test_blast_radius_deduplicates(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "MATCH path",
            [
                ["app", 1, ["app", "core"]],
                ["app", 2, ["app", "lib-a", "core"]],
            ],
        )
        result = engine.blast_radius("core")
        assert result.total_affected == 1  # app counted once


class TestCycleDetection:
    def test_find_cycles(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "MATCH path",
            [
                [["a", "b", "c", "a"]],
            ],
        )
        result = engine.find_cycles()
        assert result.total_cycles == 1
        assert result.cycles[0] == ["a", "b", "c"]

    def test_no_cycles(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        result = engine.find_cycles()
        assert result.total_cycles == 0

    def test_cycle_normalization(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "MATCH path",
            [
                [["b", "c", "a", "b"]],
                [["c", "a", "b", "c"]],
            ],
        )
        result = engine.find_cycles()
        assert result.total_cycles == 1  # Same cycle, normalized


class TestCentrality:
    def test_centrality_ordering(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        # Direct dependents query (DEPENDS_ON]->) returns top packages
        mock_graph.set_response(
            "ORDER BY direct_dependents",
            [
                ["core", 5],
                ["utils", 3],
            ],
        )
        # Transitive dependents query (DEPENDS_ON*) returns count
        mock_graph.set_response("transitive_dependents", [[8]])
        result = engine.centrality(limit=5)
        assert len(result.packages) == 2
        assert result.packages[0].name == "core"
        assert result.packages[0].direct_dependents == 5


class TestLicenseCheck:
    def test_license_detects_copyleft(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "MATCH path",
            [
                ["lib-a", "MIT", 1, ["app", "lib-a"]],
                ["lib-b", "GPL-3.0", 1, ["app", "lib-b"]],
                ["core", "MIT", 2, ["app", "lib-a", "core"]],
            ],
        )
        result = engine.license_check("app")
        assert result.root_package == "app"
        assert len(result.issues) == 1
        assert result.issues[0].license == "GPL-3.0"
        assert result.issues[0].risk.value == "strong_copyleft"

    def test_license_all_permissive(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "MATCH path",
            [
                ["lib-a", "MIT", 1, ["app", "lib-a"]],
                ["core", "Apache-2.0", 2, ["app", "lib-a", "core"]],
            ],
        )
        result = engine.license_check("app")
        assert len(result.issues) == 0


class TestDepthAnalysis:
    def test_depth_calculation(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "MATCH path",
            [
                ["lib-a", 1, ["app", "lib-a"]],
                ["core", 2, ["app", "lib-a", "core"]],
                ["lib-b", 1, ["app", "lib-b"]],
            ],
        )
        result = engine.dependency_depth("app")
        assert result.package == "app"
        assert result.max_depth == 2
        assert result.dependency_count == 3

    def test_depth_no_deps(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        result = engine.dependency_depth("leaf")
        assert result.max_depth == 0
        assert result.dependency_count == 0


class TestGetPackage:
    def test_get_existing_package(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "MATCH (p:Package",
            [
                ["express", "4.18.2", "MIT", "Fast web framework", 50000000],
            ],
        )
        pkg = engine.get_package("express")
        assert pkg is not None
        assert pkg.name == "express"
        assert pkg.version == "4.18.2"

    def test_get_missing_package(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        pkg = engine.get_package("nonexistent")
        assert pkg is None


class TestSearchPackages:
    def test_search(self, mock_graph: MockGraph, engine: AnalysisEngine) -> None:
        mock_graph.set_response(
            "CONTAINS",
            [
                ["express", "4.18.2", "MIT", "Web framework", 50000000],
                ["express-session", "1.17.3", "MIT", "Session middleware", 1000000],
            ],
        )
        results = engine.search_packages("express")
        assert len(results) == 2
