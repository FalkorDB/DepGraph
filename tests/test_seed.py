"""Tests for seed data generator."""

from __future__ import annotations

from depgraph.ingest.seed import generate_ecosystem


class TestSeedGenerator:
    def test_generates_correct_count(self) -> None:
        data = generate_ecosystem(num_packages=20, seed=42)
        assert len(data["packages"]) <= 20
        assert len(data["packages"]) > 0

    def test_deterministic_with_seed(self) -> None:
        data1 = generate_ecosystem(num_packages=30, seed=123)
        data2 = generate_ecosystem(num_packages=30, seed=123)
        assert data1["packages"] == data2["packages"]
        assert data1["dependencies"] == data2["dependencies"]

    def test_different_seeds_differ(self) -> None:
        data1 = generate_ecosystem(num_packages=30, seed=1)
        data2 = generate_ecosystem(num_packages=30, seed=2)
        # At least some packages should have different versions
        versions1 = {p["name"]: p["version"] for p in data1["packages"]}
        versions2 = {p["name"]: p["version"] for p in data2["packages"]}
        # Not all versions should be the same (very unlikely with different seeds)
        assert versions1 != versions2

    def test_generates_vulnerabilities(self) -> None:
        data = generate_ecosystem(num_packages=50, seed=42)
        assert len(data["vulnerabilities"]) > 0
        for vuln in data["vulnerabilities"]:
            assert "vuln_id" in vuln
            assert "severity" in vuln
            assert "affected_package" in vuln

    def test_generates_maintainers(self) -> None:
        data = generate_ecosystem(num_packages=50, seed=42)
        assert len(data["maintainers"]) > 0

    def test_no_self_dependencies(self) -> None:
        data = generate_ecosystem(num_packages=60, seed=42)
        for dep in data["dependencies"]:
            assert dep["source"] != dep["target"]

    def test_dependencies_reference_existing_packages(self) -> None:
        data = generate_ecosystem(num_packages=60, seed=42)
        pkg_names = {p["name"] for p in data["packages"]}
        for dep in data["dependencies"]:
            assert dep["source"] in pkg_names
            assert dep["target"] in pkg_names

    def test_generates_cycles(self) -> None:
        data = generate_ecosystem(num_packages=40, seed=42)
        # Build adjacency list
        adj: dict[str, set[str]] = {}
        for dep in data["dependencies"]:
            adj.setdefault(dep["source"], set()).add(dep["target"])
        # Simple cycle detection via DFS
        has_cycle = _has_cycle(adj)
        assert has_cycle, "Seed data should contain at least one cycle for testing"


def _has_cycle(adj: dict[str, set[str]]) -> bool:
    """Check if a directed graph has a cycle."""
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, set()):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.discard(node)
        return False

    return any(node not in visited and dfs(node) for node in adj)
