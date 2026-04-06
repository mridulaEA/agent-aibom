"""Tests for core Pydantic models."""

from agent_aibom.core.models import (
    AgentFramework,
    AgentIdentity,
    AgenticBOM,
    BOMMetadata,
    FindingSource,
    RiskFinding,
    RiskCategory,
    RiskScore,
    RiskSeverity,
    Tool,
    ToolType,
)


def test_agent_identity_defaults():
    agent = AgentIdentity(name="foo")
    assert agent.name == "foo"
    assert agent.framework == AgentFramework.UNKNOWN
    assert agent.tools == []
    assert agent.has_owner is False
    assert agent.has_external_actions is False


def test_agent_external_tools():
    agent = AgentIdentity(
        name="foo",
        tools=[
            Tool(name="Read", tool_type=ToolType.FILE_SYSTEM),
            Tool(name="WebFetch", tool_type=ToolType.BROWSER, external=True),
        ],
    )
    assert agent.has_external_actions is True
    assert len(agent.external_tools) == 1
    assert agent.tool_names == ["Read", "WebFetch"]


def test_risk_finding_provenance():
    f = RiskFinding(
        agent_id="a1",
        agent_name="test",
        category=RiskCategory.NO_OWNER,
        severity=RiskSeverity.MEDIUM,
        title="test",
        description="test",
        source=FindingSource.HEURISTIC,
        confidence=0.6,
        source_file="agents/foo.md",
        source_line=10,
    )
    assert f.source == FindingSource.HEURISTIC
    assert f.confidence == 0.6
    assert f.source_file == "agents/foo.md"


def test_risk_score_grading():
    assert RiskScore.compute_grade(0.0) == "A"
    assert RiskScore.compute_grade(1.5) == "A"
    assert RiskScore.compute_grade(2.5) == "B"
    assert RiskScore.compute_grade(5.0) == "C"
    assert RiskScore.compute_grade(7.0) == "D"
    assert RiskScore.compute_grade(9.0) == "F"


def test_bom_summary(sample_bom):
    s = sample_bom.summary()
    assert s["agent_count"] == 2
    assert s["repository"] == "/test/repo"
    assert s["agents_without_owners"] == 1


def test_bom_get_agent(sample_bom):
    assert sample_bom.get_agent("test-agent") is not None
    assert sample_bom.get_agent("nonexistent") is None


def test_bom_serialization(sample_bom):
    data = sample_bom.model_dump(mode="json")
    restored = AgenticBOM.model_validate(data)
    assert restored.agent_count == sample_bom.agent_count
    assert restored.agents[0].name == sample_bom.agents[0].name


def test_bom_link():
    meta = BOMMetadata()
    link = meta.bom_link
    assert link.startswith("urn:cdx:")
    assert "/1" in link  # version 1

    ref = meta.bom_link_ref("my-agent")
    assert ref.endswith("#my-agent")
    assert ref.startswith("urn:cdx:")


def test_delegation_authority_scope():
    from agent_aibom.core.models import DelegationLink
    d = DelegationLink(
        from_agent="a", to_agent="b", delegation_type="spawn",
        authority_scope=["read:account-data", "write:none"],
    )
    assert d.authority_scope == ["read:account-data", "write:none"]


def test_agent_attestation():
    from agent_aibom.core.models import AgentAttestation, DelegationHop
    att = AgentAttestation(
        principal="user:alice@corp.com",
        agent_name="finance-agent",
        agent_bom_link="urn:cdx:abc-123/1#finance-agent",
        authority_scope=["read:account-data"],
        delegation_chain=[
            DelegationHop(agent_name="support-agent", action="delegate", authority_scope=["read:account-data"]),
            DelegationHop(agent_name="finance-agent", action="sql-query", authority_scope=["read:account-data"]),
        ],
        approval_gate="high-risk-sql",
        approval_granted=True,
        policy_reference="data-access-policy-v2",
        policy_result="pass",
        trace_id="trace-xyz-789",
    )
    assert att.principal == "user:alice@corp.com"
    assert len(att.delegation_chain) == 2
    assert att.approval_granted is True

    # Serialization round-trip
    data = att.model_dump(mode="json")
    restored = AgentAttestation.model_validate(data)
    assert restored.agent_name == "finance-agent"
    assert len(restored.delegation_chain) == 2
