"""OSV.dev vulnerability database integration — scan packages for known CVEs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog

from depgraph.graph import queries

if TYPE_CHECKING:
    from falkordb import Graph

logger = structlog.get_logger(__name__)

OSV_API_URL = "https://api.osv.dev/v1"
OSV_REQUEST_TIMEOUT = 15.0

# Query to list all packages with versions
_LIST_ALL_PACKAGES = """
MATCH (p:Package)
RETURN p.name AS name, p.version AS version
ORDER BY p.name
"""


def query_osv(name: str, version: str, ecosystem: str = "npm") -> list[dict[str, Any]]:
    """Query OSV.dev for vulnerabilities affecting a specific package version.

    Args:
        name: Package name.
        version: Package version.
        ecosystem: Package ecosystem (npm, PyPI, etc.).

    Returns:
        List of vulnerability dicts from OSV API.
    """
    logger.info("osv_query", package=name, version=version, ecosystem=ecosystem)

    payload: dict[str, Any] = {
        "package": {"name": name, "ecosystem": ecosystem},
    }
    if version and version != "0.0.0":
        payload["version"] = version

    try:
        with httpx.Client(timeout=OSV_REQUEST_TIMEOUT) as client:
            resp = client.post(f"{OSV_API_URL}/query", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("osv_query_failed", package=name, status=exc.response.status_code)
        return []
    except httpx.RequestError as exc:
        logger.warning("osv_request_error", package=name, error=str(exc))
        return []

    return data.get("vulns", [])


def scan_and_ingest_package(
    graph: Graph,
    name: str,
    version: str,
    ecosystem: str = "npm",
) -> dict[str, Any]:
    """Scan a single package against OSV.dev and ingest vulnerabilities into the graph.

    Returns:
        Dict with packages_scanned, vulnerabilities_found, and details.
    """
    vulns = query_osv(name, version, ecosystem)
    ingested: list[dict[str, str]] = []

    for vuln in vulns:
        vuln_id = vuln.get("id", "")
        if not vuln_id:
            continue

        severity = _extract_severity(vuln)
        summary = (vuln.get("summary") or vuln.get("details") or "")[:500]

        try:
            graph.query(
                queries.CREATE_VULNERABILITY,
                {
                    "vuln_id": vuln_id,
                    "severity": severity,
                    "description": summary,
                    "affected_package": name,
                },
            )
            ingested.append(
                {
                    "id": vuln_id,
                    "severity": severity,
                    "package": name,
                    "summary": summary[:200],
                }
            )
        except Exception as exc:
            logger.warning("osv_ingest_failed", vuln_id=vuln_id, error=str(exc))

    logger.info("osv_scan_complete", package=name, vulns_found=len(ingested))
    return {
        "packages_scanned": 1,
        "vulnerabilities_found": len(ingested),
        "vulnerabilities": ingested,
    }


def scan_graph_packages(
    graph: Graph,
    ecosystem: str = "npm",
) -> dict[str, Any]:
    """Scan all packages in the graph against OSV.dev.

    Returns:
        Aggregated scan results with total counts and per-vulnerability details.
    """
    logger.info("osv_scan_all", ecosystem=ecosystem)

    result = graph.query(_LIST_ALL_PACKAGES)
    all_vulns: list[dict[str, str]] = []
    packages_scanned = 0

    for row in result.result_set:
        name, version = row[0], row[1]
        packages_scanned += 1

        vulns = query_osv(name, version, ecosystem)
        for vuln in vulns:
            vuln_id = vuln.get("id", "")
            if not vuln_id:
                continue

            severity = _extract_severity(vuln)
            summary = (vuln.get("summary") or vuln.get("details") or "")[:500]

            try:
                graph.query(
                    queries.CREATE_VULNERABILITY,
                    {
                        "vuln_id": vuln_id,
                        "severity": severity,
                        "description": summary,
                        "affected_package": name,
                    },
                )
                all_vulns.append(
                    {
                        "id": vuln_id,
                        "severity": severity,
                        "package": name,
                        "summary": summary[:200],
                    }
                )
            except Exception as exc:
                logger.warning("osv_ingest_failed", vuln_id=vuln_id, error=str(exc))

    logger.info("osv_scan_all_complete", packages_scanned=packages_scanned, vulns=len(all_vulns))
    return {
        "packages_scanned": packages_scanned,
        "vulnerabilities_found": len(all_vulns),
        "vulnerabilities": all_vulns,
    }


def _extract_severity(vuln: dict[str, Any]) -> str:
    """Extract a severity level from an OSV vulnerability record.

    OSV uses CVSS vectors in database_specific or severity array.
    We map to our simple critical/high/medium/low scale.
    """
    # Check severity array first (OSV format)
    for sev in vuln.get("severity", []):
        score_str = sev.get("score", "")
        # CVSS vector — extract base score if present
        if "CVSS" in sev.get("type", ""):
            return _cvss_vector_to_severity(score_str)

    # Check database_specific for severity
    db_specific = vuln.get("database_specific", {})
    if "severity" in db_specific:
        raw = db_specific["severity"].upper()
        if raw in ("CRITICAL",):
            return "critical"
        if raw in ("HIGH",):
            return "high"
        if raw in ("MODERATE", "MEDIUM"):
            return "medium"
        if raw in ("LOW",):
            return "low"

    # Fallback: check ecosystem-specific severity in affected[].ecosystem_specific
    for affected in vuln.get("affected", []):
        eco = affected.get("ecosystem_specific", {})
        if "severity" in eco:
            raw = eco["severity"].upper()
            if "CRITICAL" in raw:
                return "critical"
            if "HIGH" in raw:
                return "high"
            if "MODERATE" in raw or "MEDIUM" in raw:
                return "medium"
            if "LOW" in raw:
                return "low"

    return "medium"


def _cvss_vector_to_severity(vector: str) -> str:
    """Convert a CVSS vector string to a simple severity level.

    Looks for the base score in the vector. Falls back to heuristics.
    """
    # Try to find numeric score (some OSV entries include it)
    # CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H — score not in vector
    # Use attack complexity and impact as heuristic
    vector_upper = vector.upper()
    if "/C:H/I:H/A:H" in vector_upper:
        return "critical"
    if "/C:H" in vector_upper or "/I:H" in vector_upper or "/A:H" in vector_upper:
        return "high"
    if "/C:L" in vector_upper or "/I:L" in vector_upper:
        return "medium"
    return "low"
