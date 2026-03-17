"""Data ingestion pipeline — loads ecosystem data into FalkorDB."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from depgraph.graph import queries

if TYPE_CHECKING:
    from falkordb import Graph

logger = structlog.get_logger(__name__)


def ingest_ecosystem(graph: Graph, data: dict[str, Any]) -> dict[str, int]:
    """Load a full ecosystem dataset into the graph. Returns counts of entities created."""
    counts = {"packages": 0, "dependencies": 0, "vulnerabilities": 0, "maintainers": 0}

    # Create packages first
    for pkg in data.get("packages", []):
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

    logger.info("packages_ingested", count=counts["packages"])

    # Create dependencies
    for dep in data.get("dependencies", []):
        try:
            graph.query(
                queries.CREATE_DEPENDENCY,
                {
                    "source": dep["source"],
                    "target": dep["target"],
                    "version_constraint": dep["version_constraint"],
                    "dep_type": dep["dep_type"],
                },
            )
            counts["dependencies"] += 1
        except Exception as exc:
            logger.warning(
                "dependency_skipped", source=dep["source"], target=dep["target"], error=str(exc)
            )

    logger.info("dependencies_ingested", count=counts["dependencies"])

    # Create vulnerabilities
    for vuln in data.get("vulnerabilities", []):
        try:
            graph.query(
                queries.CREATE_VULNERABILITY,
                {
                    "vuln_id": vuln["vuln_id"],
                    "severity": vuln["severity"],
                    "description": vuln["description"],
                    "affected_package": vuln["affected_package"],
                },
            )
            counts["vulnerabilities"] += 1
        except Exception as exc:
            logger.warning("vulnerability_skipped", vuln_id=vuln["vuln_id"], error=str(exc))

    logger.info("vulnerabilities_ingested", count=counts["vulnerabilities"])

    # Create maintainers
    for maint in data.get("maintainers", []):
        try:
            graph.query(
                queries.CREATE_MAINTAINER,
                {
                    "name": maint["name"],
                    "email": maint["email"],
                    "package": maint["package"],
                },
            )
            counts["maintainers"] += 1
        except Exception as exc:
            logger.warning("maintainer_skipped", name=maint["name"], error=str(exc))

    logger.info("maintainers_ingested", count=counts["maintainers"])

    return counts


def ingest_requirements_txt(graph: Graph, path: Path) -> dict[str, int]:
    """Parse and ingest a Python requirements.txt file."""
    counts = {"packages": 0, "dependencies": 0}
    lines = path.read_text().strip().splitlines()

    root_name = path.parent.name or "my-project"
    graph.query(
        queries.CREATE_PACKAGE,
        {
            "name": root_name,
            "version": "0.0.0",
            "license": "Unknown",
            "description": f"Project from {path.name}",
            "downloads": 0,
        },
    )
    counts["packages"] += 1

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        # Parse "package==version", "package>=version", "package"
        name, version, constraint = _parse_requirement(line)
        graph.query(
            queries.CREATE_PACKAGE,
            {
                "name": name,
                "version": version,
                "license": "Unknown",
                "description": f"Imported from {path.name}",
                "downloads": 0,
            },
        )
        counts["packages"] += 1

        graph.query(
            queries.CREATE_DEPENDENCY,
            {
                "source": root_name,
                "target": name,
                "version_constraint": constraint,
                "dep_type": "runtime",
            },
        )
        counts["dependencies"] += 1

    logger.info("requirements_ingested", path=str(path), counts=counts)
    return counts


def ingest_package_json(graph: Graph, path: Path) -> dict[str, int]:
    """Parse and ingest a Node.js package.json file."""
    counts = {"packages": 0, "dependencies": 0}

    with open(path) as f:
        data = json.load(f)

    root_name = data.get("name", path.parent.name)
    root_version = data.get("version", "0.0.0")
    graph.query(
        queries.CREATE_PACKAGE,
        {
            "name": root_name,
            "version": root_version,
            "license": data.get("license", "Unknown"),
            "description": data.get("description", ""),
            "downloads": 0,
        },
    )
    counts["packages"] += 1

    for dep_type, dep_key in [("runtime", "dependencies"), ("dev", "devDependencies")]:
        for name, version_constraint in data.get(dep_key, {}).items():
            graph.query(
                queries.CREATE_PACKAGE,
                {
                    "name": name,
                    "version": version_constraint.lstrip("^~>=<"),
                    "license": "Unknown",
                    "description": f"Imported from {path.name}",
                    "downloads": 0,
                },
            )
            counts["packages"] += 1

            graph.query(
                queries.CREATE_DEPENDENCY,
                {
                    "source": root_name,
                    "target": name,
                    "version_constraint": version_constraint,
                    "dep_type": dep_type,
                },
            )
            counts["dependencies"] += 1

    logger.info("package_json_ingested", path=str(path), counts=counts)
    return counts


def _parse_requirement(line: str) -> tuple[str, str, str]:
    """Parse a single requirement line into (name, version, constraint)."""
    for sep in ["==", ">=", "<=", "~=", "!="]:
        if sep in line:
            parts = line.split(sep, 1)
            name = parts[0].strip().split("[")[0]  # Handle extras like pkg[extra]
            version = parts[1].strip().split(";")[0].strip().split(",")[0].strip()
            return name, version, f"{sep}{version}"
    # No version constraint
    name = line.strip().split(";")[0].strip().split("[")[0]
    return name, "0.0.0", "*"
