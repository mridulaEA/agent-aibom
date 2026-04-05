"""CLI for Agent AIBOM — scan, risk, export, graph, diff."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from agent_aibom import __version__
from agent_aibom.core.config import RiskConfig, ScanConfig, Settings
from agent_aibom.core.models import AgenticBOM, BOMMetadata, ExportFormat, RiskSeverity
from agent_aibom.core.registry import BOMRegistry
from agent_aibom.discovery import DiscoveryOrchestrator
from agent_aibom.graph import DelegationGraph, GraphVisualizer, PermissionGraph
from agent_aibom.risk.scorer import RiskEngine

app = typer.Typer(
    name="agent-aibom",
    help="Agentic AI Bill of Materials — discover, graph, score, and export agent inventories.",
    no_args_is_help=True,
)
console = Console()
VERBOSE = False

# --- Shared helpers ---


def _log(msg: str) -> None:
    """Print only in verbose mode."""
    if VERBOSE:
        console.print(f"[dim]{msg}[/dim]")


def _resolve_store_dir(store_dir: str | None, settings: Settings | None = None) -> Path:
    if store_dir:
        return Path(store_dir)
    if settings:
        return settings.resolve_store_dir()
    return Settings().resolve_store_dir()


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    global VERBOSE
    VERBOSE = verbose


def _discover(path: str, config: ScanConfig | None = None) -> AgenticBOM:
    """Run discovery and return a BOM."""
    scan_path = Path(path).resolve()
    if not scan_path.is_dir():
        console.print(f"[red]Error: {path} is not a directory[/red]")
        raise typer.Exit(1)

    cfg = config or ScanConfig()
    orch = DiscoveryOrchestrator(cfg)
    _log(f"Scanners: {orch.scanner_names}")
    _log(f"Frameworks: {cfg.frameworks}")
    _log(f"Exclude: {cfg.exclude_patterns}")

    with console.status("[bold blue]Scanning for agents..."):
        agents = orch.discover(scan_path)

    _log(f"Discovered {len(agents)} agents")

    bom = AgenticBOM(
        metadata=BOMMetadata(
            repository=str(scan_path),
        ),
        agents=agents,
    )

    # Collect delegations from agents into top-level
    for agent in agents:
        bom.delegations.extend(agent.delegations)

    return bom


# --- Commands ---


@app.command()
def version():
    """Show version."""
    console.print(f"agent-aibom {__version__}")


@app.command()
def scan(
    path: str = typer.Argument(".", help="Path to scan for agents"),
    store_dir: str | None = typer.Option(None, "--store-dir", envvar="AGENT_AIBOM_STORE_DIR"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
):
    """Discover agents and generate a BOM."""
    settings = Settings.from_file(config) if config else Settings()
    bom = _discover(path, settings.scan)
    registry = BOMRegistry(_resolve_store_dir(store_dir))
    saved = registry.save(bom)

    if quiet:
        console.print(bom.metadata.serial_number)
        return

    # Summary table
    table = Table(title=f"Agent AIBOM — {len(bom.agents)} agents discovered")
    table.add_column("Name", style="cyan", max_width=45)
    table.add_column("Framework", style="green")
    table.add_column("Tools", justify="right")
    table.add_column("Delegations", justify="right")
    table.add_column("Source", style="dim", max_width=50)

    for agent in sorted(bom.agents, key=lambda a: a.name):
        if agent.name.startswith("_error:"):
            continue
        table.add_row(
            agent.name,
            agent.framework.value,
            str(len(agent.tools)),
            str(len(agent.delegations)),
            agent.source_file or "",
        )

    console.print(table)
    console.print(f"\n[dim]BOM saved: {saved}[/dim]")
    console.print(f"[dim]Serial: {bom.metadata.serial_number}[/dim]")


@app.command()
def risk(
    path: str = typer.Argument(".", help="Path to scan and assess risk"),
    store_dir: str | None = typer.Option(None, "--store-dir", envvar="AGENT_AIBOM_STORE_DIR"),
    config: str | None = typer.Option(None, "--config", "-c"),
):
    """Run risk assessment on discovered agents."""
    settings = Settings.from_file(config) if config else Settings()
    bom = _discover(path, settings.scan)

    with console.status("[bold yellow]Running risk assessment..."):
        engine = RiskEngine(settings.risk)
        score, findings = engine.score(bom)

    bom.risk_findings = findings
    bom.risk_score = score

    registry = BOMRegistry(_resolve_store_dir(store_dir))
    registry.save(bom)

    # Risk summary panel
    grade_color = {"A": "green", "B": "blue", "C": "yellow", "D": "red", "F": "red bold"}.get(
        score.grade, "white"
    )
    console.print(Panel(
        f"[{grade_color}]Grade: {score.grade}  Score: {score.overall}/10.0[/{grade_color}]"
        f"\n\nAgents: {len(bom.agents)}  |  Findings: {len(findings)}"
        f"\nCritical: {score.findings_count.get(RiskSeverity.CRITICAL, 0)}"
        f"  High: {score.findings_count.get(RiskSeverity.HIGH, 0)}"
        f"  Medium: {score.findings_count.get(RiskSeverity.MEDIUM, 0)}"
        f"  Low: {score.findings_count.get(RiskSeverity.LOW, 0)}",
        title="Risk Assessment",
    ))

    # Findings table
    if findings:
        table = Table(title="Findings")
        table.add_column("Severity", style="bold")
        table.add_column("Agent", style="cyan", max_width=35)
        table.add_column("Category")
        table.add_column("Title", max_width=50)
        table.add_column("Source", style="dim")
        table.add_column("Conf", justify="right")

        sev_style = {
            RiskSeverity.CRITICAL: "red bold",
            RiskSeverity.HIGH: "red",
            RiskSeverity.MEDIUM: "yellow",
            RiskSeverity.LOW: "dim",
            RiskSeverity.INFO: "dim",
        }

        for f in sorted(findings, key=lambda x: list(RiskSeverity).index(x.severity)):
            table.add_row(
                f"[{sev_style.get(f.severity, '')}]{f.severity.value}[/]",
                f.agent_name,
                f.category.value,
                f.title,
                f.source.value,
                f"{f.confidence:.0%}",
            )

        console.print(table)


@app.command(name="export")
def export_cmd(
    path: str = typer.Argument(".", help="Path to scan"),
    format: str = typer.Option("json", "--format", "-f", help="Formats: json,sarif,csv"),
    output_dir: str = typer.Option("./aibom-output", "--output-dir", "-d"),
    store_dir: str | None = typer.Option(None, "--store-dir", envvar="AGENT_AIBOM_STORE_DIR"),
    config: str | None = typer.Option(None, "--config", "-c"),
):
    """Export BOM in specified formats."""
    from agent_aibom.export import ExportEngine

    settings = Settings.from_file(config) if config else Settings()
    bom = _discover(path, settings.scan)

    formats = [f.strip() for f in format.split(",")]
    fmt_map = {f.value: f for f in ExportFormat}
    export_formats: list[ExportFormat] = []
    for f in formats:
        if f not in fmt_map:
            console.print(f"[red]Unknown format: {f}. Valid: {list(fmt_map.keys())}[/red]")
            raise typer.Exit(1)
        export_formats.append(fmt_map[f])

    # Check if SARIF is requested — tell user we're running risk
    needs_risk = ExportFormat.SARIF in export_formats
    if needs_risk:
        console.print("[yellow]SARIF export requires risk assessment — running risk engine...[/yellow]")

    engine = ExportEngine(settings.risk)
    out = Path(output_dir)

    with console.status("[bold blue]Exporting..."):
        paths = engine.export_all(bom, export_formats, out)

    # Also persist BOM
    registry = BOMRegistry(_resolve_store_dir(store_dir))
    registry.save(bom)

    for p in paths:
        console.print(f"[green]✓[/green] {p}")


@app.command()
def graph(
    path: str = typer.Argument(".", help="Path to scan"),
    type: str = typer.Option("permissions", "--type", "-t", help="permissions or delegations"),
    output: str = typer.Option("mermaid", "--output", "-o", help="mermaid, dot, or d3"),
    config: str | None = typer.Option(None, "--config", "-c"),
):
    """Generate agent graph visualization."""
    bom = _discover(path)

    if type == "permissions":
        pg = PermissionGraph(bom)
        nx_graph = pg.to_networkx()
        title = "Permission Graph"
    elif type == "delegations":
        dg = DelegationGraph(bom)
        nx_graph = dg.to_networkx()
        title = "Delegation Graph"
    else:
        console.print(f"[red]Unknown graph type: {type}. Use 'permissions' or 'delegations'.[/red]")
        raise typer.Exit(1)

    viz = GraphVisualizer()
    if output == "mermaid":
        result = viz.to_mermaid(nx_graph, title)
    elif output == "dot":
        result = viz.to_dot(nx_graph, title)
    elif output == "d3":
        result = viz.to_d3_json(nx_graph)
    else:
        console.print(f"[red]Unknown output: {output}. Use 'mermaid', 'dot', or 'd3'.[/red]")
        raise typer.Exit(1)

    console.print(result)


@app.command()
def diff(
    bom_a: str = typer.Argument(help="First BOM (serial number or file path)"),
    bom_b: str = typer.Argument(help="Second BOM (serial number or file path)"),
    store_dir: str | None = typer.Option(None, "--store-dir", envvar="AGENT_AIBOM_STORE_DIR"),
):
    """Compare two BOMs and show differences."""
    registry = BOMRegistry(_resolve_store_dir(store_dir))

    try:
        a = registry.load(bom_a)
        b = registry.load(bom_b)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    agents_a = {ag.name for ag in a.agents}
    agents_b = {ag.name for ag in b.agents}

    added = sorted(agents_b - agents_a)
    removed = sorted(agents_a - agents_b)
    common = agents_a & agents_b

    changed: list[tuple[str, list[str]]] = []
    for name in sorted(common):
        aa = a.get_agent(name)
        bb = b.get_agent(name)
        if aa and bb:
            diffs: list[str] = []
            if set(aa.tool_names) != set(bb.tool_names):
                diffs.append(f"tools: {len(aa.tools)}→{len(bb.tools)}")
            if len(aa.permissions) != len(bb.permissions):
                diffs.append(f"perms: {len(aa.permissions)}→{len(bb.permissions)}")
            if len(aa.delegations) != len(bb.delegations):
                diffs.append(f"delegs: {len(aa.delegations)}→{len(bb.delegations)}")
            if diffs:
                changed.append((name, diffs))

    console.print(Panel(
        f"+{len(added)} added  -{len(removed)} removed  ~{len(changed)} changed",
        title="BOM Diff",
    ))

    if added:
        console.print("\n[green]Added agents:[/green]")
        for name in added:
            console.print(f"  + {name}")
    if removed:
        console.print("\n[red]Removed agents:[/red]")
        for name in removed:
            console.print(f"  - {name}")
    if changed:
        console.print("\n[yellow]Changed agents:[/yellow]")
        for name, diffs in changed:
            console.print(f"  ~ {name}: {', '.join(diffs)}")


@app.command()
def dashboard(
    path: str = typer.Argument(".", help="Path to scan"),
    output: str = typer.Option("./aibom-dashboard.html", "--output", "-o", help="Output HTML file"),
    store_dir: str | None = typer.Option(None, "--store-dir", envvar="AGENT_AIBOM_STORE_DIR"),
    config: str | None = typer.Option(None, "--config", "-c"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open in browser"),
):
    """Generate interactive HTML dashboard."""
    from agent_aibom.dashboard import generate_dashboard

    settings = Settings.from_file(config) if config else Settings()
    bom = _discover(path, settings.scan)

    # Run risk for the dashboard
    with console.status("[bold yellow]Running risk assessment..."):
        engine = RiskEngine(settings.risk)
        score, findings = engine.score(bom)
    bom.risk_findings = findings
    bom.risk_score = score
    for a in bom.agents:
        bom.delegations.extend(a.delegations)

    # Persist
    registry = BOMRegistry(_resolve_store_dir(store_dir, settings))
    registry.save(bom)

    # Generate dashboard
    out = Path(output)
    with console.status("[bold blue]Generating dashboard..."):
        generate_dashboard(bom, out)

    console.print(f"[green]Dashboard generated:[/green] {out.resolve()}")

    if not no_open:
        import webbrowser
        webbrowser.open(f"file://{out.resolve()}")


if __name__ == "__main__":
    app()
