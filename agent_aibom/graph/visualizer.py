"""Graph visualization — Mermaid, DOT, and D3.js JSON output."""

from __future__ import annotations

import json

import networkx as nx


class GraphVisualizer:
    """Convert NetworkX graphs to various output formats."""

    @staticmethod
    def to_mermaid(graph: nx.DiGraph, title: str = "Agent Graph") -> str:
        """Render graph as Mermaid flowchart markdown."""
        lines = [f"graph TD"]

        # Define node shapes based on kind
        for node, data in graph.nodes(data=True):
            kind = data.get("kind", "unknown")
            safe = _safe_id(node)
            label = node.removeprefix("tool:").removeprefix("resource:").removeprefix("sys:")
            if kind == "agent":
                lines.append(f"    {safe}[{label}]")
            elif kind == "tool":
                ext = " ⚡" if data.get("external") else ""
                lines.append(f"    {safe}[/{label}{ext}/]")
            elif kind == "resource":
                lines.append(f"    {safe}[({label})]")
            elif kind == "system":
                lines.append(f"    {safe}{{{{{label}}}}}")
            else:
                lines.append(f"    {safe}[{label}]")

        # Define edges
        for u, v, data in graph.edges(data=True):
            relation = data.get("relation") or data.get("delegation_type") or ""
            su, sv = _safe_id(u), _safe_id(v)
            if relation:
                lines.append(f"    {su} -->|{relation}| {sv}")
            else:
                lines.append(f"    {su} --> {sv}")

        return "\n".join(lines)

    @staticmethod
    def to_dot(graph: nx.DiGraph, title: str = "Agent Graph") -> str:
        """Render graph as Graphviz DOT format."""
        lines = [f'digraph "{title}" {{']
        lines.append("    rankdir=LR;")
        lines.append('    node [fontname="Helvetica", fontsize=10];')

        # Node definitions with shapes
        for node, data in graph.nodes(data=True):
            kind = data.get("kind", "unknown")
            safe = _safe_id(node)
            label = node.removeprefix("tool:").removeprefix("resource:").removeprefix("sys:")

            shape_map = {
                "agent": "box",
                "tool": "ellipse",
                "resource": "diamond",
                "system": "hexagon",
            }
            shape = shape_map.get(kind, "box")

            color = ""
            if kind == "tool" and data.get("external"):
                color = ', style=filled, fillcolor="#ffcccc"'
            elif kind == "agent":
                color = ', style=filled, fillcolor="#cceeff"'

            lines.append(f'    {safe} [label="{label}", shape={shape}{color}];')

        # Edges
        for u, v, data in graph.edges(data=True):
            relation = data.get("relation") or data.get("delegation_type") or ""
            su, sv = _safe_id(u), _safe_id(v)
            label = f' [label="{relation}"]' if relation else ""
            lines.append(f"    {su} -> {sv}{label};")

        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def to_d3_json(graph: nx.DiGraph) -> str:
        """Render graph as D3.js-compatible JSON (nodes + links)."""
        nodes = []
        node_index: dict[str, int] = {}
        for i, (node, data) in enumerate(graph.nodes(data=True)):
            node_index[node] = i
            nodes.append({
                "id": node,
                "kind": data.get("kind", "unknown"),
                **{k: v for k, v in data.items() if k != "kind"},
            })

        links = []
        for u, v, data in graph.edges(data=True):
            links.append({
                "source": node_index[u],
                "target": node_index[v],
                **data,
            })

        return json.dumps({"nodes": nodes, "links": links}, indent=2, default=str)


def _safe_id(name: str) -> str:
    """Convert a node name to a safe Mermaid/DOT identifier."""
    return (
        name
        .replace(":", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace(" ", "_")
        .replace("<", "")
        .replace(">", "")
    )
