"""Pydantic models for DepGraph entities and API responses."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# --- Enums ---


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DepType(StrEnum):
    RUNTIME = "runtime"
    DEV = "dev"
    OPTIONAL = "optional"


class LicenseRisk(StrEnum):
    PERMISSIVE = "permissive"
    WEAK_COPYLEFT = "weak_copyleft"
    STRONG_COPYLEFT = "strong_copyleft"
    UNKNOWN = "unknown"


LICENSE_RISK_MAP: dict[str, LicenseRisk] = {
    "MIT": LicenseRisk.PERMISSIVE,
    "Apache-2.0": LicenseRisk.PERMISSIVE,
    "BSD-2-Clause": LicenseRisk.PERMISSIVE,
    "BSD-3-Clause": LicenseRisk.PERMISSIVE,
    "ISC": LicenseRisk.PERMISSIVE,
    "LGPL-2.1": LicenseRisk.WEAK_COPYLEFT,
    "LGPL-3.0": LicenseRisk.WEAK_COPYLEFT,
    "MPL-2.0": LicenseRisk.WEAK_COPYLEFT,
    "GPL-2.0": LicenseRisk.STRONG_COPYLEFT,
    "GPL-3.0": LicenseRisk.STRONG_COPYLEFT,
    "AGPL-3.0": LicenseRisk.STRONG_COPYLEFT,
}


# --- Input Models ---


class PackageInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field(..., min_length=1, max_length=50)
    license: str = Field(default="MIT", max_length=50)
    description: str = Field(default="", max_length=500)
    downloads: int = Field(default=0, ge=0)


class DependencyInput(BaseModel):
    source: str = Field(..., min_length=1, description="Source package name")
    target: str = Field(..., min_length=1, description="Target package name")
    version_constraint: str = Field(default="*", max_length=50)
    dep_type: DepType = Field(default=DepType.RUNTIME)


class VulnerabilityInput(BaseModel):
    vuln_id: str = Field(..., min_length=1, max_length=100)
    severity: Severity
    description: str = Field(default="", max_length=1000)
    affected_package: str = Field(..., min_length=1)


# --- Response Models ---


class PackageInfo(BaseModel):
    name: str
    version: str
    license: str
    description: str
    downloads: int


class BlastRadiusResult(BaseModel):
    source_package: str
    affected_packages: list[AffectedPackage]
    total_affected: int
    max_depth: int


class AffectedPackage(BaseModel):
    name: str
    depth: int
    path: list[str]


class CycleResult(BaseModel):
    cycles: list[list[str]]
    total_cycles: int


class CentralityResult(BaseModel):
    packages: list[PackageCentrality]


class PackageCentrality(BaseModel):
    name: str
    direct_dependents: int
    transitive_dependents: int


class LicenseIssue(BaseModel):
    package: str
    license: str
    risk: LicenseRisk
    dependency_chain: list[str]


class LicenseReport(BaseModel):
    root_package: str
    issues: list[LicenseIssue]
    total_dependencies_checked: int


class DepthResult(BaseModel):
    package: str
    max_depth: int
    dependency_count: int
    tree: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    falkordb_connected: bool
    graph_name: str
    node_count: int
    relationship_count: int


class GraphStats(BaseModel):
    packages: int
    dependencies: int
    vulnerabilities: int
    maintainers: int


# Rebuild forward refs
BlastRadiusResult.model_rebuild()
LicenseReport.model_rebuild()
