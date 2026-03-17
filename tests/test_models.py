"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from depgraph.models import (
    AffectedPackage,
    BlastRadiusResult,
    DependencyInput,
    LicenseRisk,
    PackageInput,
    Severity,
    VulnerabilityInput,
)


class TestPackageInput:
    def test_valid_package(self) -> None:
        pkg = PackageInput(name="express", version="4.18.2")
        assert pkg.name == "express"
        assert pkg.license == "MIT"

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PackageInput(name="", version="1.0.0")

    def test_negative_downloads_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PackageInput(name="pkg", version="1.0.0", downloads=-1)


class TestDependencyInput:
    def test_valid_dependency(self) -> None:
        dep = DependencyInput(source="app", target="express")
        assert dep.version_constraint == "*"
        assert dep.dep_type.value == "runtime"


class TestVulnerabilityInput:
    def test_valid_vulnerability(self) -> None:
        vuln = VulnerabilityInput(
            vuln_id="CVE-2024-1234",
            severity=Severity.CRITICAL,
            affected_package="lodash",
        )
        assert vuln.severity == Severity.CRITICAL


class TestBlastRadiusResult:
    def test_serialization(self) -> None:
        result = BlastRadiusResult(
            source_package="core",
            affected_packages=[
                AffectedPackage(name="app", depth=2, path=["app", "lib", "core"]),
            ],
            total_affected=1,
            max_depth=2,
        )
        data = result.model_dump()
        assert data["source_package"] == "core"
        assert len(data["affected_packages"]) == 1


class TestLicenseRisk:
    def test_risk_values(self) -> None:
        assert LicenseRisk.PERMISSIVE == "permissive"
        assert LicenseRisk.STRONG_COPYLEFT == "strong_copyleft"
