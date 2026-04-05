"""CrewAI agent scanner — parses crewai.yaml, agents.yaml, Python agent definitions."""

from __future__ import annotations

import re
from pathlib import Path

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    Tool,
    ToolType,
)
from agent_aibom.discovery.base import AbstractScanner


class CrewAIScanner(AbstractScanner):
    """Discovers CrewAI agent definitions."""

    @property
    def name(self) -> str:
        return "CrewAI Scanner"

    @property
    def framework(self) -> AgentFramework:
        return AgentFramework.CREWAI

    def scan(self, path: Path) -> list[AgentIdentity]:
        agents: list[AgentIdentity] = []
        exclude = ["node_modules", ".venv", "venv", "__pycache__", ".git"]

        # Scan YAML config files
        yaml_files = self._resolve_files(
            path, ["**/agents.yaml", "**/crewai.yaml", "**/crew.yaml"], exclude,
        )
        for yaml_file in yaml_files:
            agents.extend(self._parse_yaml(yaml_file, path))

        # Scan Python files for Agent() instantiations
        py_files = self._resolve_files(path, ["**/*.py"], exclude)
        for py_file in py_files:
            agents.extend(self._parse_python(py_file, path))

        return agents

    def _parse_yaml(self, yaml_file: Path, root: Path) -> list[AgentIdentity]:
        try:
            import yaml
            data = yaml.safe_load(yaml_file.read_text())
        except Exception:
            return []

        if not isinstance(data, dict):
            return []

        agents: list[AgentIdentity] = []

        # Handle agents.yaml format: top-level keys are agent names
        # or nested under "agents" key
        agent_defs = data.get("agents", data)
        if not isinstance(agent_defs, dict):
            return []

        for agent_name, config in agent_defs.items():
            if not isinstance(config, dict):
                continue
            if not any(k in config for k in ("role", "goal", "backstory", "tools")):
                continue

            tools = []
            for tool_name in config.get("tools", []):
                tools.append(Tool(
                    name=str(tool_name),
                    tool_type=ToolType.CUSTOM,
                ))

            agents.append(AgentIdentity(
                name=agent_name,
                description=config.get("goal", ""),
                framework=AgentFramework.CREWAI,
                source_file=str(yaml_file.relative_to(root)),
                repository=str(root),
                role=config.get("role", ""),
                goal=config.get("goal", ""),
                backstory=config.get("backstory", ""),
                tools=tools,
                tags=["crewai"],
            ))

        return agents

    def _parse_python(self, py_file: Path, root: Path) -> list[AgentIdentity]:
        try:
            content = py_file.read_text()
        except OSError:
            return []

        if "crewai" not in content.lower() and "Agent(" not in content:
            return []

        # Check for crewai import
        if not re.search(r'from\s+crewai\s+import|import\s+crewai', content):
            return []

        agents: list[AgentIdentity] = []

        # Match Agent(...) instantiations with keyword args
        pattern = re.compile(
            r'Agent\s*\(\s*'
            r'(?:.*?role\s*=\s*["\']([^"\']*)["\'])?'
            r'(?:.*?goal\s*=\s*["\']([^"\']*)["\'])?',
            re.DOTALL,
        )

        for m in pattern.finditer(content):
            role = m.group(1) or "unknown"
            goal = m.group(2) or ""
            agents.append(AgentIdentity(
                name=role.lower().replace(" ", "-"),
                description=goal,
                framework=AgentFramework.CREWAI,
                source_file=str(py_file.relative_to(root)),
                repository=str(root),
                role=role,
                goal=goal,
                tags=["crewai"],
            ))

        return agents
