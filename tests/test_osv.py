"""Tests for OSV.dev vulnerability scanning."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from conftest import MockGraph
from depgraph.ingest.osv import (
    _cvss_vector_to_severity,
    _extract_severity,
    query_osv,
    scan_and_ingest_package,
    scan_graph_packages,
)


class TestExtractSeverity:
    def test_cvss_severity_array(self) -> None:
        vuln = {
            "severity": [
                {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
            ]
        }
        assert _extract_severity(vuln) == "critical"

    def test_database_specific_severity(self) -> None:
        vuln = {"database_specific": {"severity": "HIGH"}}
        assert _extract_severity(vuln) == "high"

    def test_database_specific_moderate(self) -> None:
        vuln = {"database_specific": {"severity": "MODERATE"}}
        assert _extract_severity(vuln) == "medium"

    def test_ecosystem_specific(self) -> None:
        vuln = {"affected": [{"ecosystem_specific": {"severity": "LOW"}}]}
        assert _extract_severity(vuln) == "low"

    def test_no_severity_defaults_medium(self) -> None:
        assert _extract_severity({}) == "medium"


class TestCvssVectorToSeverity:
    def test_critical(self) -> None:
        assert (
            _cvss_vector_to_severity("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "critical"
        )

    def test_high(self) -> None:
        assert _cvss_vector_to_severity("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:N") == "high"

    def test_medium(self) -> None:
        assert _cvss_vector_to_severity("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N") == "medium"

    def test_low(self) -> None:
        assert _cvss_vector_to_severity("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:N/I:N/A:N") == "low"


class TestQueryOsv:
    @patch("depgraph.ingest.osv.httpx.Client")
    def test_successful_query(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "vulns": [
                {
                    "id": "GHSA-1234",
                    "summary": "XSS vuln",
                    "database_specific": {"severity": "HIGH"},
                },
            ]
        }
        mock_client_cls.return_value.__enter__ = lambda s: s
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value.post.return_value = mock_resp

        result = query_osv("express", "4.17.1", "npm")
        assert len(result) == 1
        assert result[0]["id"] == "GHSA-1234"

    @patch("depgraph.ingest.osv.httpx.Client")
    def test_no_vulns(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_client_cls.return_value.__enter__ = lambda s: s
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value.post.return_value = mock_resp

        result = query_osv("safe-pkg", "1.0.0", "npm")
        assert result == []


class TestScanAndIngestPackage:
    @patch("depgraph.ingest.osv.query_osv")
    def test_ingest_vulns(self, mock_query: MagicMock) -> None:
        mock_query.return_value = [
            {
                "id": "CVE-2023-001",
                "summary": "RCE vulnerability",
                "database_specific": {"severity": "CRITICAL"},
            },
            {
                "id": "CVE-2023-002",
                "summary": "XSS issue",
                "database_specific": {"severity": "MEDIUM"},
            },
        ]
        graph = MockGraph()
        result = scan_and_ingest_package(graph, "express", "4.17.1", "npm")
        assert result["packages_scanned"] == 1
        assert result["vulnerabilities_found"] == 2
        assert len(result["vulnerabilities"]) == 2

    @patch("depgraph.ingest.osv.query_osv")
    def test_no_vulns_found(self, mock_query: MagicMock) -> None:
        mock_query.return_value = []
        graph = MockGraph()
        result = scan_and_ingest_package(graph, "safe-pkg", "1.0.0", "npm")
        assert result["vulnerabilities_found"] == 0


class TestScanGraphPackages:
    @patch("depgraph.ingest.osv.query_osv")
    def test_scans_all_packages(self, mock_query: MagicMock) -> None:
        mock_query.side_effect = [
            [{"id": "CVE-001", "summary": "vuln1", "database_specific": {"severity": "HIGH"}}],
            [],  # safe package
        ]
        graph = MockGraph()
        graph.set_response("MATCH (p:Package)", [["pkg-a", "1.0.0"], ["pkg-b", "2.0.0"]])

        result = scan_graph_packages(graph, ecosystem="npm")
        assert result["packages_scanned"] == 2
        assert result["vulnerabilities_found"] == 1
