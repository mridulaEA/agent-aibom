"""Claude Code agent scanner — parses .claude/agents/*.md, skills, MCP configs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import frontmatter

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    DelegationLink,
    ModelBinding,
    Permission,
    PermissionScope,
    Tool,
    ToolType,
)
from agent_aibom.discovery.base import AbstractScanner


class ClaudeCodeScanner(AbstractScanner):
    """Discovers Claude Code agents, skills, and MCP tools."""

    @property
    def name(self) -> str:
        return "Claude Code Scanner"

    @property
    def framework(self) -> AgentFramework:
        return AgentFramework.CLAUDE_CODE

    def scan(self, path: Path) -> list[AgentIdentity]:
        agents: list[AgentIdentity] = []
        agents.extend(self._scan_agents(path))
        agents.extend(self._scan_skills(path))
        self._enrich_with_mcp_tools(path, agents)
        return agents

    # --- Agent .md files ---

    def _scan_agents(self, root: Path) -> list[AgentIdentity]:
        default_globs = [".claude/agents/*.md"]
        exclude = ["node_modules", ".venv", "venv", "__pycache__", ".git"]
        md_files = self._resolve_files(root, default_globs, exclude)

        if not md_files:
            return []

        agents: list[AgentIdentity] = []
        for md_file in md_files:
            agent = self._parse_agent_file(md_file, root)
            if agent:
                agents.append(agent)
        return agents

    def _parse_agent_file(self, path: Path, root: Path) -> AgentIdentity | None:
        try:
            post = frontmatter.load(str(path))
        except Exception:
            return None

        fm = post.metadata
        body = post.content

        agent_name = fm.get("name", path.stem)
        description = fm.get("description", "")

        # Parse tools from frontmatter
        tools = self._parse_tools_from_frontmatter(fm.get("tools", []))

        # Parse model binding
        models = []
        model_val = fm.get("model", "")
        if model_val:
            models.append(ModelBinding(
                provider="anthropic",
                model_id=str(model_val),
            ))

        # Parse permissions from tool list
        permissions = self._infer_permissions(fm.get("tools", []))

        # Parse delegations from body text
        delegations = self._parse_delegations(agent_name, body)

        # Detect disallowed tools (governance signal)
        disallowed = fm.get("disallowedTools", [])

        return AgentIdentity(
            name=agent_name,
            description=description,
            framework=AgentFramework.CLAUDE_CODE,
            source_file=str(path.relative_to(root)),
            repository=str(root),
            role=description,
            tools=tools,
            permissions=permissions,
            models=models,
            delegations=delegations,
            tags=self._extract_tags(fm, disallowed),
            metadata={
                "permission_mode": fm.get("permissionMode", "default"),
                "max_turns": fm.get("maxTurns"),
                "disallowed_tools": disallowed,
            },
        )

    def _parse_tools_from_frontmatter(self, tool_names: list) -> list[Tool]:
        tools: list[Tool] = []
        for name in tool_names:
            name = str(name)
            tool_type = self._classify_tool(name)
            external = name.startswith("mcp__") or name in (
                "WebFetch", "WebSearch", "Bash",
            )
            tools.append(Tool(
                name=name,
                tool_type=tool_type,
                external=external,
            ))
        return tools

    def _classify_tool(self, name: str) -> ToolType:
        if name.startswith("mcp__"):
            return ToolType.MCP
        if name in ("Bash",):
            return ToolType.CLI
        if name in ("Read", "Write", "Edit", "Glob", "Grep"):
            return ToolType.FILE_SYSTEM
        if name in ("WebFetch", "WebSearch"):
            return ToolType.BROWSER
        if name in ("Agent", "TeamCreate", "TeamDelete", "SendMessage",
                     "TaskCreate", "TaskGet", "TaskUpdate", "TaskList"):
            return ToolType.CUSTOM
        return ToolType.CUSTOM

    def _infer_permissions(self, tool_names: list) -> list[Permission]:
        permissions: list[Permission] = []
        str_names = [str(t) for t in tool_names]

        if any(n in str_names for n in ("Read", "Glob", "Grep")):
            permissions.append(Permission(
                resource="filesystem",
                scopes=[PermissionScope.READ],
            ))
        if any(n in str_names for n in ("Write", "Edit")):
            permissions.append(Permission(
                resource="filesystem",
                scopes=[PermissionScope.WRITE],
            ))
        if "Bash" in str_names:
            permissions.append(Permission(
                resource="shell",
                scopes=[PermissionScope.EXECUTE],
            ))
        if any(n in str_names for n in ("WebFetch", "WebSearch")):
            permissions.append(Permission(
                resource="network",
                scopes=[PermissionScope.NETWORK],
            ))
        if any(n.startswith("mcp__") for n in str_names):
            permissions.append(Permission(
                resource="mcp-servers",
                scopes=[PermissionScope.EXECUTE],
            ))
        return permissions

    def _parse_delegations(self, from_agent: str, body: str) -> list[DelegationLink]:
        delegations: list[DelegationLink] = []
        seen: set[str] = set()

        # Match subagent_type="xxx" or subagent_type: "xxx"
        for m in re.finditer(r'subagent_type\s*[=:]\s*["\']([^"\']+)["\']', body):
            target = m.group(1)
            if target not in seen:
                seen.add(target)
                delegations.append(DelegationLink(
                    from_agent=from_agent,
                    to_agent=target,
                    delegation_type="spawn",
                ))

        # Match Agent(... name/subagent_type patterns
        for m in re.finditer(r'Agent\s*\(.*?subagent_type\s*[=:]\s*["\']([^"\']+)["\']', body, re.DOTALL):
            target = m.group(1)
            if target not in seen:
                seen.add(target)
                delegations.append(DelegationLink(
                    from_agent=from_agent,
                    to_agent=target,
                    delegation_type="spawn",
                ))

        # TeamCreate implies orchestration
        if "TeamCreate" in body:
            delegations.append(DelegationLink(
                from_agent=from_agent,
                to_agent="<team>",
                delegation_type="orchestrate",
            ))

        # SendMessage implies collaboration
        if "SendMessage" in body and "TeamCreate" not in body:
            delegations.append(DelegationLink(
                from_agent=from_agent,
                to_agent="<peer>",
                delegation_type="collaborate",
            ))

        return delegations

    def _extract_tags(self, fm: dict, disallowed: list) -> list[str]:
        tags = ["claude-code"]
        if fm.get("maxTurns"):
            tags.append(f"max-turns:{fm['maxTurns']}")
        if disallowed:
            tags.append("has-disallowed-tools")
        mode = fm.get("permissionMode", "")
        if mode and mode != "default":
            tags.append(f"mode:{mode}")
        return tags

    # --- Skills ---

    def _scan_skills(self, root: Path) -> list[AgentIdentity]:
        skills_dir = root / ".claude" / "skills"
        if not skills_dir.is_dir():
            return []

        agents: list[AgentIdentity] = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            agent = self._parse_skill_file(skill_md, root)
            if agent:
                agents.append(agent)
        return agents

    def _parse_skill_file(self, path: Path, root: Path) -> AgentIdentity | None:
        try:
            post = frontmatter.load(str(path))
        except Exception:
            return None

        fm = post.metadata
        return AgentIdentity(
            name=f"skill:{fm.get('name', path.parent.name)}",
            description=fm.get("description", ""),
            framework=AgentFramework.CLAUDE_CODE,
            source_file=str(path.relative_to(root)),
            repository=str(root),
            role="skill",
            tags=["claude-code", "skill"],
        )

    # --- MCP tool enrichment ---

    def _enrich_with_mcp_tools(self, root: Path, agents: list[AgentIdentity]) -> None:
        """Find .mcp.json files and enrich agents that reference those MCP servers."""
        mcp_tools = self._collect_mcp_tools(root)
        if not mcp_tools:
            return

        for agent in agents:
            for tool in agent.tools:
                if tool.name.startswith("mcp__"):
                    parts = tool.name.split("__")
                    if len(parts) >= 2:
                        server_prefix = parts[1]
                        if server_prefix in mcp_tools:
                            tool.description = f"MCP server: {server_prefix}"
                            tool.endpoint = mcp_tools[server_prefix].get("command", "")

    def _collect_mcp_tools(self, root: Path) -> dict[str, dict]:
        """Collect MCP server definitions from .mcp.json files."""
        servers: dict[str, dict] = {}

        for mcp_file in root.rglob(".mcp.json"):
            if any(p in str(mcp_file) for p in ("node_modules", ".venv", "venv", "__pycache__")):
                continue
            try:
                data = json.loads(mcp_file.read_text())
                mcp_servers = data.get("mcpServers", {})
                for name, config in mcp_servers.items():
                    servers[name] = {
                        "command": config.get("command", ""),
                        "args": config.get("args", []),
                        "source": str(mcp_file),
                    }
            except (json.JSONDecodeError, OSError):
                continue

        return servers
