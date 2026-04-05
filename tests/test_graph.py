"""Tests for permission and delegation graphs."""

from agent_aibom.graph import DelegationGraph, GraphVisualizer, PermissionGraph


def test_permission_graph_basic(sample_bom):
    pg = PermissionGraph(sample_bom)
    g = pg.to_networkx()
    assert len(g.nodes) > 0
    assert "test-agent" in g.nodes


def test_tools_for_agent(sample_bom):
    pg = PermissionGraph(sample_bom)
    tools = pg.tools_for_agent("test-agent")
    assert "Read" in tools
    assert "WebFetch" in tools


def test_external_action_surface(sample_bom):
    pg = PermissionGraph(sample_bom)
    surface = pg.external_action_surface()
    assert len(surface) >= 1
    assert any(s["tool"] == "WebFetch" for s in surface)


def test_permission_matrix(sample_bom):
    pg = PermissionGraph(sample_bom)
    matrix = pg.permission_matrix()
    assert len(matrix) > 0
    assert any(r["resource"] == "filesystem" for r in matrix)


def test_delegation_graph_basic(sample_bom):
    dg = DelegationGraph(sample_bom)
    g = dg.to_networkx()
    assert "test-agent" in g.nodes
    assert "helper-agent" in g.nodes


def test_delegation_tree(sample_bom):
    dg = DelegationGraph(sample_bom)
    tree = dg.delegation_tree()
    assert "test-agent" in tree
    assert "helper-agent" in tree["test-agent"]


def test_blast_radius(sample_bom):
    dg = DelegationGraph(sample_bom)
    radius = dg.blast_radius("test-agent")
    assert "helper-agent" in radius


def test_root_and_leaf(sample_bom):
    dg = DelegationGraph(sample_bom)
    roots = dg.root_agents()
    leaves = dg.leaf_agents()
    assert "test-agent" in roots
    assert "helper-agent" in leaves


def test_mermaid_output(sample_bom):
    pg = PermissionGraph(sample_bom)
    mermaid = GraphVisualizer.to_mermaid(pg.to_networkx())
    assert "graph TD" in mermaid
    assert "test_agent" in mermaid  # safe_id replaces -


def test_dot_output(sample_bom):
    pg = PermissionGraph(sample_bom)
    dot = GraphVisualizer.to_dot(pg.to_networkx())
    assert "digraph" in dot
    assert "test_agent" in dot


def test_d3_json_output(sample_bom):
    import json
    pg = PermissionGraph(sample_bom)
    d3 = GraphVisualizer.to_d3_json(pg.to_networkx())
    data = json.loads(d3)
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) > 0
