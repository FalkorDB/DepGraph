"""Tests for npm/PyPI registry ingestion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from depgraph.ingest.registry import (
    _extract_license,
    _normalize_pypi_name,
    _parse_pypi_requirement,
    fetch_npm_package,
    fetch_pypi_package,
    ingest_npm_package,
    ingest_pypi_package,
)

# --- Helper tests ---


class TestExtractLicense:
    def test_string_license(self) -> None:
        assert _extract_license("MIT") == "MIT"

    def test_dict_license(self) -> None:
        assert _extract_license({"type": "ISC", "url": "..."}) == "ISC"

    def test_none_license(self) -> None:
        assert _extract_license(None) == "Unknown"

    def test_truncation(self) -> None:
        assert len(_extract_license("A" * 100)) == 50


class TestParsePyPIRequirement:
    def test_simple_version(self) -> None:
        name, constraint, is_extra = _parse_pypi_requirement("requests>=2.20")
        assert name == "requests"
        assert constraint == ">=2.20"
        assert is_extra is False

    def test_parenthesized_version(self) -> None:
        name, constraint, _is_extra = _parse_pypi_requirement("typing-extensions (>=3.7)")
        assert name == "typing-extensions"
        assert constraint == ">=3.7"

    def test_with_extras(self) -> None:
        name, _constraint, is_extra = _parse_pypi_requirement('boto3 ; extra == "aws"')
        assert name == "boto3"
        assert is_extra is True

    def test_bracket_extras(self) -> None:
        name, _, _ = _parse_pypi_requirement("package[extra1,extra2]>=1.0")
        assert name == "package"

    def test_no_version(self) -> None:
        name, constraint, is_extra = _parse_pypi_requirement("simple-pkg")
        assert name == "simple-pkg"
        assert constraint == ""
        assert is_extra is False


class TestNormalizePyPIName:
    def test_lowercase(self) -> None:
        assert _normalize_pypi_name("Flask") == "flask"

    def test_dashes_to_underscores(self) -> None:
        assert _normalize_pypi_name("my-package") == "my_package"

    def test_dots_to_underscores(self) -> None:
        assert _normalize_pypi_name("zope.interface") == "zope_interface"


# --- Fetch tests (mocked HTTP) ---


class TestFetchNpmPackage:
    @patch("depgraph.ingest.registry.httpx.Client")
    def test_successful_fetch(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "name": "express",
            "description": "Fast web framework",
            "dist-tags": {"latest": "4.18.2"},
            "versions": {
                "4.18.2": {
                    "license": "MIT",
                    "dependencies": {"accepts": "~1.3.8", "body-parser": "1.20.1"},
                    "devDependencies": {"mocha": "^10.0.0"},
                }
            },
        }
        mock_client_cls.return_value.__enter__ = lambda s: s
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value.get.return_value = mock_resp

        result = fetch_npm_package("express")
        assert result["name"] == "express"
        assert result["version"] == "4.18.2"
        assert result["license"] == "MIT"
        assert "accepts" in result["dependencies"]
        assert "mocha" in result["dev_dependencies"]

    @patch("depgraph.ingest.registry.httpx.Client")
    def test_404_raises(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=MagicMock(status_code=404)
        )
        mock_client_cls.return_value.__enter__ = lambda s: s
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value.get.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            fetch_npm_package("nonexistent-pkg-xyz")


class TestFetchPyPIPackage:
    @patch("depgraph.ingest.registry.httpx.Client")
    def test_successful_fetch(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "info": {
                "name": "requests",
                "version": "2.31.0",
                "license": "Apache-2.0",
                "summary": "HTTP library",
                "requires_dist": [
                    "charset-normalizer>=2,<4",
                    "idna>=2.5,<4",
                    'PySocks!=1.5.7 ; extra == "socks"',
                ],
            }
        }
        mock_client_cls.return_value.__enter__ = lambda s: s
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value.get.return_value = mock_resp

        result = fetch_pypi_package("requests")
        assert result["name"] == "requests"
        assert result["version"] == "2.31.0"
        # 3 deps total, 1 is extra
        assert len(result["dependencies"]) == 3
        extras = [d for d in result["dependencies"] if d[2]]
        assert len(extras) == 1


# --- Ingestion tests (mocked graph + HTTP) ---


class TestIngestNpmPackage:
    @patch("depgraph.ingest.registry.fetch_npm_package")
    def test_ingests_package_and_deps(self, mock_fetch: MagicMock) -> None:
        from conftest import MockGraph

        mock_fetch.side_effect = [
            {
                "name": "my-pkg",
                "version": "1.0.0",
                "license": "MIT",
                "description": "test",
                "downloads": 0,
                "dependencies": {"dep-a": "^1.0"},
                "dev_dependencies": {},
            },
            {
                "name": "dep-a",
                "version": "1.2.0",
                "license": "ISC",
                "description": "dep",
                "downloads": 0,
                "dependencies": {},
                "dev_dependencies": {},
            },
        ]

        graph = MockGraph()
        counts = ingest_npm_package(graph, "my-pkg", max_depth=2)
        assert counts["packages"] == 2
        assert counts["dependencies"] == 1
        assert counts["errors"] == 0

    @patch("depgraph.ingest.registry.fetch_npm_package")
    def test_handles_fetch_error(self, mock_fetch: MagicMock) -> None:
        from conftest import MockGraph

        mock_fetch.side_effect = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=MagicMock(status_code=404)
        )

        graph = MockGraph()
        counts = ingest_npm_package(graph, "bad-pkg", max_depth=1)
        assert counts["packages"] == 0
        assert counts["errors"] == 1

    @patch("depgraph.ingest.registry.fetch_npm_package")
    def test_max_depth_limits(self, mock_fetch: MagicMock) -> None:
        from conftest import MockGraph

        def make_pkg(name: str, deps: dict[str, str]) -> dict:
            return {
                "name": name,
                "version": "1.0.0",
                "license": "MIT",
                "description": "",
                "downloads": 0,
                "dependencies": deps,
                "dev_dependencies": {},
            }

        mock_fetch.side_effect = [
            make_pkg("a", {"b": "^1"}),
            make_pkg("b", {"c": "^1"}),
            # c should NOT be fetched at max_depth=1
        ]

        graph = MockGraph()
        counts = ingest_npm_package(graph, "a", max_depth=1)
        assert counts["packages"] == 2  # a and b, not c


class TestIngestPyPIPackage:
    @patch("depgraph.ingest.registry.fetch_pypi_package")
    def test_ingests_with_extras(self, mock_fetch: MagicMock) -> None:
        from conftest import MockGraph

        mock_fetch.side_effect = [
            {
                "name": "flask",
                "version": "3.0.0",
                "license": "BSD-3-Clause",
                "description": "Web framework",
                "downloads": 0,
                "dependencies": [
                    ("werkzeug", ">=3.0", False),
                    ("pytest", "", True),
                ],
            },
            {
                "name": "werkzeug",
                "version": "3.0.1",
                "license": "BSD-3-Clause",
                "description": "WSGI",
                "downloads": 0,
                "dependencies": [],
            },
        ]

        graph = MockGraph()
        counts = ingest_pypi_package(graph, "flask", max_depth=2, include_extras=False)
        assert counts["packages"] == 2  # flask + werkzeug (not pytest)
        assert counts["dependencies"] == 1
