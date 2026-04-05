"""AutoGen scanner — detects AssistantAgent, UserProxyAgent, GroupChat definitions."""

from __future__ import annotations

import re
from pathlib import Path

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    DelegationLink,
)
from agent_aibom.discovery.base import AbstractScanner


class AutoGenScanner(AbstractScanner):
    """Discovers Microsoft AutoGen agent definitions."""

    @property
    def name(self) -> str:
        return "AutoGen Scanner"

    @property
    def framework(self) -> AgentFramework:
        return AgentFramework.AUTOGEN

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

        if "autogen" not in content.lower():
            return []

        agents: list[AgentIdentity] = []

        # Match AssistantAgent, UserProxyAgent, ConversableAgent instantiations
        agent_classes = ("AssistantAgent", "UserProxyAgent", "ConversableAgent")
        pattern = re.compile(
            r'(\w+)\s*=\s*('
            + "|".join(agent_classes)
            + r')\s*\(\s*(?:name\s*=\s*)?["\']([^"\']*)["\']',
        )

        found_names: list[str] = []
        for m in pattern.finditer(content):
            var_name = m.group(1)
            agent_class = m.group(2)
            agent_name = m.group(3)

            found_names.append(var_name)
            agents.append(AgentIdentity(
                name=agent_name or var_name,
                description=f"{agent_class} agent",
                framework=AgentFramework.AUTOGEN,
                source_file=str(py_file.relative_to(root)),
                repository=str(root),
                role=agent_class.replace("Agent", "").lower(),
                tags=["autogen", agent_class.lower()],
            ))

        # Detect GroupChat — links agents together
        group_match = re.search(
            r'GroupChat\s*\(\s*agents\s*=\s*\[([^\]]+)\]', content,
        )
        if group_match and agents:
            members = [m.strip() for m in group_match.group(1).split(",")]
            for i, member in enumerate(members):
                for j, other in enumerate(members):
                    if i != j:
                        agents[0].delegations.append(DelegationLink(
                            from_agent=member.strip(),
                            to_agent=other.strip(),
                            delegation_type="group-chat",
                        ))

        return agents
