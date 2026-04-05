"""Generic agent scanner — heuristic detection of agent-like patterns."""

from __future__ import annotations

import re
from pathlib import Path

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    ModelBinding,
)
from agent_aibom.discovery.base import AbstractScanner

# Patterns that indicate an agent-like construct
AGENT_PATTERNS = [
    (r'openai\.ChatCompletion\.create', "openai", "OpenAI ChatCompletion agent"),
    (r'anthropic\.Anthropic\(\)', "anthropic", "Anthropic SDK agent"),
    (r'AsyncAnthropic\(\)', "anthropic", "Anthropic async agent"),
    (r'ChatOpenAI\(', "langchain", "LangChain ChatOpenAI agent"),
    (r'ChatAnthropic\(', "langchain", "LangChain ChatAnthropic agent"),
    (r'AgentExecutor\(', "langchain", "LangChain AgentExecutor"),
    (r'initialize_agent\(', "langchain", "LangChain agent"),
]


class GenericScanner(AbstractScanner):
    """Heuristic detection of agent-like patterns in Python files."""

    @property
    def name(self) -> str:
        return "Generic Scanner"

    @property
    def framework(self) -> AgentFramework:
        return AgentFramework.CUSTOM

    def scan(self, path: Path) -> list[AgentIdentity]:
        agents: list[AgentIdentity] = []
        exclude = [
            "node_modules", ".venv", "venv", "__pycache__", ".git",
            "test_", "_test.py", "conftest",
        ]
        py_files = self._resolve_files(path, ["**/*.py"], exclude)

        for py_file in py_files:
            found = self._parse_file(py_file, path)
            if found:
                agents.extend(found)

        return agents

    def _parse_file(self, py_file: Path, root: Path) -> list[AgentIdentity]:
        try:
            content = py_file.read_text()
        except OSError:
            return []

        agents: list[AgentIdentity] = []
        seen_providers: set[str] = set()

        for pattern, provider, desc in AGENT_PATTERNS:
            if re.search(pattern, content) and provider not in seen_providers:
                seen_providers.add(provider)

                models = []
                if provider == "openai":
                    models.append(ModelBinding(provider="openai", model_id="unknown"))
                elif provider == "anthropic":
                    models.append(ModelBinding(provider="anthropic", model_id="unknown"))

                agents.append(AgentIdentity(
                    name=f"generic:{py_file.stem}:{provider}",
                    description=desc,
                    framework=AgentFramework.CUSTOM,
                    source_file=str(py_file.relative_to(root)),
                    repository=str(root),
                    models=models,
                    tags=["generic", provider],
                ))

        return agents
