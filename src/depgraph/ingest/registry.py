"""Real package registry ingestion — fetch packages from npm and PyPI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog

from depgraph.graph import queries

if TYPE_CHECKING:
    from falkordb import Graph

logger = structlog.get_logger(__name__)

# --- npm Registry ---

NPM_REGISTRY_URL = "https://registry.npmjs.org"
NPM_REQUEST_TIMEOUT = 15.0


def fetch_npm_package(name: str) -> dict[str, Any]:
    """Fetch package metadata from the npm registry.

    Returns a normalized dict with keys: name, version, license, description,
    downloads, dependencies (dict[str, str]).
    """
    url = f"{NPM_REGISTRY_URL}/{name}"
    logger.info("npm_fetch", package=name, url=url)

    with httpx.Client(timeout=NPM_REQUEST_TIMEOUT) as client:
        resp = client.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

    latest_tag = data.get("dist-tags", {}).get("latest", "0.0.0")
    latest = data.get("versions", {}).get(latest_tag, {})

    return {
        "name": data.get("name", name),
        "version": latest_tag,
        "license": _extract_license(latest.get("license")),
        "description": (data.get("description") or "")[:500],
        "downloads": 0,
        "dependencies": latest.get("dependencies") or {},
        "dev_dependencies": latest.get("devDependencies") or {},
    }


def ingest_npm_package(
    graph: Graph,
    name: str,
    *,
    max_depth: int = 3,
    include_dev: bool = False,
) -> dict[str, int]:
    """Fetch an npm package and its transitive dependencies, ingest into graph.

    Args:
        graph: FalkorDB graph instance.
        name: Root package name (e.g. "express").
        max_depth: Maximum dependency resolution depth.
        include_dev: Whether to include devDependencies.

    Returns:
        Counts of ingested entities.
    """
    counts = {"packages": 0, "dependencies": 0, "errors": 0}
    visited: set[str] = set()
    _resolve_npm_recursive(graph, name, visited, counts, max_depth, include_dev, depth=0)
    logger.info("npm_ingest_complete", root=name, **counts)
    return counts


def _resolve_npm_recursive(
    graph: Graph,
    name: str,
    visited: set[str],
    counts: dict[str, int],
    max_depth: int,
    include_dev: bool,
    depth: int,
) -> None:
    """Recursively fetch and ingest npm packages."""
    if name in visited or depth > max_depth:
        return
    visited.add(name)

    try:
        pkg = fetch_npm_package(name)
    except httpx.HTTPStatusError as exc:
        logger.warning("npm_fetch_failed", package=name, status=exc.response.status_code)
        counts["errors"] += 1
        return
    except httpx.RequestError as exc:
        logger.warning("npm_fetch_error", package=name, error=str(exc))
        counts["errors"] += 1
        return

    # Create package node
    graph.query(
        queries.CREATE_PACKAGE,
        {
            "name": pkg["name"],
            "version": pkg["version"],
            "license": pkg["license"],
            "description": pkg["description"],
            "downloads": pkg["downloads"],
        },
    )
    counts["packages"] += 1

    # Process runtime dependencies
    all_deps: dict[str, tuple[str, str]] = {}
    for dep_name, constraint in pkg["dependencies"].items():
        all_deps[dep_name] = (constraint, "runtime")

    if include_dev:
        for dep_name, constraint in pkg["dev_dependencies"].items():
            if dep_name not in all_deps:
                all_deps[dep_name] = (constraint, "dev")

    for dep_name, (constraint, dep_type) in all_deps.items():
        # Recurse first to ensure target node exists
        _resolve_npm_recursive(
            graph, dep_name, visited, counts, max_depth, include_dev=False, depth=depth + 1
        )

        # Create dependency edge (only if target was successfully fetched)
        if dep_name in visited:
            try:
                graph.query(
                    queries.CREATE_DEPENDENCY,
                    {
                        "source": pkg["name"],
                        "target": dep_name,
                        "version_constraint": constraint,
                        "dep_type": dep_type,
                    },
                )
                counts["dependencies"] += 1
            except Exception as exc:
                logger.warning(
                    "npm_dep_create_failed",
                    source=pkg["name"],
                    target=dep_name,
                    error=str(exc),
                )


# --- PyPI Registry ---

PYPI_REGISTRY_URL = "https://pypi.org/pypi"
PYPI_REQUEST_TIMEOUT = 15.0


def fetch_pypi_package(name: str) -> dict[str, Any]:
    """Fetch package metadata from PyPI.

    Returns a normalized dict with keys: name, version, license, description,
    downloads, dependencies (list[str] of requirement specifiers).
    """
    url = f"{PYPI_REGISTRY_URL}/{name}/json"
    logger.info("pypi_fetch", package=name, url=url)

    with httpx.Client(timeout=PYPI_REQUEST_TIMEOUT) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    info = data.get("info", {})
    requires_dist = info.get("requires_dist") or []

    # Parse requirements into (name, constraint, is_extra) tuples
    deps: list[tuple[str, str, bool]] = []
    for req_str in requires_dist:
        dep_name, constraint, is_extra = _parse_pypi_requirement(req_str)
        if dep_name:
            deps.append((dep_name, constraint, is_extra))

    return {
        "name": info.get("name", name),
        "version": info.get("version", "0.0.0"),
        "license": (info.get("license") or "Unknown")[:50],
        "description": (info.get("summary") or "")[:500],
        "downloads": 0,
        "dependencies": deps,
    }


def ingest_pypi_package(
    graph: Graph,
    name: str,
    *,
    max_depth: int = 3,
    include_extras: bool = False,
) -> dict[str, int]:
    """Fetch a PyPI package and its transitive dependencies, ingest into graph.

    Args:
        graph: FalkorDB graph instance.
        name: Root package name (e.g. "requests").
        max_depth: Maximum dependency resolution depth.
        include_extras: Whether to include extra/optional dependencies.

    Returns:
        Counts of ingested entities.
    """
    counts = {"packages": 0, "dependencies": 0, "errors": 0}
    visited: set[str] = set()
    _resolve_pypi_recursive(graph, name, visited, counts, max_depth, include_extras, depth=0)
    logger.info("pypi_ingest_complete", root=name, **counts)
    return counts


def _resolve_pypi_recursive(
    graph: Graph,
    name: str,
    visited: set[str],
    counts: dict[str, int],
    max_depth: int,
    include_extras: bool,
    depth: int,
) -> None:
    """Recursively fetch and ingest PyPI packages."""
    normalized = _normalize_pypi_name(name)
    if normalized in visited or depth > max_depth:
        return
    visited.add(normalized)

    try:
        pkg = fetch_pypi_package(name)
    except httpx.HTTPStatusError as exc:
        logger.warning("pypi_fetch_failed", package=name, status=exc.response.status_code)
        counts["errors"] += 1
        return
    except httpx.RequestError as exc:
        logger.warning("pypi_fetch_error", package=name, error=str(exc))
        counts["errors"] += 1
        return

    # Create package node
    graph.query(
        queries.CREATE_PACKAGE,
        {
            "name": pkg["name"],
            "version": pkg["version"],
            "license": pkg["license"],
            "description": pkg["description"],
            "downloads": pkg["downloads"],
        },
    )
    counts["packages"] += 1

    for dep_name, constraint, is_extra in pkg["dependencies"]:
        if is_extra and not include_extras:
            continue

        _resolve_pypi_recursive(
            graph,
            dep_name,
            visited,
            counts,
            max_depth,
            include_extras=False,
            depth=depth + 1,
        )

        dep_normalized = _normalize_pypi_name(dep_name)
        if dep_normalized in visited:
            try:
                graph.query(
                    queries.CREATE_DEPENDENCY,
                    {
                        "source": pkg["name"],
                        "target": dep_name,
                        "version_constraint": constraint or "*",
                        "dep_type": "optional" if is_extra else "runtime",
                    },
                )
                counts["dependencies"] += 1
            except Exception as exc:
                logger.warning(
                    "pypi_dep_create_failed",
                    source=pkg["name"],
                    target=dep_name,
                    error=str(exc),
                )


# --- Helpers ---


def _extract_license(license_val: Any) -> str:
    """Normalize npm license field (can be string, dict, or None)."""
    if isinstance(license_val, str):
        return license_val[:50]
    if isinstance(license_val, dict):
        return (license_val.get("type") or "Unknown")[:50]
    return "Unknown"


def _parse_pypi_requirement(req_str: str) -> tuple[str, str, bool]:
    """Parse a PEP 508 requirement string into (name, constraint, is_extra).

    Examples:
        "requests>=2.20" -> ("requests", ">=2.20", False)
        "boto3; extra == \"aws\"" -> ("boto3", "", True)
        "typing-extensions (>=3.7) ; python_version < \"3.8\"" -> ("typing-extensions", ">=3.7", False)
    """
    is_extra = "extra ==" in req_str or "extra==" in req_str

    # Split on semicolon to remove environment markers
    base = req_str.split(";")[0].strip()

    # Extract name and version constraint
    # Handle both "name (>=version)" and "name>=version" formats
    if "(" in base:
        parts = base.split("(", 1)
        name = parts[0].strip()
        constraint = parts[1].rstrip(")").strip()
    else:
        # Split on first comparison operator
        for op in [">=", "<=", "!=", "~=", "==", ">", "<"]:
            if op in base:
                idx = base.index(op)
                name = base[:idx].strip()
                constraint = base[idx:].strip()
                break
        else:
            name = base.strip()
            constraint = ""

    # Clean up extras from name like "package[extra1,extra2]"
    if "[" in name:
        name = name.split("[")[0]

    return name, constraint, is_extra


def _normalize_pypi_name(name: str) -> str:
    """Normalize a PyPI package name for deduplication."""
    return name.lower().replace("-", "_").replace(".", "_")
