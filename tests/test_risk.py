"""Tests for risk scoring engine and rules."""

from agent_aibom.core.config import RiskConfig
from agent_aibom.core.models import (
    AgentIdentity,
    AgenticBOM,
    DelegationLink,
    Permission,
    PermissionScope,
    RiskCategory,
    RiskSeverity,
    Tool,
    ToolType,
)
from agent_aibom.risk.rules import (
    rule_data_exfiltration,
    rule_excessive_permissions,
    rule_external_action,
    rule_missing_approval_gate,
    rule_missing_trace,
    rule_no_owner,
    rule_prompt_injection,
    rule_secret_exposure,
    rule_unbounded_delegation,
    rule_unapproved_model,
)
from agent_aibom.risk.scorer import RiskEngine


def test_rule_no_owner():
    agent = AgentIdentity(name="orphan")
    config = RiskConfig(require_owner=True)
    findings = rule_no_owner(agent, config)
    assert len(findings) == 1
    assert findings[0].category == RiskCategory.NO_OWNER


def test_rule_no_owner_disabled():
    agent = AgentIdentity(name="orphan")
    config = RiskConfig(require_owner=False)
    findings = rule_no_owner(agent, config)
    assert len(findings) == 0


def test_rule_excessive_permissions():
    agent = AgentIdentity(
        name="admin",
        permissions=[Permission(resource="all", scopes=[PermissionScope.ADMIN])],
    )
    findings = rule_excessive_permissions(agent, RiskConfig())
    assert len(findings) == 1
    assert findings[0].severity == RiskSeverity.HIGH


def test_rule_external_action():
    agent = AgentIdentity(
        name="web-agent",
        tools=[Tool(name="WebFetch", external=True)],
    )
    findings = rule_external_action(agent, RiskConfig())
    assert len(findings) == 1


def test_rule_data_exfiltration():
    agent = AgentIdentity(
        name="leaky",
        permissions=[
            Permission(resource="fs", scopes=[PermissionScope.READ]),
            Permission(resource="net", scopes=[PermissionScope.NETWORK]),
        ],
    )
    findings = rule_data_exfiltration(agent, RiskConfig())
    assert len(findings) == 1
    assert findings[0].severity == RiskSeverity.CRITICAL


def test_rule_prompt_injection():
    agent = AgentIdentity(
        name="risky",
        tools=[
            Tool(name="WebFetch"),
            Tool(name="Bash"),
        ],
    )
    findings = rule_prompt_injection(agent, RiskConfig())
    assert len(findings) == 1


def test_rule_unbounded_delegation():
    agent = AgentIdentity(
        name="boss",
        delegations=[
            DelegationLink(from_agent="boss", to_agent="worker", delegation_type="spawn"),
        ],
    )
    findings = rule_unbounded_delegation(agent, RiskConfig())
    assert len(findings) == 1  # max_depth is None


def test_rule_missing_trace():
    agent = AgentIdentity(name="untraced")
    findings = rule_missing_trace(agent, RiskConfig())
    assert len(findings) == 1
    assert findings[0].severity == RiskSeverity.LOW


def test_rule_secret_exposure():
    agent = AgentIdentity(
        name="leaky",
        description='config: api_key="sk-1234567890abcdefghijklmnop"',
    )
    findings = rule_secret_exposure(agent, RiskConfig())
    assert len(findings) == 1
    assert findings[0].severity == RiskSeverity.CRITICAL


def test_rule_unapproved_model():
    from agent_aibom.core.models import ModelBinding
    agent = AgentIdentity(
        name="modeled",
        models=[ModelBinding(provider="anthropic", model_id="opus")],
    )
    config = RiskConfig(approved_models=["sonnet"])
    findings = rule_unapproved_model(agent, config)
    assert len(findings) == 1


def test_risk_engine_scoring(sample_bom):
    engine = RiskEngine()
    score, findings = engine.score(sample_bom)
    assert score.overall >= 0.0
    assert score.overall <= 10.0
    assert score.grade in ("A", "B", "C", "D", "F")
    assert len(findings) > 0


def test_risk_engine_empty_bom():
    bom = AgenticBOM()
    engine = RiskEngine()
    score, findings = engine.score(bom)
    assert score.overall == 0.0
    assert score.grade == "A"
    assert len(findings) == 0
