"""Analysis engine — orchestrates graph queries and returns structured results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from depgraph.graph import queries
from depgraph.models import (
    LICENSE_RISK_MAP,
    AffectedPackage,
    BlastRadiusResult,
    CentralityResult,
    CycleResult,
    DepthResult,
    GraphStats,
    LicenseIssue,
    LicenseReport,
    LicenseRisk,
    PackageCentrality,
    PackageInfo,
)

if TYPE_CHECKING:
    from falkordb import Graph

logger = structlog.get_logger(__name__)


class AnalysisEngine:
    """Core analysis engine wrapping FalkorDB graph queries."""

    def __init__(self, graph: Graph, max_depth: int = 10) -> None:
        self._graph = graph
        self._max_depth = max_depth

    def get_package(self, name: str) -> PackageInfo | None:
        """Look up a single package by name."""
        result = self._graph.query(queries.GET_PACKAGE, {"name": name})
        if not result.result_set:
            return None
        row = result.result_set[0]
        return PackageInfo(
            name=row[0], version=row[1], license=row[2], description=row[3], downloads=row[4]
        )

    def list_packages(self, limit: int = 100) -> list[PackageInfo]:
        """List all packages in the graph."""
        result = self._graph.query(queries.LIST_PACKAGES, {"limit": limit})
        return [
            PackageInfo(name=r[0], version=r[1], license=r[2], description=r[3], downloads=r[4])
            for r in result.result_set
        ]

    def search_packages(self, query: str, limit: int = 20) -> list[PackageInfo]:
        """Search packages by name substring."""
        result = self._graph.query(queries.SEARCH_PACKAGES, {"query": query, "limit": limit})
        return [
            PackageInfo(name=r[0], version=r[1], license=r[2], description=r[3], downloads=r[4])
            for r in result.result_set
        ]

    def blast_radius(self, package_name: str) -> BlastRadiusResult:
        """Find all packages transitively affected if a given package has an issue."""
        logger.info("analyzing_blast_radius", package=package_name)
        q = queries.format_query(queries.BLAST_RADIUS, self._max_depth)
        result = self._graph.query(q, {"name": package_name})

        seen: set[str] = set()
        affected: list[AffectedPackage] = []
        max_depth = 0

        for row in result.result_set:
            name, depth, chain = row[0], row[1], row[2]
            if name not in seen:
                seen.add(name)
                affected.append(AffectedPackage(name=name, depth=depth, path=chain))
                max_depth = max(max_depth, depth)

        return BlastRadiusResult(
            source_package=package_name,
            affected_packages=affected,
            total_affected=len(affected),
            max_depth=max_depth,
        )

    def find_cycles(self, limit: int = 20) -> CycleResult:
        """Detect circular dependencies in the graph."""
        logger.info("detecting_cycles")
        q = queries.format_query(queries.FIND_CYCLES, self._max_depth)
        result = self._graph.query(q, {"limit": limit})

        # Normalize cycles: start from lexicographically smallest node
        unique_cycles: list[list[str]] = []
        seen_signatures: set[str] = set()

        for row in result.result_set:
            cycle = row[0]
            # Remove the duplicate last element (same as first)
            if len(cycle) > 1 and cycle[0] == cycle[-1]:
                cycle = cycle[:-1]
            # Normalize: rotate so smallest element is first
            if cycle:
                min_idx = cycle.index(min(cycle))
                normalized = cycle[min_idx:] + cycle[:min_idx]
                sig = "->".join(normalized)
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    unique_cycles.append(normalized)

        return CycleResult(cycles=unique_cycles, total_cycles=len(unique_cycles))

    def centrality(self, limit: int = 20) -> CentralityResult:
        """Find the most depended-upon packages (single points of failure)."""
        logger.info("computing_centrality")
        direct_result = self._graph.query(queries.DIRECT_DEPENDENTS, {"limit": limit})

        package_centralities: list[PackageCentrality] = []
        for row in direct_result.result_set:
            name, direct = row[0], row[1]
            # Compute transitive dependents for top packages
            q = queries.format_query(queries.TRANSITIVE_DEPENDENTS, self._max_depth)
            trans_result = self._graph.query(q, {"name": name})
            transitive = trans_result.result_set[0][0] if trans_result.result_set else 0
            package_centralities.append(
                PackageCentrality(
                    name=name, direct_dependents=direct, transitive_dependents=transitive
                )
            )

        return CentralityResult(packages=package_centralities)

    def license_check(self, package_name: str) -> LicenseReport:
        """Check for copyleft license propagation through transitive dependencies."""
        logger.info("checking_licenses", package=package_name)
        q = queries.format_query(queries.LICENSE_CHAIN, self._max_depth)
        result = self._graph.query(q, {"name": package_name})

        issues: list[LicenseIssue] = []
        seen: set[str] = set()
        total_checked = 0

        for row in result.result_set:
            dep_name, license_str, _depth, chain = row[0], row[1], row[2], row[3]
            total_checked += 1
            risk = LICENSE_RISK_MAP.get(license_str, LicenseRisk.UNKNOWN)
            if (
                risk in (LicenseRisk.STRONG_COPYLEFT, LicenseRisk.WEAK_COPYLEFT)
                and dep_name not in seen
            ):
                seen.add(dep_name)
                issues.append(
                    LicenseIssue(
                        package=dep_name,
                        license=license_str,
                        risk=risk,
                        dependency_chain=chain,
                    )
                )

        return LicenseReport(
            root_package=package_name,
            issues=issues,
            total_dependencies_checked=total_checked,
        )

    def dependency_depth(self, package_name: str) -> DepthResult:
        """Analyze the dependency tree depth and structure for a package."""
        logger.info("analyzing_depth", package=package_name)
        q = queries.format_query(queries.DEPENDENCY_TREE, self._max_depth)
        result = self._graph.query(q, {"name": package_name})

        max_depth = 0
        dep_count = 0
        seen: set[str] = set()
        tree: dict[str, Any] = {}

        for row in result.result_set:
            dep_name, depth, chain = row[0], row[1], row[2]
            if dep_name not in seen:
                seen.add(dep_name)
                dep_count += 1
            max_depth = max(max_depth, depth)
            _build_tree(tree, chain)

        return DepthResult(
            package=package_name,
            max_depth=max_depth,
            dependency_count=dep_count,
            tree=tree,
        )

    def graph_stats(self) -> GraphStats:
        """Get counts of all entity types in the graph."""
        from depgraph.graph.schema import get_stats

        stats = get_stats(self._graph)
        return GraphStats(**stats)


def _build_tree(tree: dict[str, Any], chain: list[str]) -> None:
    """Build a nested dict representing the dependency tree from a chain."""
    current = tree
    for node in chain:
        if node not in current:
            current[node] = {}
        current = current[node]
