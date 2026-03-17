"""FastAPI REST API for DepGraph."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query

from depgraph.config import load_config
from depgraph.db import GraphDB
from depgraph.graph.engine import AnalysisEngine
from depgraph.graph.schema import ensure_schema, get_stats
from depgraph.ingest.parsers import ingest_ecosystem
from depgraph.ingest.seed import generate_ecosystem
from depgraph.logging import setup_logging
from depgraph.models import (
    BlastRadiusResult,
    CentralityResult,
    CycleResult,
    DepthResult,
    GraphStats,
    HealthResponse,
    LicenseReport,
    PackageInfo,
)

logger = structlog.get_logger(__name__)

_db: GraphDB | None = None
_engine: AnalysisEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application startup and shutdown."""
    global _db, _engine
    config = load_config()
    setup_logging(config.log_level)

    _db = GraphDB(config.db)
    graph = _db.connect()
    ensure_schema(graph)
    _engine = AnalysisEngine(graph, max_depth=config.max_traversal_depth)
    logger.info("api_started", graph=config.db.graph_name)
    yield
    if _db:
        _db.close()
    logger.info("api_stopped")


app = FastAPI(
    title="DepGraph",
    description="Package Dependency Impact Analyzer powered by FalkorDB",
    version="0.1.0",
    lifespan=lifespan,
)


def _get_engine() -> AnalysisEngine:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Analysis engine not initialized")
    return _engine


# --- Health ---


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check endpoint."""
    if _db is None:
        return HealthResponse(
            status="unhealthy",
            falkordb_connected=False,
            graph_name="",
            node_count=0,
            relationship_count=0,
        )
    connected = _db.health_check()
    stats = get_stats(_db.graph) if connected else {}
    return HealthResponse(
        status="healthy" if connected else "unhealthy",
        falkordb_connected=connected,
        graph_name=_db._config.graph_name,
        node_count=stats.get("packages", 0)
        + stats.get("vulnerabilities", 0)
        + stats.get("maintainers", 0),
        relationship_count=stats.get("dependencies", 0),
    )


# --- Graph Stats ---


@app.get("/stats", response_model=GraphStats)
def stats() -> GraphStats:
    """Get graph statistics."""
    return _get_engine().graph_stats()


# --- Packages ---


@app.get("/packages", response_model=list[PackageInfo])
def list_packages(limit: int = Query(default=100, ge=1, le=1000)) -> list[PackageInfo]:
    """List all packages."""
    return _get_engine().list_packages(limit=limit)


@app.get("/packages/search", response_model=list[PackageInfo])
def search_packages(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[PackageInfo]:
    """Search packages by name."""
    return _get_engine().search_packages(q, limit=limit)


@app.get("/packages/{name}", response_model=PackageInfo)
def get_package(name: str) -> PackageInfo:
    """Get package details."""
    pkg = _get_engine().get_package(name)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package '{name}' not found")
    return pkg


# --- Analysis ---


@app.get("/analysis/blast-radius/{package_name}", response_model=BlastRadiusResult)
def blast_radius(package_name: str) -> BlastRadiusResult:
    """Compute blast radius — all packages affected if this package has an issue."""
    engine = _get_engine()
    pkg = engine.get_package(package_name)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
    return engine.blast_radius(package_name)


@app.get("/analysis/cycles", response_model=CycleResult)
def find_cycles(limit: int = Query(default=20, ge=1, le=100)) -> CycleResult:
    """Detect circular dependencies in the graph."""
    return _get_engine().find_cycles(limit=limit)


@app.get("/analysis/centrality", response_model=CentralityResult)
def centrality(limit: int = Query(default=20, ge=1, le=100)) -> CentralityResult:
    """Find the most depended-upon packages (single points of failure)."""
    return _get_engine().centrality(limit=limit)


@app.get("/analysis/licenses/{package_name}", response_model=LicenseReport)
def license_check(package_name: str) -> LicenseReport:
    """Check transitive license compatibility."""
    engine = _get_engine()
    pkg = engine.get_package(package_name)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
    return engine.license_check(package_name)


@app.get("/analysis/depth/{package_name}", response_model=DepthResult)
def dependency_depth(package_name: str) -> DepthResult:
    """Analyze dependency tree depth and structure."""
    engine = _get_engine()
    pkg = engine.get_package(package_name)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
    return engine.dependency_depth(package_name)


# --- Data Management ---


@app.post("/seed", response_model=dict[str, int])
def seed_data(
    num_packages: int = Query(default=80, ge=5, le=200),
    clear: bool = Query(default=True),
) -> dict[str, int]:
    """Seed the graph with sample ecosystem data."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    if clear:
        from depgraph.graph.schema import clear_graph

        clear_graph(_db.graph)
        ensure_schema(_db.graph)
    data = generate_ecosystem(num_packages=num_packages)
    save_path = Path("data/sample_ecosystem.json")
    from depgraph.ingest.seed import save_ecosystem

    save_ecosystem(data, save_path)
    return ingest_ecosystem(_db.graph, data)
