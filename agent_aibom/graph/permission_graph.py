"""Permission graph — Agent → Tool → System edges with queryable API."""

from __future__ import annotations

import networkx as nx

from agent_aibom.core.models import AgenticBOM, AgentIdentity, Tool


class PermissionGraph:
    """Directed graph mapping agents to their tools and the systems they access."""

    def __init__(self, bom: AgenticBOM) -> None:
        self.graph = nx.DiGraph()
        self._build(bom)

    def _build(self, bom: AgenticBOM) -> None:
        for agent in bom.agents:
            self.graph.add_node(
                agent.name,
                kind="agent",
                framework=agent.framework.value,
                source_file=agent.source_file or "",
            )
            for tool in agent.tools:
                tool_id = f"tool:{tool.name}"
                self.graph.add_node(
                    tool_id,
                    kind="tool",
                    tool_type=tool.tool_type.value,
                    external=tool.external,
                )
                self.graph.add_edge(agent.name, tool_id, relation="uses")

                # If tool has an endpoint, add a system node
                if tool.endpoint:
                    sys_id = f"sys:{tool.endpoint}"
                    self.graph.add_node(sys_id, kind="system")
                    self.graph.add_edge(tool_id, sys_id, relation="accesses")

            for perm in agent.permissions:
                res_id = f"resource:{perm.resource}"
                self.graph.add_node(
                    res_id,
                    kind="resource",
                    scopes=[s.value for s in perm.scopes],
                )
                self.graph.add_edge(
                    agent.name,
                    res_id,
                    relation="has_permission",
                    scopes=[s.value for s in perm.scopes],
                )

    def tools_for_agent(self, agent_name: str) -> list[str]:
        """Return tool names accessible by an agent."""
        return [
            n.removeprefix("tool:")
            for n in self.graph.successors(agent_name)
            if self.graph.nodes[n].get("kind") == "tool"
        ]

    def agents_with_access_to(self, resource: str) -> list[str]:
        """Return agents that have permissions on a resource."""
        target = f"resource:{resource}"
        if target not in self.graph:
            return []
        return [
            n for n in self.graph.predecessors(target)
            if self.graph.nodes[n].get("kind") == "agent"
        ]

    def external_action_surface(self) -> list[dict[str, str]]:
        """Return all agent→external-tool pairs."""
        results: list[dict[str, str]] = []
        for node, data in self.graph.nodes(data=True):
            if data.get("kind") == "tool" and data.get("external"):
                agents = [
                    n for n in self.graph.predecessors(node)
                    if self.graph.nodes[n].get("kind") == "agent"
                ]
                for agent in agents:
                    results.append({
                        "agent": agent,
                        "tool": node.removeprefix("tool:"),
                        "tool_type": data.get("tool_type", ""),
                    })
        return results

    def permission_matrix(self) -> list[dict[str, object]]:
        """Return a flat list of agent→resource→scopes triples."""
        rows: list[dict[str, object]] = []
        for u, v, data in self.graph.edges(data=True):
            if data.get("relation") == "has_permission":
                rows.append({
                    "agent": u,
                    "resource": v.removeprefix("resource:"),
                    "scopes": data.get("scopes", []),
                })
        return rows

    def to_networkx(self) -> nx.DiGraph:
        return self.graph
