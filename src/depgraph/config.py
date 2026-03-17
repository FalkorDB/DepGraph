"""Configuration for DepGraph, loaded from environment variables with sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FalkorDBConfig:
    """FalkorDB connection settings."""

    host: str = field(default_factory=lambda: os.getenv("FALKORDB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("FALKORDB_PORT", "6379")))
    graph_name: str = field(default_factory=lambda: os.getenv("FALKORDB_GRAPH", "depgraph"))
    password: str | None = field(default_factory=lambda: os.getenv("FALKORDB_PASSWORD"))
    max_retries: int = field(default_factory=lambda: int(os.getenv("FALKORDB_MAX_RETRIES", "3")))
    retry_delay: float = field(
        default_factory=lambda: float(os.getenv("FALKORDB_RETRY_DELAY", "1.0"))
    )


@dataclass(frozen=True)
class AppConfig:
    """Application-wide settings."""

    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    max_traversal_depth: int = field(
        default_factory=lambda: int(os.getenv("MAX_TRAVERSAL_DEPTH", "10"))
    )
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))
    db: FalkorDBConfig = field(default_factory=FalkorDBConfig)


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    return AppConfig()
