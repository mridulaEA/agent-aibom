"""MCP server and tool scanner — parses .mcp.json and @mcp.tool() definitions."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    Tool,
    ToolType,
)
from agent_aibom.discovery.base import AbstractScanner


class MCPScanner(AbstractScanner):
    """Discovers MCP servers and their tools."""

    @property
    def name(self) -> str:
        return "MCP Scanner"

    @property
    def framework(self) -> AgentFramework:
        return AgentFramework.CUSTOM

    def scan(self, path: Path) -> list[AgentIdentity]:
        agents: list[AgentIdentity] = []
        exclude = ["node_modules", ".venv", "venv", "__pycache__", ".git"]

        # Resolve .mcp.json files
        mcp_files = self._resolve_files(
            path, ["**/.mcp.json"], exclude,
        )
        for mcp_file in mcp_files:
            agents.extend(self._parse_mcp_json(mcp_file, path))

        # Resolve server.py files with @mcp.tool()
        # Only use default server glob if no include_globs override
        if not self.override.include_globs:
            for server_file in path.rglob("**/mcp/server.py"):
                if not self._should_exclude(server_file, exclude):
                    agent = self._parse_server_py(server_file, path)
                    if agent:
                        agents.append(agent)

        return agents

    def _parse_mcp_json(self, mcp_file: Path, root: Path) -> list[AgentIdentity]:
        try:
            data = json.loads(mcp_file.read_text())
        except (json.JSONDecodeError, OSError):
            return []

        agents: list[AgentIdentity] = []
        mcp_servers = data.get("mcpServers", {})

        for server_name, config in mcp_servers.items():
            command = config.get("command", "")
            args = config.get("args", [])

            agents.append(AgentIdentity(
                name=f"mcp:{server_name}",
                description=f"MCP server '{server_name}' ({command})",
                framework=AgentFramework.CUSTOM,
                source_file=str(mcp_file.relative_to(root)),
                repository=str(root),
                role="mcp-server",
                tools=[Tool(
                    name=server_name,
                    description=f"MCP server: {command} {' '.join(str(a) for a in args)}",
                    tool_type=ToolType.MCP,
                )],
                tags=["mcp", "server"],
                metadata={
                    "command": command,
                    "args": args,
                    "type": config.get("type", "stdio"),
                },
            ))

        return agents

    def _parse_server_py(self, server_file: Path, root: Path) -> AgentIdentity | None:
        try:
            content = server_file.read_text()
        except OSError:
            return None

        # Extract @mcp.tool() decorated functions
        tool_pattern = re.compile(
            r'@\w+\.tool\(\)\s*\n'
            r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\).*?:\s*\n'
            r'\s*"""([^"]*?)"""',
            re.DOTALL,
        )

        tools: list[Tool] = []
        for m in tool_pattern.finditer(content):
            func_name = m.group(1)
            docstring = m.group(2).strip().split("\n")[0]  # First line only
            tools.append(Tool(
                name=func_name,
                description=docstring,
                tool_type=ToolType.MCP,
            ))

        if not tools:
            return None

        # Derive server name from parent directory
        parent = server_file.parent.parent.name  # e.g., security_iq

        return AgentIdentity(
            name=f"mcp-server:{parent}",
            description=f"MCP server with {len(tools)} tools from {parent}",
            framework=AgentFramework.CUSTOM,
            source_file=str(server_file.relative_to(root)),
            repository=str(root),
            role="mcp-server",
            tools=tools,
            tags=["mcp", "server", parent],
        )
