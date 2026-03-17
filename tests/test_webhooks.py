"""Tests for webhook handlers."""

from __future__ import annotations

from conftest import MockGraph
from depgraph.webhooks import (
    handle_generic_webhook,
    handle_npm_webhook,
    handle_pypi_webhook,
    verify_hmac_signature,
)


class TestVerifyHmacSignature:
    def test_valid_signature(self) -> None:
        import hashlib
        import hmac as hmac_mod

        secret = "my-secret"
        payload = b'{"test": true}'
        sig = hmac_mod.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_hmac_signature(payload, sig, secret) is True

    def test_invalid_signature(self) -> None:
        assert verify_hmac_signature(b"payload", "bad-sig", "secret") is False


class TestNpmWebhook:
    def test_package_publish(self) -> None:
        graph = MockGraph()
        result = handle_npm_webhook(
            graph,
            {
                "event": "package:publish",
                "name": "my-pkg",
                "version": "1.0.0",
                "license": "MIT",
                "description": "test",
            },
        )
        assert result["status"] == "updated"
        assert result["package"] == "my-pkg"

    def test_package_unpublish(self) -> None:
        graph = MockGraph()
        graph.set_response("MATCH (p:Package", [[1]])
        result = handle_npm_webhook(
            graph,
            {
                "event": "package:unpublish",
                "name": "removed-pkg",
            },
        )
        assert result["status"] == "removed"

    def test_missing_name_skips(self) -> None:
        graph = MockGraph()
        result = handle_npm_webhook(graph, {"event": "package:publish"})
        assert result["status"] == "skipped"

    def test_unknown_event_ignored(self) -> None:
        graph = MockGraph()
        result = handle_npm_webhook(graph, {"event": "package:star", "name": "pkg"})
        assert result["status"] == "ignored"

    def test_publish_with_dependencies(self) -> None:
        graph = MockGraph()
        result = handle_npm_webhook(
            graph,
            {
                "event": "package:publish",
                "name": "my-pkg",
                "version": "2.0.0",
                "dependencies": {"dep-a": "^1.0", "dep-b": "^2.0"},
            },
        )
        assert result["status"] == "updated"
        assert result["dependencies_updated"] == 2


class TestPyPIWebhook:
    def test_new_release(self) -> None:
        graph = MockGraph()
        result = handle_pypi_webhook(
            graph,
            {
                "action": "new-release",
                "project": "flask",
                "version": "3.0.0",
            },
        )
        assert result["status"] == "updated"

    def test_remove_release(self) -> None:
        graph = MockGraph()
        graph.set_response("MATCH (p:Package", [[1]])
        result = handle_pypi_webhook(
            graph,
            {
                "action": "remove-release",
                "project": "old-pkg",
            },
        )
        assert result["status"] == "removed"

    def test_missing_name_skips(self) -> None:
        graph = MockGraph()
        result = handle_pypi_webhook(graph, {"action": "new-release"})
        assert result["status"] == "skipped"

    def test_unknown_action_ignored(self) -> None:
        graph = MockGraph()
        result = handle_pypi_webhook(graph, {"action": "something-else", "project": "pkg"})
        assert result["status"] == "ignored"


class TestGenericWebhook:
    def test_publish_with_deps(self) -> None:
        graph = MockGraph()
        result = handle_generic_webhook(
            graph,
            {
                "action": "publish",
                "package": {
                    "name": "my-lib",
                    "version": "1.0.0",
                    "license": "MIT",
                    "description": "test lib",
                    "dependencies": {"dep-x": "^1.0"},
                },
            },
        )
        assert result["status"] == "updated"
        assert result["package"] == "my-lib"
        assert result["dependencies_updated"] == 1

    def test_unpublish(self) -> None:
        graph = MockGraph()
        graph.set_response("MATCH (p:Package", [[1]])
        result = handle_generic_webhook(
            graph,
            {
                "action": "unpublish",
                "package": {"name": "old-lib"},
            },
        )
        assert result["status"] == "removed"

    def test_missing_name_skips(self) -> None:
        graph = MockGraph()
        result = handle_generic_webhook(graph, {"action": "publish", "package": {}})
        assert result["status"] == "skipped"

    def test_no_dependencies(self) -> None:
        graph = MockGraph()
        result = handle_generic_webhook(
            graph,
            {
                "action": "publish",
                "package": {
                    "name": "standalone",
                    "version": "1.0.0",
                },
            },
        )
        assert result["status"] == "updated"
        assert result["dependencies_updated"] == 0
