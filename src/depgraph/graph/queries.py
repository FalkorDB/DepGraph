"""Core Cypher query definitions — all parameterized, never string-interpolated."""

from __future__ import annotations

# --- Package CRUD ---

CREATE_PACKAGE = """
MERGE (p:Package {name: $name})
SET p.version = $version, p.license = $license,
    p.description = $description, p.downloads = $downloads
RETURN p
"""

CREATE_DEPENDENCY = """
MATCH (src:Package {name: $source}), (tgt:Package {name: $target})
MERGE (src)-[r:DEPENDS_ON]->(tgt)
SET r.version_constraint = $version_constraint, r.dep_type = $dep_type
RETURN r
"""

CREATE_VULNERABILITY = """
MERGE (v:Vulnerability {vuln_id: $vuln_id})
SET v.severity = $severity, v.description = $description
WITH v
MATCH (p:Package {name: $affected_package})
MERGE (v)-[:AFFECTS]->(p)
RETURN v
"""

CREATE_MAINTAINER = """
MERGE (m:Maintainer {name: $name})
SET m.email = $email
WITH m
MATCH (p:Package {name: $package})
MERGE (m)-[:MAINTAINS]->(p)
RETURN m
"""

# --- Blast Radius Analysis ---
# Finds all packages transitively depending on a given package
BLAST_RADIUS = """
MATCH path = (affected:Package)-[:DEPENDS_ON*1..{max_depth}]->(target:Package {{name: $name}})
RETURN affected.name AS affected_name,
       length(path) AS depth,
       [n IN nodes(path) | n.name] AS chain
ORDER BY depth ASC
"""

# --- Circular Dependency Detection ---
# Finds cycles in the dependency graph
FIND_CYCLES = """
MATCH path = (p:Package)-[:DEPENDS_ON*2..{max_depth}]->(p)
WITH p, path, [n IN nodes(path) | n.name] AS cycle_nodes
RETURN DISTINCT cycle_nodes
LIMIT $limit
"""

# --- Centrality Analysis ---
# Direct dependents: packages that directly depend on a given package
DIRECT_DEPENDENTS = """
MATCH (dep:Package)-[:DEPENDS_ON]->(p:Package)
RETURN p.name AS package, count(dep) AS direct_dependents
ORDER BY direct_dependents DESC
LIMIT $limit
"""

# Transitive dependents: all packages that transitively depend on a given package
TRANSITIVE_DEPENDENTS = """
MATCH (dep:Package)-[:DEPENDS_ON*1..{max_depth}]->(p:Package {{name: $name}})
RETURN count(DISTINCT dep) AS transitive_dependents
"""

# --- License Propagation ---
# Find all transitive dependencies and their licenses
LICENSE_CHAIN = """
MATCH path = (root:Package {{name: $name}})-[:DEPENDS_ON*1..{max_depth}]->(dep:Package)
RETURN dep.name AS dep_name,
       dep.license AS license,
       length(path) AS depth,
       [n IN nodes(path) | n.name] AS chain
ORDER BY depth ASC
"""

# --- Dependency Depth ---
# Find the longest dependency chain from a package
DEPENDENCY_TREE = """
MATCH path = (root:Package {{name: $name}})-[:DEPENDS_ON*1..{max_depth}]->(dep:Package)
RETURN dep.name AS dep_name,
       length(path) AS depth,
       [n IN nodes(path) | n.name] AS chain
ORDER BY depth ASC
"""

# --- Package Info ---
GET_PACKAGE = """
MATCH (p:Package {name: $name})
RETURN p.name AS name, p.version AS version, p.license AS license,
       p.description AS description, p.downloads AS downloads
"""

LIST_PACKAGES = """
MATCH (p:Package)
RETURN p.name AS name, p.version AS version, p.license AS license,
       p.description AS description, p.downloads AS downloads
ORDER BY p.name
LIMIT $limit
"""

# --- Vulnerability Queries ---
VULNERABILITIES_FOR_PACKAGE = """
MATCH (v:Vulnerability)-[:AFFECTS]->(p:Package {name: $name})
RETURN v.vuln_id AS vuln_id, v.severity AS severity, v.description AS description
"""

# Find all packages affected by a specific vulnerability through transitive deps
VULN_IMPACT = """
MATCH (v:Vulnerability {{vuln_id: $vuln_id}})-[:AFFECTS]->(target:Package)
OPTIONAL MATCH path = (affected:Package)-[:DEPENDS_ON*1..{max_depth}]->(target)
RETURN target.name AS directly_affected,
       collect(DISTINCT affected.name) AS transitively_affected,
       v.severity AS severity
"""

# --- Search ---
SEARCH_PACKAGES = """
MATCH (p:Package)
WHERE p.name CONTAINS $query
RETURN p.name AS name, p.version AS version, p.license AS license,
       p.description AS description, p.downloads AS downloads
ORDER BY p.downloads DESC
LIMIT $limit
"""


def format_query(template: str, max_depth: int = 10) -> str:
    """Format a query template with the max traversal depth.

    We use Python string formatting for the depth parameter (integer constant)
    while keeping Cypher $params for user-provided values.
    """
    return template.format(max_depth=max_depth)
