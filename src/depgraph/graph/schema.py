"""Graph schema setup — creates indices for efficient querying."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from falkordb import Graph

logger = structlog.get_logger(__name__)

SCHEMA_QUERIES = [
    # Indices for fast lookups (FalkorDB syntax)
    "CREATE INDEX FOR (p:Package) ON (p.name)",
    "CREATE INDEX FOR (v:Vulnerability) ON (v.vuln_id)",
    "CREATE INDEX FOR (m:Maintainer) ON (m.name)",
]


def ensure_schema(graph: Graph) -> None:
    """Create indices if they don't already exist."""
    for query in SCHEMA_QUERIES:
        try:
            graph.query(query)
        except Exception as exc:
            # Some FalkorDB versions handle IF NOT EXISTS differently
            logger.debug("schema_query_note", query=query, note=str(exc))
    logger.info("graph_schema_ensured")


def clear_graph(graph: Graph) -> None:
    """Remove all nodes and relationships from the graph."""
    graph.query("MATCH (n) DETACH DELETE n")
    logger.info("graph_cleared")


def get_stats(graph: Graph) -> dict[str, int]:
    """Return counts of nodes and relationships by type."""
    pkg_result = graph.query("MATCH (p:Package) RETURN count(p) AS c")
    dep_result = graph.query("MATCH ()-[r:DEPENDS_ON]->() RETURN count(r) AS c")
    vuln_result = graph.query("MATCH (v:Vulnerability) RETURN count(v) AS c")
    maint_result = graph.query("MATCH (m:Maintainer) RETURN count(m) AS c")

    return {
        "packages": pkg_result.result_set[0][0] if pkg_result.result_set else 0,
        "dependencies": dep_result.result_set[0][0] if dep_result.result_set else 0,
        "vulnerabilities": vuln_result.result_set[0][0] if vuln_result.result_set else 0,
        "maintainers": maint_result.result_set[0][0] if maint_result.result_set else 0,
    }
