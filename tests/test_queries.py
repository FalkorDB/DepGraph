"""Tests for Cypher query formatting."""

from __future__ import annotations

from depgraph.graph.queries import BLAST_RADIUS, FIND_CYCLES, LICENSE_CHAIN, format_query


class TestQueryFormatting:
    def test_format_blast_radius(self) -> None:
        q = format_query(BLAST_RADIUS, max_depth=5)
        assert "*1..5" in q
        assert "$name" in q  # Parameterized
        assert "{max_depth}" not in q  # Template substituted

    def test_format_cycles(self) -> None:
        q = format_query(FIND_CYCLES, max_depth=8)
        assert "*2..8" in q
        assert "$limit" in q

    def test_format_license_chain(self) -> None:
        q = format_query(LICENSE_CHAIN, max_depth=10)
        assert "*1..10" in q
        assert "$name" in q

    def test_default_depth(self) -> None:
        q = format_query(BLAST_RADIUS)
        assert "*1..10" in q
