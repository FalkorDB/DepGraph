"""Realistic package ecosystem seed data generator.

Generates an interconnected graph of packages, dependencies, vulnerabilities,
and maintainers that mimics a real-world npm/pip-like ecosystem.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

# Realistic package names grouped by domain
PACKAGE_POOLS: dict[str, list[dict[str, str]]] = {
    "web": [
        {"name": "express", "desc": "Fast web framework"},
        {"name": "fastify", "desc": "High-performance web framework"},
        {"name": "koa", "desc": "Middleware-based web framework"},
        {"name": "hapi", "desc": "Enterprise web framework"},
        {"name": "flask-core", "desc": "Lightweight web framework"},
    ],
    "http": [
        {"name": "axios", "desc": "HTTP client library"},
        {"name": "node-fetch", "desc": "Fetch API for Node.js"},
        {"name": "got", "desc": "HTTP request library"},
        {"name": "superagent", "desc": "Progressive HTTP client"},
    ],
    "utility": [
        {"name": "lodash", "desc": "Utility library for common operations"},
        {"name": "underscore", "desc": "Functional programming helpers"},
        {"name": "ramda", "desc": "Practical functional library"},
        {"name": "date-fns", "desc": "Modern date utility library"},
        {"name": "moment", "desc": "Date manipulation library"},
        {"name": "uuid", "desc": "UUID generation library"},
        {"name": "nanoid", "desc": "Tiny unique string generator"},
    ],
    "security": [
        {"name": "helmet", "desc": "HTTP security headers"},
        {"name": "cors", "desc": "Cross-origin resource sharing"},
        {"name": "csrf-shield", "desc": "CSRF protection middleware"},
        {"name": "bcrypt-lib", "desc": "Password hashing library"},
        {"name": "jsonwebtoken", "desc": "JWT implementation"},
    ],
    "database": [
        {"name": "knex", "desc": "SQL query builder"},
        {"name": "sequelize", "desc": "ORM for SQL databases"},
        {"name": "typeorm", "desc": "TypeScript ORM"},
        {"name": "prisma-client", "desc": "Next-gen database client"},
        {"name": "mongoose", "desc": "MongoDB object modeling"},
        {"name": "redis-client", "desc": "Redis client library"},
        {"name": "pg-driver", "desc": "PostgreSQL driver"},
    ],
    "validation": [
        {"name": "joi", "desc": "Schema validation"},
        {"name": "zod-core", "desc": "TypeScript-first schema validation"},
        {"name": "yup", "desc": "Object schema validation"},
        {"name": "ajv", "desc": "JSON Schema validator"},
    ],
    "logging": [
        {"name": "winston", "desc": "Universal logging library"},
        {"name": "pino", "desc": "Low-overhead JSON logger"},
        {"name": "bunyan", "desc": "Structured logging for Node"},
        {"name": "debug-util", "desc": "Tiny debugging utility"},
    ],
    "testing": [
        {"name": "jest-core", "desc": "Testing framework"},
        {"name": "mocha", "desc": "Feature-rich test framework"},
        {"name": "chai", "desc": "BDD/TDD assertion library"},
        {"name": "sinon", "desc": "Standalone test spies, stubs, mocks"},
        {"name": "supertest", "desc": "HTTP assertions for testing"},
    ],
    "infra": [
        {"name": "dotenv", "desc": "Environment variable loader"},
        {"name": "config-store", "desc": "Configuration management"},
        {"name": "chalk-color", "desc": "Terminal string styling"},
        {"name": "commander", "desc": "Command-line interfaces"},
        {"name": "inquirer", "desc": "Interactive CLI prompts"},
        {"name": "glob-match", "desc": "Glob pattern matching"},
        {"name": "minimatch", "desc": "Glob matcher library"},
        {"name": "semver", "desc": "Semantic versioning parser"},
        {"name": "path-util", "desc": "Path manipulation utilities"},
    ],
    "encoding": [
        {"name": "qs", "desc": "Querystring parser"},
        {"name": "mime-types", "desc": "MIME type mapping"},
        {"name": "iconv-lite", "desc": "Character encoding conversion"},
        {"name": "buffer-util", "desc": "Buffer utility functions"},
        {"name": "safe-buffer", "desc": "Safer Buffer API"},
    ],
    "stream": [
        {"name": "readable-stream", "desc": "Streams compatibility library"},
        {"name": "through2", "desc": "Tiny stream wrapper"},
        {"name": "pump", "desc": "Pipe streams and handle errors"},
        {"name": "concat-stream", "desc": "Writable stream that concatenates"},
    ],
    "crypto": [
        {"name": "crypto-utils", "desc": "Cryptographic utility functions"},
        {"name": "hash-sum", "desc": "Blazing fast hash function"},
    ],
    "compression": [
        {"name": "zlib-wrap", "desc": "Zlib compression bindings"},
        {"name": "brotli-compress", "desc": "Brotli compression"},
    ],
}

LICENSES = [
    "MIT",
    "MIT",
    "MIT",
    "MIT",
    "MIT",  # weighted toward MIT
    "Apache-2.0",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "ISC",
    "LGPL-3.0",
    "GPL-3.0",
    "MPL-2.0",
]

MAINTAINER_NAMES = [
    "alice_dev",
    "bob_engineer",
    "carol_ops",
    "dan_security",
    "eve_platform",
    "frank_infra",
    "grace_data",
    "henry_backend",
    "iris_frontend",
    "jack_sre",
    "kate_devtools",
    "liam_testing",
    "mia_core",
    "noah_network",
    "olivia_cloud",
]

VULNERABILITY_TEMPLATES = [
    {"prefix": "CVE-2024", "severity": "critical", "desc": "Remote code execution via {pkg}"},
    {"prefix": "CVE-2024", "severity": "high", "desc": "Prototype pollution in {pkg}"},
    {"prefix": "CVE-2024", "severity": "high", "desc": "Path traversal vulnerability in {pkg}"},
    {"prefix": "CVE-2024", "severity": "medium", "desc": "Regex denial of service in {pkg}"},
    {"prefix": "CVE-2024", "severity": "medium", "desc": "Open redirect via {pkg} URL parsing"},
    {"prefix": "CVE-2024", "severity": "low", "desc": "Information disclosure in {pkg} debug mode"},
    {"prefix": "CVE-2025", "severity": "critical", "desc": "Arbitrary file write through {pkg}"},
    {"prefix": "CVE-2025", "severity": "high", "desc": "SQL injection via {pkg} query builder"},
]


def generate_ecosystem(
    num_packages: int = 80,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a realistic package ecosystem.

    Returns a dict with packages, dependencies, vulnerabilities, and maintainers.
    """
    rng = random.Random(seed)

    # Collect all packages from pools
    all_pool_packages = []
    for pool in PACKAGE_POOLS.values():
        all_pool_packages.extend(pool)

    # Select packages
    selected = (
        all_pool_packages[:num_packages]
        if num_packages <= len(all_pool_packages)
        else all_pool_packages
    )
    packages: list[dict[str, Any]] = []
    for pkg in selected:
        packages.append(
            {
                "name": pkg["name"],
                "version": f"{rng.randint(1, 15)}.{rng.randint(0, 20)}.{rng.randint(0, 10)}",
                "license": rng.choice(LICENSES),
                "description": pkg["desc"],
                "downloads": rng.randint(1000, 50_000_000),
            }
        )

    pkg_names = [p["name"] for p in packages]

    # Generate realistic dependencies based on domain relationships
    dependencies = _generate_dependencies(packages, rng)

    # Add a few deliberate cycles for testing cycle detection
    if len(pkg_names) >= 4:
        cycle_deps = _generate_cycles(pkg_names, rng)
        dependencies.extend(cycle_deps)

    # Generate vulnerabilities (5-10% of packages have vulnerabilities)
    vuln_count = max(3, len(packages) // 12)
    vulnerable_packages = rng.sample(pkg_names, min(vuln_count, len(pkg_names)))
    vulnerabilities = []
    for i, pkg_name in enumerate(vulnerable_packages):
        template = rng.choice(VULNERABILITY_TEMPLATES)
        vulnerabilities.append(
            {
                "vuln_id": f"{template['prefix']}-{1000 + i}",
                "severity": template["severity"],
                "description": template["desc"].format(pkg=pkg_name),
                "affected_package": pkg_name,
            }
        )

    # Assign maintainers (each maintainer owns 2-6 packages)
    maintainers = []
    for maint_name in MAINTAINER_NAMES[: min(10, len(packages) // 3)]:
        num_owned = rng.randint(2, min(6, len(pkg_names)))
        owned = rng.sample(pkg_names, num_owned)
        for pkg_name in owned:
            maintainers.append(
                {
                    "name": maint_name,
                    "email": f"{maint_name}@example.com",
                    "package": pkg_name,
                }
            )

    return {
        "packages": packages,
        "dependencies": dependencies,
        "vulnerabilities": vulnerabilities,
        "maintainers": maintainers,
    }


def _generate_dependencies(
    packages: list[dict[str, Any]], rng: random.Random
) -> list[dict[str, str]]:
    """Generate realistic dependency relationships between packages."""
    deps: list[dict[str, str]] = []
    pkg_names = [p["name"] for p in packages]
    pkg_set = set(pkg_names)

    # Domain-based dependency rules (higher-level depends on lower-level)
    domain_deps: dict[str, list[str]] = {
        "web": ["http", "utility", "security", "validation", "logging", "encoding"],
        "http": ["utility", "encoding", "stream"],
        "database": ["utility", "logging", "stream"],
        "security": ["crypto", "utility", "encoding"],
        "validation": ["utility"],
        "testing": ["utility", "http"],
        "logging": ["utility", "stream"],
        "infra": ["utility"],
        "compression": ["stream"],
        "stream": ["utility"],
    }

    pkg_to_domain = {}
    for domain, pool in PACKAGE_POOLS.items():
        for pkg in pool:
            pkg_to_domain[pkg["name"]] = domain

    # Create domain-based dependencies
    for pkg_name in pkg_names:
        domain = pkg_to_domain.get(pkg_name)
        if not domain or domain not in domain_deps:
            continue

        target_domains = domain_deps[domain]
        for target_domain in target_domains:
            if target_domain not in PACKAGE_POOLS:
                continue
            candidates = [p["name"] for p in PACKAGE_POOLS[target_domain] if p["name"] in pkg_set]
            if candidates and rng.random() < 0.4:
                target = rng.choice(candidates)
                if target != pkg_name:
                    deps.append(
                        {
                            "source": pkg_name,
                            "target": target,
                            "version_constraint": f"^{rng.randint(1, 5)}.0.0",
                            "dep_type": "runtime",
                        }
                    )

    # Add some random cross-domain dependencies
    for _ in range(len(packages) // 4):
        src = rng.choice(pkg_names)
        tgt = rng.choice(pkg_names)
        if src != tgt:
            deps.append(
                {
                    "source": src,
                    "target": tgt,
                    "version_constraint": f">={rng.randint(1, 3)}.0.0",
                    "dep_type": rng.choice(["runtime", "runtime", "dev", "optional"]),
                }
            )

    # Deduplicate
    seen: set[tuple[str, str]] = set()
    unique_deps: list[dict[str, str]] = []
    for dep in deps:
        key = (dep["source"], dep["target"])
        if key not in seen:
            seen.add(key)
            unique_deps.append(dep)

    return unique_deps


def _generate_cycles(pkg_names: list[str], rng: random.Random) -> list[dict[str, str]]:
    """Generate 1-2 deliberate dependency cycles for testing."""
    cycle_deps: list[dict[str, str]] = []
    candidates = rng.sample(pkg_names, min(6, len(pkg_names)))

    # Create one 3-node cycle: A->B->C->A
    if len(candidates) >= 3:
        a, b, c = candidates[0], candidates[1], candidates[2]
        for src, tgt in [(a, b), (b, c), (c, a)]:
            cycle_deps.append(
                {
                    "source": src,
                    "target": tgt,
                    "version_constraint": "^1.0.0",
                    "dep_type": "runtime",
                }
            )

    return cycle_deps


def save_ecosystem(data: dict[str, Any], path: Path) -> None:
    """Save generated ecosystem data to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_ecosystem(path: Path) -> dict[str, Any]:
    """Load ecosystem data from a JSON file."""
    with open(path) as f:
        return json.load(f)
