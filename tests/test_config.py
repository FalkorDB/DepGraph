"""Tests for configuration module."""

from __future__ import annotations

from depgraph.config import AppConfig, FalkorDBConfig, load_config


class TestFalkorDBConfig:
    def test_defaults(self) -> None:
        config = FalkorDBConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.graph_name == "depgraph"
        assert config.password is None
        assert config.max_retries == 3

    def test_env_override(self, monkeypatch: object) -> None:
        import pytest

        mp = pytest.MonkeyPatch()
        mp.setenv("FALKORDB_HOST", "remote-host")
        mp.setenv("FALKORDB_PORT", "6380")
        mp.setenv("FALKORDB_GRAPH", "test_graph")
        try:
            config = FalkorDBConfig()
            assert config.host == "remote-host"
            assert config.port == 6380
            assert config.graph_name == "test_graph"
        finally:
            mp.undo()


class TestAppConfig:
    def test_defaults(self) -> None:
        config = AppConfig()
        assert config.log_level == "INFO"
        assert config.api_port == 8000
        assert config.max_traversal_depth == 10
        assert isinstance(config.db, FalkorDBConfig)

    def test_load_config(self) -> None:
        config = load_config()
        assert isinstance(config, AppConfig)
