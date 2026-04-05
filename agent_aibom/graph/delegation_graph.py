"""Delegation graph — Agent → Agent hierarchy with blast-radius queries."""

from __future__ import annotations

import networkx as nx

from agent_aibom.core.models import AgenticBOM


class DelegationGraph:
    """Directed graph mapping agent delegation relationships."""

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
            for deleg in agent.delegations:
                self.graph.add_node(deleg.to_agent, kind="agent")
                self.graph.add_edge(
                    deleg.from_agent,
                    deleg.to_agent,
                    delegation_type=deleg.delegation_type,
                    max_depth=deleg.max_depth,
                    tools_delegated=deleg.tools_delegated,
                )

        # Also add top-level delegations from the BOM
        for deleg in bom.delegations:
            if deleg.from_agent not in self.graph:
                self.graph.add_node(deleg.from_agent, kind="agent")
            if deleg.to_agent not in self.graph:
                self.graph.add_node(deleg.to_agent, kind="agent")
            self.graph.add_edge(
                deleg.from_agent,
                deleg.to_agent,
                delegation_type=deleg.delegation_type,
                max_depth=deleg.max_depth,
            )

    def root_agents(self) -> list[str]:
        """Agents that delegate but are never delegated to."""
        return [n for n in self.graph.nodes() if self.graph.in_degree(n) == 0]

    def leaf_agents(self) -> list[str]:
        """Agents that are delegated to but never delegate."""
        return [n for n in self.graph.nodes() if self.graph.out_degree(n) == 0]

    def delegation_depth(self, agent: str) -> int:
        """Max depth of delegation chain from this agent."""
        if agent not in self.graph:
            return 0
        try:
            paths = nx.single_source_shortest_path_length(self.graph, agent)
            return max(paths.values()) if paths else 0
        except nx.NetworkXError:
            return 0

    def delegation_tree(self) -> dict[str, list[str]]:
        """Return adjacency list: agent → list of delegates."""
        return {
            node: list(self.graph.successors(node))
            for node in self.graph.nodes()
            if self.graph.out_degree(node) > 0
        }

    def blast_radius(self, agent: str) -> set[str]:
        """All agents reachable from this agent via delegation (transitive closure)."""
        if agent not in self.graph:
            return set()
        return set(nx.descendants(self.graph, agent))

    def can_delegate_to(self, from_agent: str, to_agent: str) -> bool:
        """Check if there's a delegation path from one agent to another."""
        if from_agent not in self.graph or to_agent not in self.graph:
            return False
        return nx.has_path(self.graph, from_agent, to_agent)

    def to_networkx(self) -> nx.DiGraph:
        return self.graph
