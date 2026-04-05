"""Edge case tests for discovery scanners."""

import json
import tempfile
from pathlib import Path

from agent_aibom.core.config import ScanConfig, ScannerOverride
from agent_aibom.discovery import DiscoveryOrchestrator
from agent_aibom.discovery.claude_scanner import ClaudeCodeScanner
from agent_aibom.discovery.mcp_scanner import MCPScanner
from agent_aibom.discovery.generic_scanner import GenericScanner


def test_empty_directory():
    with tempfile.TemporaryDirectory() as d:
        orch = DiscoveryOrchestrator()
        agents = orch.discover(d)
        assert agents == []


def test_invalid_path():
    import pytest
    orch = DiscoveryOrchestrator()
    with pytest.raises(ValueError, match="does not exist"):
        orch.discover("/nonexistent/xyz")


def test_claude_scanner_malformed_frontmatter():
    """Scanner should handle broken YAML frontmatter gracefully."""
    with tempfile.TemporaryDirectory() as d:
        agents_dir = Path(d) / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        # Write a malformed .md file
        (agents_dir / "broken.md").write_text("---\nname: [invalid yaml\n---\nbody")

        # Write a valid one
        (agents_dir / "good.md").write_text("---\nname: good-agent\ndescription: works\n---\nbody")

        scanner = ClaudeCodeScanner()
        agents = scanner.scan(Path(d))
        # Should get at least the good one, not crash
        assert any(a.name == "good-agent" for a in agents)


def test_claude_scanner_no_agents_dir():
    with tempfile.TemporaryDirectory() as d:
        scanner = ClaudeCodeScanner()
        agents = scanner.scan(Path(d))
        assert agents == []


def test_claude_scanner_with_tools_and_model():
    with tempfile.TemporaryDirectory() as d:
        agents_dir = Path(d) / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "test.md").write_text(
            "---\n"
            "name: test-scanner-agent\n"
            "description: A test\n"
            "model: opus\n"
            "tools:\n"
            "  - Read\n"
            "  - Write\n"
            "  - Bash\n"
            "  - WebFetch\n"
            "  - mcp__siq__scan\n"
            "---\n"
            "Body with subagent_type=\"helper-bot\" reference.\n"
        )

        scanner = ClaudeCodeScanner()
        agents = scanner.scan(Path(d))
        assert len(agents) == 1
        agent = agents[0]
        assert agent.name == "test-scanner-agent"
        assert len(agent.tools) == 5
        assert agent.models[0].model_id == "opus"
        assert agent.has_external_actions  # WebFetch + mcp
        assert len(agent.delegations) == 1  # subagent_type found
        assert agent.delegations[0].to_agent == "helper-bot"


def test_claude_scanner_skills():
    with tempfile.TemporaryDirectory() as d:
        skill_dir = Path(d) / ".claude" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: cool-skill\ndescription: Does cool stuff\n---\nBody"
        )

        scanner = ClaudeCodeScanner()
        agents = scanner.scan(Path(d))
        assert any("skill:" in a.name for a in agents)


def test_mcp_scanner_valid_json():
    with tempfile.TemporaryDirectory() as d:
        mcp = {"mcpServers": {"myserver": {"type": "stdio", "command": "uv", "args": ["run"]}}}
        (Path(d) / ".mcp.json").write_text(json.dumps(mcp))

        scanner = MCPScanner()
        agents = scanner.scan(Path(d))
        assert len(agents) == 1
        assert agents[0].name == "mcp:myserver"


def test_mcp_scanner_broken_json():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / ".mcp.json").write_text("not json{{{")
        scanner = MCPScanner()
        agents = scanner.scan(Path(d))
        assert agents == []


def test_generic_scanner_no_false_positives():
    """Generic scanner should not flag normal Python files."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "normal.py").write_text("import os\nprint('hello')\n")
        scanner = GenericScanner()
        agents = scanner.scan(Path(d))
        assert agents == []


def test_generic_scanner_finds_anthropic():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "bot.py").write_text(
            "from anthropic import Anthropic\nclient = anthropic.Anthropic()\n"
        )
        scanner = GenericScanner()
        agents = scanner.scan(Path(d))
        assert len(agents) >= 1


def test_orchestrator_deduplication():
    """Two scanners finding the same agent should deduplicate."""
    with tempfile.TemporaryDirectory() as d:
        agents_dir = Path(d) / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "dedup.md").write_text("---\nname: dedup-agent\n---\nbody")

        config = ScanConfig(frameworks=["claude-code"])
        orch = DiscoveryOrchestrator(config)
        agents = orch.discover(d)
        names = [a.name for a in agents]
        assert names.count("dedup-agent") == 1


def test_orchestrator_scanner_error_recovery():
    """If a scanner throws, orchestrator should still return partial results."""
    with tempfile.TemporaryDirectory() as d:
        agents_dir = Path(d) / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "ok.md").write_text("---\nname: survivor\n---\nbody")

        config = ScanConfig(frameworks=["claude-code", "generic"])
        orch = DiscoveryOrchestrator(config)
        agents = orch.discover(d)
        assert any(a.name == "survivor" for a in agents)


# --- ScannerOverride tests ---


def test_scanner_override_include_globs():
    """Override include_globs should redirect the scanner to a custom path."""
    with tempfile.TemporaryDirectory() as d:
        # Put agents in a non-standard location
        custom_dir = Path(d) / "custom-agents"
        custom_dir.mkdir()
        (custom_dir / "special.md").write_text("---\nname: custom-agent\n---\nbody")

        # Default scan should NOT find it (not in .claude/agents/)
        scanner_default = ClaudeCodeScanner()
        assert scanner_default.scan(Path(d)) == []

        # Override scan SHOULD find it
        override = ScannerOverride(include_globs=["custom-agents/*.md"])
        scanner_override = ClaudeCodeScanner(override=override)
        agents = scanner_override.scan(Path(d))
        assert any(a.name == "custom-agent" for a in agents)


def test_scanner_override_extra_exclude():
    """Override extra_exclude should filter out additional paths."""
    with tempfile.TemporaryDirectory() as d:
        agents_dir = Path(d) / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "keep.md").write_text("---\nname: keep-me\n---\nbody")
        (agents_dir / "skip.md").write_text("---\nname: skip-me\n---\nbody")

        # Without extra_exclude: finds both
        scanner = ClaudeCodeScanner()
        agents = scanner.scan(Path(d))
        assert len(agents) == 2

        # With extra_exclude on "skip": only finds keep
        override = ScannerOverride(extra_exclude=["skip"])
        scanner2 = ClaudeCodeScanner(override=override)
        agents2 = scanner2.scan(Path(d))
        assert len(agents2) == 1
        assert agents2[0].name == "keep-me"


def test_scanner_override_enabled_false():
    """Disabled scanner should not be instantiated by orchestrator."""
    config = ScanConfig(
        frameworks=["claude-code", "generic"],
        scanner_overrides={
            "generic": ScannerOverride(enabled=False),
        },
    )
    orch = DiscoveryOrchestrator(config)
    assert "Generic Scanner" not in orch.scanner_names
    assert "Claude Code Scanner" in orch.scanner_names


def test_mcp_override_include_globs():
    """MCP scanner should use override globs for .mcp.json discovery."""
    with tempfile.TemporaryDirectory() as d:
        # Put .mcp.json in a nested custom path
        nested = Path(d) / "services" / "api"
        nested.mkdir(parents=True)
        mcp = {"mcpServers": {"api-server": {"command": "node", "args": ["server.js"]}}}
        (nested / ".mcp.json").write_text(json.dumps(mcp))

        # Default scan finds it via **/.mcp.json
        scanner_default = MCPScanner()
        assert len(scanner_default.scan(Path(d))) >= 1

        # Override restricts to only services/api/
        override = ScannerOverride(include_globs=["services/api/.mcp.json"])
        scanner_override = MCPScanner(override=override)
        agents = scanner_override.scan(Path(d))
        assert len(agents) == 1
        assert agents[0].name == "mcp:api-server"


def test_orchestrator_passes_overrides():
    """Orchestrator should pass scanner_overrides from config to each scanner."""
    with tempfile.TemporaryDirectory() as d:
        custom = Path(d) / "my-agents"
        custom.mkdir()
        (custom / "agent.md").write_text("---\nname: overridden\n---\nbody")

        config = ScanConfig(
            frameworks=["claude-code"],
            scanner_overrides={
                "claude-code": ScannerOverride(include_globs=["my-agents/*.md"]),
            },
        )
        orch = DiscoveryOrchestrator(config)
        agents = orch.discover(d)
        assert any(a.name == "overridden" for a in agents)
