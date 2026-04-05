"""Pressure tests — large BOMs, serialization round-trips, graph edge cases."""

import json
import tempfile
from pathlib import Path

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    AgenticBOM,
    BOMMetadata,
    DelegationLink,
    ExportFormat,
    Permission,
    PermissionScope,
    Tool,
    ToolType,
)
from agent_aibom.core.registry import BOMRegistry
from agent_aibom.export import ExportEngine
from agent_aibom.graph import DelegationGraph, GraphVisualizer, PermissionGraph
from agent_aibom.risk.scorer import RiskEngine


def _make_agents(n: int) -> list[AgentIdentity]:
    agents = []
    for i in range(n):
        tools = [
            Tool(name=f"tool-{i}-{j}", tool_type=ToolType.CUSTOM, external=(j % 5 == 0))
            for j in range(10)
        ]
        delegations = []
        if i > 0:
            delegations.append(DelegationLink(
                from_agent=f"agent-{i}", to_agent=f"agent-{i-1}", delegation_type="spawn"
            ))
        agents.append(AgentIdentity(
            name=f"agent-{i}",
            description=f"Test agent number {i}",
            framework=AgentFramework.CLAUDE_CODE,
            tools=tools,
            permissions=[
                Permission(resource="fs", scopes=[PermissionScope.READ, PermissionScope.WRITE]),
                Permission(resource="net", scopes=[PermissionScope.NETWORK]),
            ],
            delegations=delegations,
            owner="test-team" if i % 3 != 0 else None,
        ))
    return agents


def test_large_bom_100_agents():
    """100 agents with 10 tools each — serialization round-trip."""
    agents = _make_agents(100)
    bom = AgenticBOM(
        metadata=BOMMetadata(repository="/pressure-test"),
        agents=agents,
    )
    assert bom.agent_count == 100
    assert bom.tool_count == 1000

    # Serialize and deserialize
    data = bom.model_dump(mode="json")
    json_str = json.dumps(data, default=str)
    restored = AgenticBOM.model_validate(json.loads(json_str))
    assert restored.agent_count == 100


def test_large_bom_risk_scoring():
    agents = _make_agents(50)
    bom = AgenticBOM(agents=agents)
    engine = RiskEngine()
    score, findings = engine.score(bom)
    assert score.overall >= 0.0
    assert score.overall <= 10.0
    assert len(findings) > 0
    # Every agent should have at least missing-trace
    assert len(findings) >= 50


def test_large_bom_registry_round_trip():
    with tempfile.TemporaryDirectory() as d:
        registry = BOMRegistry(d)
        agents = _make_agents(100)
        bom = AgenticBOM(agents=agents)
        path = registry.save(bom)
        assert path.stat().st_size > 0

        loaded = registry.load(bom.metadata.serial_number)
        assert loaded.agent_count == 100


def test_large_bom_export_all_formats():
    with tempfile.TemporaryDirectory() as d:
        agents = _make_agents(50)
        bom = AgenticBOM(agents=agents)
        engine = ExportEngine()
        paths = engine.export_all(
            bom,
            [ExportFormat.JSON, ExportFormat.SARIF, ExportFormat.CSV],
            Path(d),
        )
        assert len(paths) == 3
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 0


def test_permission_graph_100_agents():
    agents = _make_agents(100)
    bom = AgenticBOM(agents=agents)
    pg = PermissionGraph(bom)
    g = pg.to_networkx()
    # 100 agents + 1000 tools + resources
    assert len(g.nodes) > 100
    surface = pg.external_action_surface()
    assert len(surface) > 0


def test_delegation_chain_depth():
    """Linear chain of 20 agents — test blast radius."""
    agents = _make_agents(20)
    bom = AgenticBOM(agents=agents)
    for a in agents:
        bom.delegations.extend(a.delegations)

    dg = DelegationGraph(bom)
    # agent-19 delegates to agent-18, which delegates to agent-17, etc.
    radius = dg.blast_radius("agent-19")
    assert len(radius) == 19  # all agents below it

    depth = dg.delegation_depth("agent-19")
    assert depth == 19


def test_mermaid_large_graph():
    agents = _make_agents(20)
    bom = AgenticBOM(agents=agents)
    pg = PermissionGraph(bom)
    mermaid = GraphVisualizer.to_mermaid(pg.to_networkx())
    assert "graph TD" in mermaid
    assert len(mermaid) > 1000  # should be substantial


def test_dot_large_graph():
    agents = _make_agents(20)
    bom = AgenticBOM(agents=agents)
    dg = DelegationGraph(bom)
    for a in agents:
        bom.delegations.extend(a.delegations)
    dg2 = DelegationGraph(bom)
    dot = GraphVisualizer.to_dot(dg2.to_networkx())
    assert "digraph" in dot
    assert "agent_0" in dot


def test_diff_large_boms():
    with tempfile.TemporaryDirectory() as d:
        registry = BOMRegistry(d)
        bom_a = AgenticBOM(agents=_make_agents(50))
        bom_b = AgenticBOM(agents=_make_agents(55))  # 5 more agents
        registry.save(bom_a)
        registry.save(bom_b)

        result = registry.diff(
            bom_a.metadata.serial_number,
            bom_b.metadata.serial_number,
        )
        assert len(result["added"]) == 5
        assert len(result["removed"]) == 0


def test_sarif_schema_structure():
    """Validate SARIF output has correct structure."""
    with tempfile.TemporaryDirectory() as d:
        agents = _make_agents(10)
        bom = AgenticBOM(agents=agents)
        engine = ExportEngine()
        path = engine.export(bom, ExportFormat.SARIF, Path(d))

        data = json.loads(path.read_text())
        assert data["version"] == "2.1.0"
        assert "$schema" in data
        run = data["runs"][0]
        assert "tool" in run
        assert run["tool"]["driver"]["name"] == "agent-aibom"
        assert "rules" in run["tool"]["driver"]
        assert len(run["results"]) > 0

        # Each result should have required fields
        for result in run["results"]:
            assert "ruleId" in result
            assert "level" in result
            assert "message" in result
            assert result["level"] in ("error", "warning", "note")
