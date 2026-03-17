"""Tests for SBOM export and import (CycloneDX + SPDX)."""

from __future__ import annotations

import pytest

from conftest import MockGraph
from depgraph.sbom import export_cyclonedx, export_spdx, import_sbom


@pytest.fixture
def graph_with_packages() -> MockGraph:
    """Mock graph with package and dependency data for SBOM tests."""
    g = MockGraph()
    g.set_response(
        "MATCH (p:Package)\nRETURN",
        [
            ["express", "4.18.2", "MIT", "Web framework"],
            ["body-parser", "1.20.1", "MIT", "Body parsing"],
            ["accepts", "1.3.8", "MIT", "Content negotiation"],
        ],
    )
    g.set_response(
        "MATCH (src:Package)-[r:DEPENDS_ON]->(tgt:Package)",
        [
            ["express", "body-parser", "1.20.1", "runtime"],
            ["express", "accepts", "~1.3.8", "runtime"],
        ],
    )
    return g


class TestExportCycloneDX:
    def test_basic_structure(self, graph_with_packages: MockGraph) -> None:
        result = export_cyclonedx(graph_with_packages)
        assert result["bomFormat"] == "CycloneDX"
        assert result["specVersion"] == "1.5"
        assert "serialNumber" in result
        assert "metadata" in result
        assert len(result["components"]) == 3
        assert len(result["dependencies"]) == 3

    def test_components_have_required_fields(self, graph_with_packages: MockGraph) -> None:
        result = export_cyclonedx(graph_with_packages)
        for comp in result["components"]:
            assert "name" in comp
            assert "version" in comp
            assert "type" in comp
            assert comp["type"] == "library"
            assert "bom-ref" in comp

    def test_dependencies_reference_valid_bomrefs(self, graph_with_packages: MockGraph) -> None:
        result = export_cyclonedx(graph_with_packages)
        bom_refs = {c["bom-ref"] for c in result["components"]}
        for dep in result["dependencies"]:
            assert dep["ref"] in bom_refs
            for target in dep.get("dependsOn", []):
                assert target in bom_refs

    def test_express_depends_on_body_parser(self, graph_with_packages: MockGraph) -> None:
        result = export_cyclonedx(graph_with_packages)
        express_dep = next(d for d in result["dependencies"] if "express" in d["ref"])
        dep_names = [ref.split("@")[0].split(":")[-1] for ref in express_dep.get("dependsOn", [])]
        assert "body-parser" in dep_names
        assert "accepts" in dep_names


class TestExportSPDX:
    def test_basic_structure(self, graph_with_packages: MockGraph) -> None:
        result = export_spdx(graph_with_packages)
        assert result["spdxVersion"] == "SPDX-2.3"
        assert result["dataLicense"] == "CC0-1.0"
        assert "creationInfo" in result
        assert len(result["packages"]) == 3

    def test_packages_have_required_fields(self, graph_with_packages: MockGraph) -> None:
        result = export_spdx(graph_with_packages)
        for pkg in result["packages"]:
            assert "SPDXID" in pkg
            assert "name" in pkg
            assert "versionInfo" in pkg
            assert "licenseConcluded" in pkg

    def test_relationships_include_depends_on(self, graph_with_packages: MockGraph) -> None:
        result = export_spdx(graph_with_packages)
        dep_rels = [r for r in result["relationships"] if r["relationshipType"] == "DEPENDS_ON"]
        assert len(dep_rels) == 2  # express -> body-parser, express -> accepts


class TestImportCycloneDX:
    def test_import_roundtrip(self, graph_with_packages: MockGraph) -> None:
        """Export then import should be lossless."""
        exported = export_cyclonedx(graph_with_packages)
        import_graph = MockGraph()
        counts = import_sbom(import_graph, exported)
        assert counts["packages"] == 3
        assert counts["dependencies"] == 2

    def test_import_with_missing_fields(self) -> None:
        """Import handles components without optional fields."""
        data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "components": [
                {"name": "minimal-pkg", "type": "library"},
            ],
            "dependencies": [],
        }
        graph = MockGraph()
        counts = import_sbom(graph, data)
        assert counts["packages"] == 1
        assert counts["dependencies"] == 0


class TestImportSPDX:
    def test_import_roundtrip(self, graph_with_packages: MockGraph) -> None:
        exported = export_spdx(graph_with_packages)
        import_graph = MockGraph()
        counts = import_sbom(import_graph, exported)
        assert counts["packages"] == 3
        assert counts["dependencies"] == 2


class TestImportAutoDetect:
    def test_unrecognized_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized SBOM format"):
            import_sbom(MockGraph(), {"some": "random"})
