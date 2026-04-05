"""LangGraph scanner — detects StateGraph definitions, nodes, edges, and tools."""

from __future__ import annotations

import re
from pathlib import Path

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    DelegationLink,
    Tool,
    ToolType,
)
from agent_aibom.discovery.base import AbstractScanner


class LangGraphScanner(AbstractScanner):
    """Discovers LangGraph agent graphs."""

    @property
    def name(self) -> str:
        return "LangGraph Scanner"

    @property
    def framework(self) -> AgentFramework:
        return AgentFramework.LANGGRAPH

    def scan(self, path: Path) -> list[AgentIdentity]:
        agents: list[AgentIdentity] = []
        exclude = ["node_modules", ".venv", "venv", "__pycache__", ".git"]
        py_files = self._resolve_files(path, ["**/*.py"], exclude)

        for py_file in py_files:
            agents.extend(self._parse_file(py_file, path))

        return agents

    def _parse_file(self, py_file: Path, root: Path) -> list[AgentIdentity]:
        try:
            content = py_file.read_text()
        except OSError:
            return []

        if "StateGraph" not in content and "langgraph" not in content:
            return []

        agents: list[AgentIdentity] = []

        # Find StateGraph instantiations
        graph_names = re.findall(r'(\w+)\s*=\s*StateGraph\s*\(', content)

        for graph_name in graph_names:
            # Find add_node calls for this graph
            nodes = re.findall(
                rf'{graph_name}\.add_node\s*\(\s*["\']([^"\']+)["\']',
                content,
            )

            # Find add_edge calls
            edges = re.findall(
                rf'{graph_name}\.add_edge\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']',
                content,
            )

            # Find @tool decorated functions in same file
            tools = [
                Tool(name=name, tool_type=ToolType.CUSTOM)
                for name in re.findall(r'@tool\s*(?:\([^)]*\))?\s*\ndef\s+(\w+)', content)
            ]

            # Build delegation links from edges
            delegations = [
                DelegationLink(
                    from_agent=src,
                    to_agent=dst,
                    delegation_type="edge",
                )
                for src, dst in edges
            ]

            agents.append(AgentIdentity(
                name=graph_name,
                description=f"LangGraph with {len(nodes)} nodes",
                framework=AgentFramework.LANGGRAPH,
                source_file=str(py_file.relative_to(root)),
                repository=str(root),
                tools=tools,
                delegations=delegations,
                tags=["langgraph"],
                metadata={"nodes": nodes, "edges": edges},
            ))

        return agents
