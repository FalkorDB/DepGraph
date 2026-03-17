"""Webhook handlers for incremental graph updates from package registries."""

from __future__ import annotations

import hashlib
import hmac
from typing import TYPE_CHECKING, Any

import structlog

from depgraph.graph import queries

if TYPE_CHECKING:
    from falkordb import Graph

logger = structlog.get_logger(__name__)

# --- Signature Verification ---


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify an HMAC-SHA256 webhook signature.

    Args:
        payload: Raw request body bytes.
        signature: The signature header value (hex digest).
        secret: The shared secret key.

    Returns:
        True if signature is valid.
    """
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# --- npm Webhook Handler ---


def handle_npm_webhook(graph: Graph, body: dict[str, Any]) -> dict[str, Any]:
    """Handle an npm registry webhook event.

    npm hooks fire on package publish, unpublish, star, etc.
    See: https://docs.npmjs.com/cli/v9/commands/npm-hook

    Expected payload structure:
    {
        "event": "package:publish" | "package:unpublish" | "package:change",
        "name": "package-name",
        "version": "1.2.3",
        "type": "package",
        ...
    }
    """
    event = body.get("event", "unknown")
    name = body.get("name", "")
    version = body.get("version", "")

    logger.info("npm_webhook", webhook_event=event, package=name, version=version)

    if not name:
        logger.warning("npm_webhook_missing_name")
        return {"status": "skipped", "reason": "missing package name"}

    if event in ("package:publish", "package:change"):
        return _upsert_package_from_webhook(graph, name, version, body, ecosystem="npm")
    elif event == "package:unpublish":
        return _remove_package(graph, name)
    else:
        logger.info("npm_webhook_ignored", webhook_event=event)
        return {"status": "ignored", "event": event}


# --- PyPI Webhook Handler ---


def handle_pypi_webhook(graph: Graph, body: dict[str, Any]) -> dict[str, Any]:
    """Handle a PyPI webhook event.

    PyPI doesn't have native webhooks, but tools like warehouse-webhooks
    or custom CI integrations can send events in this format:

    {
        "action": "new-release" | "remove-release" | "new-file",
        "project": "package-name",
        "version": "1.2.3",
        ...
    }
    """
    action = body.get("action", "unknown")
    name = body.get("project", body.get("name", ""))
    version = body.get("version", "")

    logger.info("pypi_webhook", action=action, package=name, version=version)

    if not name:
        logger.warning("pypi_webhook_missing_name")
        return {"status": "skipped", "reason": "missing package name"}

    if action in ("new-release", "new-file"):
        return _upsert_package_from_webhook(graph, name, version, body, ecosystem="PyPI")
    elif action == "remove-release":
        return _remove_package(graph, name)
    else:
        logger.info("pypi_webhook_ignored", action=action)
        return {"status": "ignored", "action": action}


# --- Generic Webhook Handler ---


def handle_generic_webhook(graph: Graph, body: dict[str, Any]) -> dict[str, Any]:
    """Handle a generic package update webhook.

    Expected payload:
    {
        "action": "publish" | "update" | "unpublish",
        "package": {
            "name": "pkg-name",
            "version": "1.0.0",
            "license": "MIT",
            "description": "...",
            "dependencies": {"dep1": "^1.0", "dep2": ">=2.0"}
        }
    }
    """
    action = body.get("action", "publish")
    pkg_data = body.get("package", {})
    name = pkg_data.get("name", "")

    logger.info("generic_webhook", action=action, package=name)

    if not name:
        return {"status": "skipped", "reason": "missing package name"}

    if action == "unpublish":
        return _remove_package(graph, name)

    # Upsert package
    version = pkg_data.get("version", "0.0.0")
    graph.query(
        queries.CREATE_PACKAGE,
        {
            "name": name,
            "version": version,
            "license": pkg_data.get("license", "Unknown")[:50],
            "description": pkg_data.get("description", "")[:500],
            "downloads": pkg_data.get("downloads", 0),
        },
    )

    # Upsert dependencies if provided
    dep_count = 0
    deps = pkg_data.get("dependencies", {})
    for dep_name, constraint in deps.items():
        # Ensure target package exists (create stub if not)
        graph.query(
            queries.CREATE_PACKAGE,
            {
                "name": dep_name,
                "version": "0.0.0",
                "license": "Unknown",
                "description": "",
                "downloads": 0,
            },
        )
        try:
            graph.query(
                queries.CREATE_DEPENDENCY,
                {
                    "source": name,
                    "target": dep_name,
                    "version_constraint": constraint,
                    "dep_type": "runtime",
                },
            )
            dep_count += 1
        except Exception as exc:
            logger.warning("generic_dep_skip", source=name, target=dep_name, error=str(exc))

    return {"status": "updated", "package": name, "dependencies_updated": dep_count}


# --- Internal Helpers ---

_REMOVE_PACKAGE_QUERY = """
MATCH (p:Package {name: $name})
OPTIONAL MATCH (p)-[r]-()
DELETE r, p
RETURN count(p) AS removed
"""


def _upsert_package_from_webhook(
    graph: Graph,
    name: str,
    version: str,
    body: dict[str, Any],
    ecosystem: str,
) -> dict[str, Any]:
    """Create or update a package node from webhook data, then re-resolve deps."""
    # Upsert the package node
    graph.query(
        queries.CREATE_PACKAGE,
        {
            "name": name,
            "version": version or "0.0.0",
            "license": body.get("license", "Unknown")[:50],
            "description": body.get("description", "")[:500],
            "downloads": body.get("downloads", 0),
        },
    )

    # If the webhook includes dependency info, update edges
    dep_count = 0
    deps = body.get("dependencies", body.get("dist", {}).get("dependencies", {}))
    if isinstance(deps, dict):
        for dep_name, constraint in deps.items():
            graph.query(
                queries.CREATE_PACKAGE,
                {
                    "name": dep_name,
                    "version": "0.0.0",
                    "license": "Unknown",
                    "description": "",
                    "downloads": 0,
                },
            )
            try:
                graph.query(
                    queries.CREATE_DEPENDENCY,
                    {
                        "source": name,
                        "target": dep_name,
                        "version_constraint": str(constraint),
                        "dep_type": "runtime",
                    },
                )
                dep_count += 1
            except Exception as exc:
                logger.warning("webhook_dep_skip", source=name, target=dep_name, error=str(exc))

    logger.info("webhook_upsert_complete", package=name, deps=dep_count, ecosystem=ecosystem)
    return {"status": "updated", "package": name, "dependencies_updated": dep_count}


def _remove_package(graph: Graph, name: str) -> dict[str, Any]:
    """Remove a package and all its relationships from the graph."""
    logger.info("removing_package", package=name)
    result = graph.query(_REMOVE_PACKAGE_QUERY, {"name": name})
    removed = result.result_set[0][0] if result.result_set else 0
    return {"status": "removed", "package": name, "nodes_removed": removed}
