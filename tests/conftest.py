"""Shared fixtures for Agent AIBOM tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    AgenticBOM,
    BOMMetadata,
    DelegationLink,
    ModelBinding,
    Permission,
    PermissionScope,
    RiskFinding,
    RiskCategory,
    RiskSeverity,
    Tool,
    ToolType,
)
from agent_aibom.core.registry import BOMRegistry


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def registry(tmp_dir):
    return BOMRegistry(tmp_dir)


@pytest.fixture
def sample_agent() -> AgentIdentity:
    return AgentIdentity(
        name="test-agent",
        description="A test agent",
        framework=AgentFramework.CLAUDE_CODE,
        source_file=".claude/agents/test-agent.md",
        owner="test-team",
        tools=[
            Tool(name="Read", tool_type=ToolType.FILE_SYSTEM),
            Tool(name="Write", tool_type=ToolType.FILE_SYSTEM),
            Tool(name="WebFetch", tool_type=ToolType.BROWSER, external=True),
            Tool(name="Bash", tool_type=ToolType.CLI),
        ],
        permissions=[
            Permission(resource="filesystem", scopes=[PermissionScope.READ, PermissionScope.WRITE]),
            Permission(resource="network", scopes=[PermissionScope.NETWORK]),
        ],
        models=[
            ModelBinding(provider="anthropic", model_id="opus"),
        ],
        delegations=[
            DelegationLink(from_agent="test-agent", to_agent="helper-agent", delegation_type="spawn"),
        ],
    )


@pytest.fixture
def sample_agent_no_owner() -> AgentIdentity:
    return AgentIdentity(
        name="orphan-agent",
        description="No owner",
        framework=AgentFramework.CLAUDE_CODE,
    )


@pytest.fixture
def sample_bom(sample_agent, sample_agent_no_owner) -> AgenticBOM:
    return AgenticBOM(
        metadata=BOMMetadata(repository="/test/repo"),
        agents=[sample_agent, sample_agent_no_owner],
        delegations=sample_agent.delegations,
    )
