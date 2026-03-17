"""FalkorDB connection management with retry logic and health checks."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from falkordb import FalkorDB

if TYPE_CHECKING:
    from falkordb import Graph

    from depgraph.config import FalkorDBConfig

logger = structlog.get_logger(__name__)


class ConnectionError(Exception):
    """Raised when FalkorDB connection cannot be established."""


class GraphDB:
    """Manages FalkorDB connections with retry logic."""

    def __init__(self, config: FalkorDBConfig) -> None:
        self._config = config
        self._client: FalkorDB | None = None
        self._graph: Graph | None = None

    def connect(self) -> Graph:
        """Establish connection to FalkorDB with retries. Returns the Graph handle."""
        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 1):
            try:
                logger.info(
                    "connecting_to_falkordb",
                    host=self._config.host,
                    port=self._config.port,
                    attempt=attempt,
                )
                self._client = FalkorDB(
                    host=self._config.host,
                    port=self._config.port,
                    password=self._config.password,
                )
                self._graph = self._client.select_graph(self._config.graph_name)
                # Verify the connection works
                self._graph.query("RETURN 1")
                logger.info("falkordb_connected", graph=self._config.graph_name)
                return self._graph
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "falkordb_connection_failed",
                    attempt=attempt,
                    max_retries=self._config.max_retries,
                    error=str(exc),
                )
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_delay * attempt)

        msg = f"Failed to connect to FalkorDB after {self._config.max_retries} attempts"
        raise ConnectionError(msg) from last_error

    @property
    def graph(self) -> Graph:
        """Get the active graph handle, connecting if needed."""
        if self._graph is None:
            return self.connect()
        return self._graph

    def health_check(self) -> bool:
        """Check if the FalkorDB connection is alive."""
        try:
            self.graph.query("RETURN 1")
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the FalkorDB connection."""
        self._client = None
        self._graph = None

    def __enter__(self) -> GraphDB:
        self.connect()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
