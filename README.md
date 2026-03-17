# 📦 DepGraph — Package Dependency Impact Analyzer

**DepGraph** analyzes package dependency graphs to answer critical supply chain security questions: *"What's the blast radius if this package has a vulnerability? Are there circular dependencies? Which packages are single points of failure? Do I have copyleft license contamination?"* — all powered by graph traversals in [FalkorDB](https://www.falkordb.com/).

[![CI](https://github.com/depgraph/depgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/depgraph/depgraph/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Why a Graph Database?

Package dependencies are inherently a **directed graph** — packages point to the packages they depend on, forming deep, interconnected webs. The questions that matter most about these dependencies are fundamentally graph questions:

- **Blast radius** = variable-length path traversal (who transitively depends on X?)
- **Circular dependencies** = cycle detection in a directed graph
- **Single points of failure** = degree centrality analysis
- **License propagation** = filtered traversal with property aggregation
- **Dependency depth** = shortest/longest path computation

A relational database would require recursive CTEs, multiple self-joins, and significant complexity to answer these questions. FalkorDB answers them in 2-3 lines of Cypher, executing in milliseconds even on large graphs.

---

## Quick Start

### With Docker Compose (recommended)

```bash
# Start FalkorDB + DepGraph API
docker compose up -d

# Seed with sample ecosystem data (80 packages, dependencies, vulnerabilities)
curl -X POST "http://localhost:8000/seed?num_packages=80"

# Analyze blast radius of a package
curl "http://localhost:8000/analysis/blast-radius/lodash" | python -m json.tool

# Find circular dependencies
curl "http://localhost:8000/analysis/cycles" | python -m json.tool

# Find single points of failure
curl "http://localhost:8000/analysis/centrality" | python -m json.tool
```

### With CLI (local development)

```bash
# Install
pip install -e ".[dev]"

# Ensure FalkorDB is running (e.g., docker run -p 6379:6379 falkordb/falkordb)

# Seed the graph
depgraph seed --packages 80

# Analyze
depgraph blast-radius lodash
depgraph cycles
depgraph centrality
depgraph licenses express
depgraph depth express
depgraph stats
```

---

## Example Output

### Blast Radius Analysis

```
$ depgraph blast-radius lodash

Blast Radius for lodash
Total affected packages: 7
Maximum propagation depth: 3

                     Affected Packages
┏━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Package    ┃ Depth ┃ Dependency Chain                      ┃
┡━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ajv        │     1 │ ajv → lodash                          │
│ hapi       │     1 │ hapi → lodash                         │
│ express    │     2 │ express → ajv → lodash                │
│ nanoid     │     2 │ nanoid → hapi → lodash                │
│ debug-util │     3 │ debug-util → nanoid → hapi → lodash   │
│ winston    │     3 │ winston → nanoid → hapi → lodash      │
│ mongoose   │     3 │ mongoose → nanoid → hapi → lodash     │
└────────────┴───────┴───────────────────────────────────────┘
```

### Circular Dependency Detection

```
$ depgraph cycles

Circular Dependencies Found: 1

  Cycle 1: debug-util → nanoid → hapi → debug-util
```

### Single Points of Failure

```
$ depgraph centrality

Most Depended-Upon Packages (Single Points of Failure)

┏━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Rank ┃ Package      ┃ Direct Deps ┃ Transitive Deps ┃
┡━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│    1 │ ramda        │           6 │              11 │
│    2 │ underscore   │           5 │              14 │
│    3 │ date-fns     │           5 │               5 │
│    4 │ moment       │           4 │               4 │
│    5 │ through2     │           4 │               4 │
└──────┴──────────────┴─────────────┴─────────────────┘
```

---

## Graph Schema

```
(:Package {name, version, license, description, downloads})
    -[:DEPENDS_ON {version_constraint, dep_type}]->
(:Package)

(:Vulnerability {vuln_id, severity, description})
    -[:AFFECTS]->
(:Package)

(:Maintainer {name, email})
    -[:MAINTAINS]->
(:Package)
```

```
  ┌──────────────┐    DEPENDS_ON     ┌──────────────┐
  │   Package    │──────────────────>│   Package    │
  │ name,version │                   │ name,version │
  │ license      │<──────────────────│ license      │
  └──────┬───────┘                   └──────────────┘
         │
         │ AFFECTS                MAINTAINS
         │                            │
  ┌──────┴───────┐             ┌──────┴───────┐
  │Vulnerability │             │  Maintainer  │
  │ vuln_id      │             │ name, email  │
  │ severity     │             └──────────────┘
  └──────────────┘
```

---

## Key Graph Queries

### 1. Vulnerability Blast Radius (multi-hop traversal)
```cypher
MATCH path = (affected:Package)-[:DEPENDS_ON*1..10]->(target:Package {name: $name})
RETURN affected.name, length(path) AS depth, [n IN nodes(path) | n.name] AS chain
ORDER BY depth ASC
```

### 2. Circular Dependency Detection (cycle finding)
```cypher
MATCH path = (p:Package)-[:DEPENDS_ON*2..10]->(p)
WITH p, path, [n IN nodes(path) | n.name] AS cycle_nodes
RETURN DISTINCT cycle_nodes
```

### 3. Single Points of Failure (centrality)
```cypher
MATCH (dep:Package)-[:DEPENDS_ON]->(p:Package)
RETURN p.name, count(dep) AS direct_dependents
ORDER BY direct_dependents DESC
```

### 4. License Propagation (filtered traversal)
```cypher
MATCH path = (root:Package {name: $name})-[:DEPENDS_ON*1..10]->(dep:Package)
RETURN dep.name, dep.license, length(path) AS depth, [n IN nodes(path) | n.name] AS chain
```

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                   Client Layer                    │
│  ┌────────────┐              ┌────────────────┐  │
│  │  CLI (Click)│             │ REST API        │  │
│  │  depgraph   │             │ (FastAPI)       │  │
│  │  blast-rad  │             │ /analysis/*     │  │
│  │  cycles     │             │ /packages/*     │  │
│  └──────┬─────┘              └───────┬────────┘  │
│         │                            │            │
│  ┌──────┴────────────────────────────┴────────┐  │
│  │           Analysis Engine                   │  │
│  │  blast_radius · cycles · centrality         │  │
│  │  license_check · dependency_depth           │  │
│  └──────────────────┬─────────────────────────┘  │
│                     │                             │
│  ┌──────────────────┴─────────────────────────┐  │
│  │      Graph Layer (Parameterized Cypher)     │  │
│  │  queries.py · schema.py · engine.py         │  │
│  └──────────────────┬─────────────────────────┘  │
│                     │                             │
│  ┌──────────────────┴─────────────────────────┐  │
│  │      Data Ingestion                         │  │
│  │  seed.py · parsers.py (req.txt, pkg.json)   │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────┘
                       │
              ┌────────┴────────┐
              │    FalkorDB     │
              │  (Graph Store)  │
              └─────────────────┘
```

---

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check with FalkorDB connectivity |
| `GET` | `/stats` | Graph statistics (node/edge counts) |
| `GET` | `/packages` | List all packages |
| `GET` | `/packages/search?q=...` | Search packages by name |
| `GET` | `/packages/{name}` | Get package details |
| `GET` | `/analysis/blast-radius/{name}` | Blast radius analysis |
| `GET` | `/analysis/cycles` | Circular dependency detection |
| `GET` | `/analysis/centrality` | Single points of failure |
| `GET` | `/analysis/licenses/{name}` | License propagation check |
| `GET` | `/analysis/depth/{name}` | Dependency tree depth |
| `POST` | `/seed` | Seed graph with sample data |

Interactive API docs available at `http://localhost:8000/docs` when running.

---

## Configuration

All settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FALKORDB_HOST` | `localhost` | FalkorDB host |
| `FALKORDB_PORT` | `6379` | FalkorDB port |
| `FALKORDB_GRAPH` | `depgraph` | Graph name |
| `FALKORDB_PASSWORD` | `None` | FalkorDB password |
| `FALKORDB_MAX_RETRIES` | `3` | Connection retry attempts |
| `FALKORDB_RETRY_DELAY` | `1.0` | Base delay between retries (seconds) |
| `MAX_TRAVERSAL_DEPTH` | `10` | Maximum depth for graph traversals |
| `LOG_LEVEL` | `INFO` | Logging level |
| `API_HOST` | `0.0.0.0` | API bind host |
| `API_PORT` | `8000` | API bind port |

---

## Development

```bash
# Install dev dependencies
make dev

# Run linter
make lint

# Format code
make format

# Run unit tests
make test

# Run integration tests (requires FalkorDB)
make test-integration

# Run all tests with coverage
make test-all

# Seed the graph
make seed

# Start the API server
make run
```

---

## Data Ingestion

DepGraph can ingest dependencies from:

1. **Built-in seed generator** — creates a realistic 80-package ecosystem with dependencies, vulnerabilities, and maintainers
2. **requirements.txt** — Python dependency files
3. **package.json** — Node.js dependency files

```bash
# Seed with generated data
depgraph seed --packages 80

# Ingest from a real project
depgraph ingest requirements.txt
depgraph ingest package.json
```

---

## Testing

- **Unit tests** (47): Test all analysis logic with mock FalkorDB graph
- **Integration tests** (5): Test full pipeline against a real FalkorDB instance

```bash
# Unit tests only
pytest tests/ -m "not integration"

# Integration tests (needs FalkorDB on localhost:6379)
pytest tests/ -m "integration"

# All tests with coverage
pytest tests/ --cov=depgraph --cov-report=term-missing
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes and add tests
4. Run `make lint && make test-all`
5. Commit with conventional commits (`feat:`, `fix:`, etc.)
6. Open a pull request

---

## License

MIT — see [LICENSE](LICENSE).
