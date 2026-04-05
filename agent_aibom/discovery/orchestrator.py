"""Discovery orchestrator — runs all enabled scanners and deduplicates results."""

from __future__ import annotations

from pathlib import Path

from agent_aibom.core.config import ScanConfig, ScannerOverride
from agent_aibom.core.models import AgentIdentity
from agent_aibom.discovery.base import AbstractScanner
from agent_aibom.discovery.claude_scanner import ClaudeCodeScanner
from agent_aibom.discovery.crewai_scanner import CrewAIScanner
from agent_aibom.discovery.langgraph_scanner import LangGraphScanner
from agent_aibom.discovery.autogen_scanner import AutoGenScanner
from agent_aibom.discovery.mcp_scanner import MCPScanner
from agent_aibom.discovery.generic_scanner import GenericScanner

SCANNER_REGISTRY: dict[str, type[AbstractScanner]] = {
    "claude-code": ClaudeCodeScanner,
    "crewai": CrewAIScanner,
    "langgraph": LangGraphScanner,
    "autogen": AutoGenScanner,
    "mcp": MCPScanner,
    "generic": GenericScanner,
}


class DiscoveryOrchestrator:
    """Runs all enabled scanners, deduplicates, and returns a merged agent list."""

    def __init__(self, config: ScanConfig | None = None) -> None:
        self.config = config or ScanConfig()
        self._scanners: list[AbstractScanner] = []
        for framework in self.config.frameworks:
            override = self.config.scanner_overrides.get(framework, ScannerOverride())
            if not override.enabled:
                continue
            scanner_cls = SCANNER_REGISTRY.get(framework)
            if scanner_cls:
                self._scanners.append(scanner_cls(override=override))

    @property
    def scanner_names(self) -> list[str]:
        return [s.name for s in self._scanners]

    def discover(self, path: str | Path) -> list[AgentIdentity]:
        """Run all scanners against the given path and return deduplicated agents."""
        path = Path(path).resolve()
        if not path.is_dir():
            raise ValueError(f"Scan path does not exist: {path}")

        all_agents: list[AgentIdentity] = []
        for scanner in self._scanners:
            try:
                found = scanner.scan(path)
                all_agents.extend(found)
            except Exception as e:
                # Log but don't fail — partial results are better than none
                all_agents.append(AgentIdentity(
                    name=f"_error:{scanner.name}",
                    description=f"Scanner error: {e}",
                    framework=scanner.framework,
                    tags=["error"],
                ))

        return self._deduplicate(all_agents)

    def _deduplicate(self, agents: list[AgentIdentity]) -> list[AgentIdentity]:
        """Remove duplicate agents by (name, source_file) key."""
        seen: dict[str, AgentIdentity] = {}
        for agent in agents:
            key = f"{agent.name}::{agent.source_file or ''}"
            if key in seen:
                existing = seen[key]
                if len(agent.tools) > len(existing.tools):
                    seen[key] = agent
            else:
                seen[key] = agent
        return list(seen.values())
