"""SBOM (Software Bill of Materials) export and import — CycloneDX 1.5 and SPDX 2.3."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from depgraph.graph import queries

if TYPE_CHECKING:
    from falkordb import Graph

logger = structlog.get_logger(__name__)

# --- Queries for SBOM data extraction ---

_ALL_PACKAGES = """
MATCH (p:Package)
RETURN p.name AS name, p.version AS version, p.license AS license,
       p.description AS description
ORDER BY p.name
"""

_ALL_DEPENDENCIES = """
MATCH (src:Package)-[r:DEPENDS_ON]->(tgt:Package)
RETURN src.name AS source, tgt.name AS target,
       r.version_constraint AS constraint, r.dep_type AS dep_type
"""


# --- CycloneDX 1.5 ---


def export_cyclonedx(graph: Graph) -> dict[str, Any]:
    """Export the dependency graph as a CycloneDX 1.5 JSON SBOM.

    See: https://cyclonedx.org/docs/1.5/json/
    """
    logger.info("exporting_cyclonedx")

    pkg_result = graph.query(_ALL_PACKAGES)
    dep_result = graph.query(_ALL_DEPENDENCIES)

    serial = str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    # Build components
    components: list[dict[str, Any]] = []
    bom_ref_map: dict[str, str] = {}

    for row in pkg_result.result_set:
        name, version, license_id, description = row[0], row[1], row[2], row[3]
        bom_ref = f"pkg:{name}@{version}"
        bom_ref_map[name] = bom_ref

        component: dict[str, Any] = {
            "type": "library",
            "bom-ref": bom_ref,
            "name": name,
            "version": version,
            "description": description or "",
        }

        if license_id and license_id != "Unknown":
            component["licenses"] = [{"license": {"id": license_id}}]

        # Add purl for ecosystem identification
        component["purl"] = f"pkg:generic/{name}@{version}"

        components.append(component)

    # Build dependency tree
    deps_by_source: dict[str, list[str]] = {}
    for row in dep_result.result_set:
        source, target = row[0], row[1]
        if source not in deps_by_source:
            deps_by_source[source] = []
        deps_by_source[source].append(target)

    dependencies: list[dict[str, Any]] = []
    for name, bom_ref in bom_ref_map.items():
        dep_entry: dict[str, Any] = {"ref": bom_ref}
        if name in deps_by_source:
            dep_entry["dependsOn"] = [
                bom_ref_map[t] for t in deps_by_source[name] if t in bom_ref_map
            ]
        dependencies.append(dep_entry)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": [{"vendor": "DepGraph", "name": "depgraph", "version": "0.1.0"}],
        },
        "components": components,
        "dependencies": dependencies,
    }


# --- SPDX 2.3 ---


def export_spdx(graph: Graph) -> dict[str, Any]:
    """Export the dependency graph as an SPDX 2.3 JSON document.

    See: https://spdx.github.io/spdx-spec/v2.3/
    """
    logger.info("exporting_spdx")

    pkg_result = graph.query(_ALL_PACKAGES)
    dep_result = graph.query(_ALL_DEPENDENCIES)

    doc_namespace = f"https://depgraph.example/spdx/{uuid.uuid4()}"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build packages
    spdx_packages: list[dict[str, Any]] = []
    spdx_id_map: dict[str, str] = {}

    for i, row in enumerate(pkg_result.result_set):
        name, version, license_id, description = row[0], row[1], row[2], row[3]
        spdx_id = f"SPDXRef-Package-{i}"
        spdx_id_map[name] = spdx_id

        pkg_entry: dict[str, Any] = {
            "SPDXID": spdx_id,
            "name": name,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "description": description or "",
        }

        if license_id and license_id != "Unknown":
            pkg_entry["licenseConcluded"] = license_id
            pkg_entry["licenseDeclared"] = license_id
        else:
            pkg_entry["licenseConcluded"] = "NOASSERTION"
            pkg_entry["licenseDeclared"] = "NOASSERTION"

        spdx_packages.append(pkg_entry)

    # Build relationships
    relationships: list[dict[str, Any]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": spdx_id_map[next(iter(spdx_id_map))] if spdx_id_map else "NONE",
        }
    ]

    for row in dep_result.result_set:
        source, target = row[0], row[1]
        if source in spdx_id_map and target in spdx_id_map:
            relationships.append(
                {
                    "spdxElementId": spdx_id_map[source],
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": spdx_id_map[target],
                }
            )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "depgraph-sbom",
        "documentNamespace": doc_namespace,
        "creationInfo": {
            "created": timestamp,
            "creators": ["Tool: depgraph-0.1.0"],
        },
        "packages": spdx_packages,
        "relationships": relationships,
    }


# --- Import ---


def import_sbom(graph: Graph, data: dict[str, Any]) -> dict[str, int]:
    """Import a CycloneDX or SPDX SBOM JSON into the graph.

    Auto-detects the format based on top-level keys.
    """
    if "bomFormat" in data and data.get("bomFormat") == "CycloneDX":
        return _import_cyclonedx(graph, data)
    if "spdxVersion" in data:
        return _import_spdx(graph, data)
    raise ValueError("Unrecognized SBOM format — expected CycloneDX or SPDX JSON")


def _import_cyclonedx(graph: Graph, data: dict[str, Any]) -> dict[str, int]:
    """Import a CycloneDX SBOM."""
    logger.info("importing_cyclonedx")
    counts = {"packages": 0, "dependencies": 0}

    bom_ref_to_name: dict[str, str] = {}
    for comp in data.get("components", []):
        name = comp["name"]
        version = comp.get("version", "0.0.0")
        bom_ref = comp.get("bom-ref", name)
        bom_ref_to_name[bom_ref] = name

        license_id = "Unknown"
        licenses = comp.get("licenses", [])
        if licenses:
            lic = licenses[0]
            if "license" in lic:
                license_id = lic["license"].get("id", "Unknown")
            elif "expression" in lic:
                license_id = lic["expression"]

        graph.query(
            queries.CREATE_PACKAGE,
            {
                "name": name,
                "version": version,
                "license": license_id[:50],
                "description": comp.get("description", "")[:500],
                "downloads": 0,
            },
        )
        counts["packages"] += 1

    for dep in data.get("dependencies", []):
        source_ref = dep.get("ref", "")
        source_name = bom_ref_to_name.get(source_ref)
        if not source_name:
            continue
        for target_ref in dep.get("dependsOn", []):
            target_name = bom_ref_to_name.get(target_ref)
            if target_name:
                try:
                    graph.query(
                        queries.CREATE_DEPENDENCY,
                        {
                            "source": source_name,
                            "target": target_name,
                            "version_constraint": "*",
                            "dep_type": "runtime",
                        },
                    )
                    counts["dependencies"] += 1
                except Exception as exc:
                    logger.warning(
                        "cdx_dep_skip", source=source_name, target=target_name, error=str(exc)
                    )

    logger.info("cyclonedx_imported", **counts)
    return counts


def _import_spdx(graph: Graph, data: dict[str, Any]) -> dict[str, int]:
    """Import an SPDX SBOM."""
    logger.info("importing_spdx")
    counts = {"packages": 0, "dependencies": 0}

    spdx_id_to_name: dict[str, str] = {}
    for pkg in data.get("packages", []):
        name = pkg["name"]
        spdx_id = pkg.get("SPDXID", name)
        spdx_id_to_name[spdx_id] = name

        license_id = pkg.get("licenseConcluded", "Unknown")
        if license_id == "NOASSERTION":
            license_id = "Unknown"

        graph.query(
            queries.CREATE_PACKAGE,
            {
                "name": name,
                "version": pkg.get("versionInfo", "0.0.0"),
                "license": license_id[:50],
                "description": pkg.get("description", "")[:500],
                "downloads": 0,
            },
        )
        counts["packages"] += 1

    for rel in data.get("relationships", []):
        if rel.get("relationshipType") != "DEPENDS_ON":
            continue
        source_name = spdx_id_to_name.get(rel.get("spdxElementId", ""))
        target_name = spdx_id_to_name.get(rel.get("relatedSpdxElement", ""))
        if source_name and target_name:
            try:
                graph.query(
                    queries.CREATE_DEPENDENCY,
                    {
                        "source": source_name,
                        "target": target_name,
                        "version_constraint": "*",
                        "dep_type": "runtime",
                    },
                )
                counts["dependencies"] += 1
            except Exception as exc:
                logger.warning(
                    "spdx_dep_skip", source=source_name, target=target_name, error=str(exc)
                )

    logger.info("spdx_imported", **counts)
    return counts
