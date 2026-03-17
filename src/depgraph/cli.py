"""Click CLI for DepGraph — command-line interface for dependency analysis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from depgraph.config import load_config
from depgraph.db import GraphDB
from depgraph.graph.engine import AnalysisEngine
from depgraph.graph.schema import clear_graph, ensure_schema
from depgraph.ingest.parsers import ingest_ecosystem, ingest_package_json, ingest_requirements_txt
from depgraph.ingest.seed import generate_ecosystem, save_ecosystem
from depgraph.logging import setup_logging

console = Console()


def _connect() -> tuple[GraphDB, AnalysisEngine]:
    """Establish connection and return (db, engine)."""
    config = load_config()
    setup_logging(config.log_level)
    db = GraphDB(config.db)
    graph = db.connect()
    ensure_schema(graph)
    engine = AnalysisEngine(graph, max_depth=config.max_traversal_depth)
    return db, engine


@click.group()
@click.version_option(version="0.1.0", prog_name="depgraph")
def cli() -> None:
    """DepGraph — Package Dependency Impact Analyzer powered by FalkorDB."""


@cli.command()
@click.option("--packages", "-n", default=80, help="Number of packages to generate.")
@click.option("--clear/--no-clear", default=True, help="Clear existing graph data first.")
@click.option(
    "--save",
    "-s",
    type=click.Path(),
    default="data/sample_ecosystem.json",
    help="Save data to file.",
)
def seed(packages: int, clear: bool, save: str) -> None:
    """Seed the graph with sample ecosystem data."""
    db, _engine = _connect()
    try:
        if clear:
            clear_graph(db.graph)
            ensure_schema(db.graph)
            console.print("[yellow]Cleared existing graph data[/yellow]")

        console.print(f"Generating ecosystem with {packages} packages...")
        data = generate_ecosystem(num_packages=packages)
        save_path = Path(save)
        save_ecosystem(data, save_path)
        console.print(f"Saved ecosystem data to {save_path}")

        counts = ingest_ecosystem(db.graph, data)
        table = Table(title="Seed Results")
        table.add_column("Entity", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for entity, count in counts.items():
            table.add_row(entity.title(), str(count))
        console.print(table)
    finally:
        db.close()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--clear/--no-clear", default=False, help="Clear existing graph data first.")
def ingest(file_path: str, clear: bool) -> None:
    """Ingest dependencies from a requirements.txt or package.json file."""
    db, _engine = _connect()
    try:
        if clear:
            clear_graph(db.graph)
            ensure_schema(db.graph)

        path = Path(file_path)
        if path.name == "package.json":
            counts = ingest_package_json(db.graph, path)
        elif path.name in ("requirements.txt", "requirements-dev.txt") or path.suffix == ".txt":
            counts = ingest_requirements_txt(db.graph, path)
        else:
            console.print(f"[red]Unsupported file format: {path.name}[/red]")
            sys.exit(1)

        console.print(
            f"[green]Ingested {counts['packages']} packages, {counts['dependencies']} dependencies[/green]"
        )
    finally:
        db.close()


@cli.command("blast-radius")
@click.argument("package_name")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON.")
def blast_radius(package_name: str, json_output: bool) -> None:
    """Analyze blast radius — what breaks if this package has an issue?"""
    db, engine = _connect()
    try:
        pkg = engine.get_package(package_name)
        if pkg is None:
            console.print(f"[red]Package '{package_name}' not found[/red]")
            sys.exit(1)

        result = engine.blast_radius(package_name)

        if json_output:
            click.echo(json.dumps(result.model_dump(), indent=2))
            return

        console.print(f"\n[bold]Blast Radius for [cyan]{package_name}[/cyan][/bold]")
        console.print(f"Total affected packages: [bold red]{result.total_affected}[/bold red]")
        console.print(f"Maximum propagation depth: {result.max_depth}\n")

        if result.affected_packages:
            table = Table(title="Affected Packages")
            table.add_column("Package", style="cyan")
            table.add_column("Depth", justify="right")
            table.add_column("Dependency Chain", style="dim")
            for ap in result.affected_packages[:30]:
                table.add_row(ap.name, str(ap.depth), " → ".join(ap.path))
            console.print(table)
        else:
            console.print("[green]No packages depend on this package.[/green]")
    finally:
        db.close()


@cli.command()
@click.option("--limit", "-l", default=20, help="Maximum number of cycles to find.")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON.")
def cycles(limit: int, json_output: bool) -> None:
    """Detect circular dependencies in the graph."""
    db, engine = _connect()
    try:
        result = engine.find_cycles(limit=limit)

        if json_output:
            click.echo(json.dumps(result.model_dump(), indent=2))
            return

        console.print(
            f"\n[bold]Circular Dependencies Found: [red]{result.total_cycles}[/red][/bold]\n"
        )

        if result.cycles:
            for i, cycle in enumerate(result.cycles, 1):
                chain = " → ".join(cycle) + f" → {cycle[0]}"
                console.print(f"  [yellow]Cycle {i}:[/yellow] {chain}")
        else:
            console.print("[green]No circular dependencies found! 🎉[/green]")
    finally:
        db.close()


@cli.command()
@click.option("--limit", "-l", default=20, help="Number of top packages to show.")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON.")
def centrality(limit: int, json_output: bool) -> None:
    """Find single points of failure — most depended-upon packages."""
    db, engine = _connect()
    try:
        result = engine.centrality(limit=limit)

        if json_output:
            click.echo(json.dumps(result.model_dump(), indent=2))
            return

        console.print("\n[bold]Most Depended-Upon Packages (Single Points of Failure)[/bold]\n")

        table = Table()
        table.add_column("Rank", justify="right", style="dim")
        table.add_column("Package", style="cyan")
        table.add_column("Direct Deps", justify="right", style="yellow")
        table.add_column("Transitive Deps", justify="right", style="red")
        for i, pkg in enumerate(result.packages, 1):
            table.add_row(
                str(i), pkg.name, str(pkg.direct_dependents), str(pkg.transitive_dependents)
            )
        console.print(table)
    finally:
        db.close()


@cli.command("licenses")
@click.argument("package_name")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON.")
def license_check(package_name: str, json_output: bool) -> None:
    """Check transitive license compatibility for a package."""
    db, engine = _connect()
    try:
        pkg = engine.get_package(package_name)
        if pkg is None:
            console.print(f"[red]Package '{package_name}' not found[/red]")
            sys.exit(1)

        result = engine.license_check(package_name)

        if json_output:
            click.echo(json.dumps(result.model_dump(), indent=2))
            return

        console.print(f"\n[bold]License Report for [cyan]{package_name}[/cyan][/bold]")
        console.print(f"Dependencies checked: {result.total_dependencies_checked}\n")

        if result.issues:
            table = Table(title="⚠️  License Issues")
            table.add_column("Package", style="cyan")
            table.add_column("License", style="yellow")
            table.add_column("Risk", style="red")
            table.add_column("Via", style="dim")
            for issue in result.issues:
                table.add_row(
                    issue.package,
                    issue.license,
                    issue.risk.value,
                    " → ".join(issue.dependency_chain),
                )
            console.print(table)
        else:
            console.print("[green]No copyleft license issues found! ✅[/green]")
    finally:
        db.close()


@cli.command("depth")
@click.argument("package_name")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON.")
def depth(package_name: str, json_output: bool) -> None:
    """Analyze dependency tree depth and structure."""
    db, engine = _connect()
    try:
        pkg = engine.get_package(package_name)
        if pkg is None:
            console.print(f"[red]Package '{package_name}' not found[/red]")
            sys.exit(1)

        result = engine.dependency_depth(package_name)

        if json_output:
            click.echo(json.dumps(result.model_dump(), indent=2))
            return

        console.print(f"\n[bold]Dependency Tree for [cyan]{package_name}[/cyan][/bold]")
        console.print(f"Total dependencies: {result.dependency_count}")
        console.print(f"Maximum depth: {result.max_depth}\n")

        if result.tree:
            tree = Tree(f"📦 {package_name}")
            _add_tree_nodes(tree, result.tree.get(package_name, {}))
            console.print(tree)
    finally:
        db.close()


@cli.command()
def stats() -> None:
    """Show graph statistics."""
    db, engine = _connect()
    try:
        result = engine.graph_stats()
        table = Table(title="Graph Statistics")
        table.add_column("Entity", style="cyan")
        table.add_column("Count", style="green", justify="right")
        table.add_row("Packages", str(result.packages))
        table.add_row("Dependencies", str(result.dependencies))
        table.add_row("Vulnerabilities", str(result.vulnerabilities))
        table.add_row("Maintainers", str(result.maintainers))
        console.print(table)
    finally:
        db.close()


@cli.command("serve")
@click.option("--host", default="0.0.0.0", help="API host.")
@click.option("--port", default=8000, help="API port.")
def serve(host: str, port: int) -> None:
    """Start the DepGraph REST API server."""
    import uvicorn

    uvicorn.run("depgraph.api:app", host=host, port=port, reload=False)


# --- Registry Ingestion ---


@cli.command("ingest-npm")
@click.argument("package_name")
@click.option("--depth", "-d", default=3, help="Maximum dependency resolution depth.")
@click.option("--dev-deps", is_flag=True, help="Include devDependencies.")
@click.option("--clear/--no-clear", default=False, help="Clear graph first.")
def ingest_npm_cmd(package_name: str, depth: int, dev_deps: bool, clear: bool) -> None:
    """Ingest a real npm package and its transitive dependencies."""
    from depgraph.ingest.registry import ingest_npm_package

    db, _engine = _connect()
    try:
        if clear:
            clear_graph(db.graph)
            ensure_schema(db.graph)
        console.print(f"Fetching [cyan]{package_name}[/cyan] from npm registry (depth={depth})...")
        counts = ingest_npm_package(db.graph, package_name, max_depth=depth, include_dev=dev_deps)
        table = Table(title="npm Ingestion Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for key, val in counts.items():
            table.add_row(key.title(), str(val))
        console.print(table)
    finally:
        db.close()


@cli.command("ingest-pypi")
@click.argument("package_name")
@click.option("--depth", "-d", default=3, help="Maximum dependency resolution depth.")
@click.option("--extras", is_flag=True, help="Include optional/extra dependencies.")
@click.option("--clear/--no-clear", default=False, help="Clear graph first.")
def ingest_pypi_cmd(package_name: str, depth: int, extras: bool, clear: bool) -> None:
    """Ingest a real PyPI package and its transitive dependencies."""
    from depgraph.ingest.registry import ingest_pypi_package

    db, _engine = _connect()
    try:
        if clear:
            clear_graph(db.graph)
            ensure_schema(db.graph)
        console.print(f"Fetching [cyan]{package_name}[/cyan] from PyPI (depth={depth})...")
        counts = ingest_pypi_package(db.graph, package_name, max_depth=depth, include_extras=extras)
        table = Table(title="PyPI Ingestion Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for key, val in counts.items():
            table.add_row(key.title(), str(val))
        console.print(table)
    finally:
        db.close()


# --- SBOM ---


@cli.command("export-sbom")
@click.option(
    "--format",
    "sbom_format",
    type=click.Choice(["cyclonedx", "spdx"]),
    default="cyclonedx",
    help="SBOM format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout).")
def export_sbom_cmd(sbom_format: str, output: str | None) -> None:
    """Export the dependency graph as an SBOM."""
    from depgraph.sbom import export_cyclonedx, export_spdx

    db, _engine = _connect()
    try:
        data = export_cyclonedx(db.graph) if sbom_format == "cyclonedx" else export_spdx(db.graph)

        result = json.dumps(data, indent=2)
        if output:
            Path(output).write_text(result)
            console.print(f"[green]SBOM exported to {output}[/green]")
        else:
            click.echo(result)
    finally:
        db.close()


@cli.command("import-sbom")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--clear/--no-clear", default=False, help="Clear graph first.")
def import_sbom_cmd(file_path: str, clear: bool) -> None:
    """Import a CycloneDX or SPDX SBOM into the graph."""
    from depgraph.sbom import import_sbom

    db, _engine = _connect()
    try:
        if clear:
            clear_graph(db.graph)
            ensure_schema(db.graph)

        with open(file_path) as f:
            data = json.load(f)

        counts = import_sbom(db.graph, data)
        console.print(
            f"[green]Imported {counts['packages']} packages, {counts['dependencies']} dependencies[/green]"
        )
    finally:
        db.close()


# --- Vulnerability Scanning ---


@cli.command("scan-vulns")
@click.option(
    "--package", "-p", "package_name", help="Scan a single package (scans all if omitted)."
)
@click.option(
    "--ecosystem",
    "-e",
    type=click.Choice(["npm", "PyPI"]),
    default="npm",
    help="Package ecosystem.",
)
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON.")
def scan_vulns_cmd(package_name: str | None, ecosystem: str, json_output: bool) -> None:
    """Scan packages against the OSV.dev vulnerability database."""
    from depgraph.ingest.osv import scan_and_ingest_package, scan_graph_packages

    db, engine = _connect()
    try:
        if package_name:
            pkg = engine.get_package(package_name)
            if pkg is None:
                console.print(f"[red]Package '{package_name}' not found[/red]")
                sys.exit(1)
            result = scan_and_ingest_package(db.graph, package_name, pkg.version, ecosystem)
        else:
            result = scan_graph_packages(db.graph)

        if json_output:
            click.echo(json.dumps(result, indent=2))
            return

        console.print("\n[bold]Vulnerability Scan Results[/bold]")
        console.print(f"Packages scanned: {result.get('packages_scanned', 0)}")
        console.print(
            f"Vulnerabilities found: [bold red]{result.get('vulnerabilities_found', 0)}[/bold red]"
        )

        vulns = result.get("vulnerabilities", [])
        if vulns:
            table = Table(title="Vulnerabilities")
            table.add_column("ID", style="cyan")
            table.add_column("Severity", style="red")
            table.add_column("Package", style="yellow")
            table.add_column("Summary")
            for v in vulns[:30]:
                table.add_row(
                    v["id"],
                    v.get("severity", "?"),
                    v.get("package", "?"),
                    v.get("summary", "")[:60],
                )
            console.print(table)
        else:
            console.print("[green]No vulnerabilities found! ✅[/green]")
    finally:
        db.close()


def _add_tree_nodes(tree: Tree, subtree: dict) -> None:
    """Recursively add nodes to a Rich tree from a nested dict."""
    for name, children in subtree.items():
        branch = tree.add(f"📦 {name}")
        if isinstance(children, dict) and children:
            _add_tree_nodes(branch, children)
