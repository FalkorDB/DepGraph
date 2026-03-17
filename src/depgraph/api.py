"""FastAPI REST API for DepGraph."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

_cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
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


# --- Registry Ingestion ---


@app.post("/ingest/npm/{package_name}", response_model=dict[str, int])
def ingest_npm(
    package_name: str,
    max_depth: int = Query(default=3, ge=1, le=5),
    include_dev: bool = Query(default=False),
) -> dict[str, int]:
    """Fetch a real npm package and its transitive dependencies from the registry."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    from depgraph.ingest.registry import ingest_npm_package

    return ingest_npm_package(_db.graph, package_name, max_depth=max_depth, include_dev=include_dev)


@app.post("/ingest/pypi/{package_name}", response_model=dict[str, int])
def ingest_pypi(
    package_name: str,
    max_depth: int = Query(default=3, ge=1, le=5),
    include_extras: bool = Query(default=False),
) -> dict[str, int]:
    """Fetch a real PyPI package and its transitive dependencies from the registry."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    from depgraph.ingest.registry import ingest_pypi_package

    return ingest_pypi_package(
        _db.graph, package_name, max_depth=max_depth, include_extras=include_extras
    )


# --- SBOM Export/Import ---


@app.get("/sbom/cyclonedx")
def export_cyclonedx() -> dict[str, Any]:
    """Export the dependency graph as a CycloneDX 1.5 SBOM."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    from depgraph.sbom import export_cyclonedx as _export_cdx

    return _export_cdx(_db.graph)


@app.get("/sbom/spdx")
def export_spdx() -> dict[str, Any]:
    """Export the dependency graph as an SPDX 2.3 SBOM."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    from depgraph.sbom import export_spdx as _export_spdx

    return _export_spdx(_db.graph)


@app.post("/sbom/import", response_model=dict[str, int])
async def import_sbom(request: Request) -> dict[str, int]:
    """Import a CycloneDX or SPDX SBOM (JSON) to populate the graph."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    body = await request.json()
    from depgraph.sbom import import_sbom as _import_sbom

    return _import_sbom(_db.graph, body)


# --- Vulnerability Scanning (OSV.dev) ---


@app.post("/vulnerabilities/scan", response_model=dict[str, Any])
def scan_all_vulnerabilities() -> dict[str, Any]:
    """Scan all packages in the graph against the OSV.dev vulnerability database."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    from depgraph.ingest.osv import scan_graph_packages

    return scan_graph_packages(_db.graph)


@app.get("/vulnerabilities/scan/{package_name}", response_model=dict[str, Any])
def scan_package_vulnerabilities(
    package_name: str,
    ecosystem: str = Query(default="npm", pattern="^(npm|PyPI)$"),
) -> dict[str, Any]:
    """Scan a single package against OSV.dev and ingest any vulnerabilities."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    engine = _get_engine()
    pkg = engine.get_package(package_name)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
    from depgraph.ingest.osv import scan_and_ingest_package

    return scan_and_ingest_package(_db.graph, package_name, pkg.version, ecosystem)


# --- Webhooks for Incremental Updates ---


@app.post("/webhooks/npm")
async def webhook_npm(request: Request) -> dict[str, str]:
    """Receive npm registry webhook events for incremental graph updates."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    body = await request.json()
    from depgraph.webhooks import handle_npm_webhook

    handle_npm_webhook(_db.graph, body)
    return {"status": "processed"}


@app.post("/webhooks/pypi")
async def webhook_pypi(request: Request) -> dict[str, str]:
    """Receive PyPI webhook events for incremental graph updates."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    body = await request.json()
    from depgraph.webhooks import handle_pypi_webhook

    handle_pypi_webhook(_db.graph, body)
    return {"status": "processed"}


@app.post("/webhooks/generic")
async def webhook_generic(request: Request) -> dict[str, str]:
    """Generic webhook for any package update event."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    body = await request.json()
    from depgraph.webhooks import handle_generic_webhook

    handle_generic_webhook(_db.graph, body)
    return {"status": "processed"}


# --- Graph Visualization Data ---

# Color palette for node labels
_LABEL_COLORS: dict[str, str] = {
    "Package": "#4ECDC4",
    "Vulnerability": "#FF6B6B",
    "Maintainer": "#45B7D1",
}

_RELATIONSHIP_COLORS: dict[str, str] = {
    "DEPENDS_ON": "#888888",
    "AFFECTS": "#FF6B6B",
    "MAINTAINS": "#45B7D1",
}


def _build_graph_data(
    graph: Any,
    node_query: str,
    link_query: str,
    node_params: dict[str, Any] | None = None,
    link_params: dict[str, Any] | None = None,
    highlight_nodes: set[str] | None = None,
    highlight_color: str = "#FFD93D",
    size_map: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build canvas-compatible graph data from Cypher queries."""
    nodes_result = graph.query(node_query, node_params or {})
    links_result = graph.query(link_query, link_params or {})

    node_id_map: dict[str, int] = {}
    nodes: list[dict[str, Any]] = []
    for i, row in enumerate(nodes_result.result_set):
        name, label = row[0], row[1]
        if name in node_id_map:
            continue
        nid = i + 1
        node_id_map[name] = nid
        color = _LABEL_COLORS.get(label, "#999999")
        if highlight_nodes and name in highlight_nodes:
            color = highlight_color
        size = 6
        if size_map and name in size_map:
            size = size_map[name]
        nodes.append(
            {
                "id": nid,
                "labels": [label],
                "color": color,
                "visible": True,
                "size": size,
                "data": {"name": name, "label": label},
            }
        )

    links: list[dict[str, Any]] = []
    link_id = 1
    for row in links_result.result_set:
        src_name, tgt_name, rel_type = row[0], row[1], row[2]
        src_id = node_id_map.get(src_name)
        tgt_id = node_id_map.get(tgt_name)
        if src_id and tgt_id:
            links.append(
                {
                    "id": link_id,
                    "relationship": rel_type,
                    "color": _RELATIONSHIP_COLORS.get(rel_type, "#AAAAAA"),
                    "source": src_id,
                    "target": tgt_id,
                    "visible": True,
                    "data": {"type": rel_type},
                }
            )
            link_id += 1

    return {"nodes": nodes, "links": links}


@app.get("/graph/data")
def graph_data() -> dict[str, Any]:
    """Full graph data for canvas visualization."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    return _build_graph_data(
        _db.graph,
        node_query="MATCH (n) RETURN n.name AS name, head(labels(n)) AS label",
        link_query=("MATCH (a)-[r]->(b) RETURN a.name AS src, b.name AS tgt, type(r) AS rel"),
    )


@app.get("/graph/blast-radius/{package_name}")
def graph_blast_radius(package_name: str) -> dict[str, Any]:
    """Subgraph showing blast radius for a package."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    engine = _get_engine()
    pkg = engine.get_package(package_name)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")

    result = engine.blast_radius(package_name)
    affected_names = {ap.name for ap in result.affected_packages}
    affected_names.add(package_name)

    # Build subgraph of only relevant nodes
    return _build_graph_data(
        _db.graph,
        node_query=(
            "MATCH (n:Package) WHERE n.name IN $names "
            "RETURN n.name AS name, head(labels(n)) AS label"
        ),
        link_query=(
            "MATCH (a:Package)-[r:DEPENDS_ON]->(b:Package) "
            "WHERE a.name IN $names AND b.name IN $names "
            "RETURN a.name AS src, b.name AS tgt, type(r) AS rel"
        ),
        node_params={"names": list(affected_names)},
        link_params={"names": list(affected_names)},
        highlight_nodes={package_name},
        highlight_color="#FF6B6B",
    )


@app.get("/graph/cycles")
def graph_cycles() -> dict[str, Any]:
    """Subgraph highlighting cycle nodes."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    engine = _get_engine()
    cycle_result = engine.find_cycles()
    cycle_nodes: set[str] = set()
    for cycle in cycle_result.cycles:
        cycle_nodes.update(cycle)

    if not cycle_nodes:
        return {"nodes": [], "links": []}

    return _build_graph_data(
        _db.graph,
        node_query=(
            "MATCH (n:Package) WHERE n.name IN $names "
            "RETURN n.name AS name, head(labels(n)) AS label"
        ),
        link_query=(
            "MATCH (a:Package)-[r:DEPENDS_ON]->(b:Package) "
            "WHERE a.name IN $names AND b.name IN $names "
            "RETURN a.name AS src, b.name AS tgt, type(r) AS rel"
        ),
        node_params={"names": list(cycle_nodes)},
        link_params={"names": list(cycle_nodes)},
        highlight_nodes=cycle_nodes,
        highlight_color="#FF6B6B",
    )


# --- Static files for frontend SPA ---

_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        """Serve the React SPA for any unmatched routes."""
        file_path = (_STATIC_DIR / full_path).resolve()
        # Block path traversal — resolved path must stay within _STATIC_DIR
        if not str(file_path).startswith(str(_STATIC_DIR)):
            return FileResponse(_STATIC_DIR / "index.html")
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_STATIC_DIR / "index.html")
