"""Built-in risk rules — one per RiskCategory."""

from __future__ import annotations

import re

from agent_aibom.core.config import RiskConfig
from agent_aibom.core.models import (
    AgentIdentity,
    FindingSource,
    PermissionScope,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)

# Secret patterns to detect in agent descriptions/metadata
SECRET_PATTERNS = [
    re.compile(r'(?:api[_-]?key|secret|token|password)\s*[:=]\s*["\'][^"\']{8,}["\']', re.I),
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),
    re.compile(r'ghp_[a-zA-Z0-9]{36}'),
    re.compile(r'AKIA[A-Z0-9]{16}'),
]


def rule_excessive_permissions(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    for perm in agent.permissions:
        if any(s in (PermissionScope.ADMIN, PermissionScope.FULL) for s in perm.scopes):
            findings.append(RiskFinding(
                agent_id=agent.id,
                agent_name=agent.name,
                category=RiskCategory.EXCESSIVE_PERMISSIONS,
                severity=RiskSeverity.HIGH,
                title=f"Excessive permission: {perm.resource}",
                description=f"Agent has {[s.value for s in perm.scopes]} on '{perm.resource}'",
                evidence=f"Permission scopes: {[s.value for s in perm.scopes]}",
                recommendation="Restrict to least-privilege scopes (read/write only)",
            ))
    return findings


def rule_missing_approval_gate(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    if not config.require_approval_gates:
        return []
    if agent.has_external_actions and not agent.approval_gates:
        return [RiskFinding(
            agent_id=agent.id,
            agent_name=agent.name,
            category=RiskCategory.MISSING_APPROVAL_GATE,
            severity=RiskSeverity.HIGH,
            title="No approval gate for external actions",
            description="Agent can take external actions without any approval gate",
            evidence=f"External tools: {[t.name for t in agent.external_tools]}",
            recommendation="Add a human-in-the-loop or policy-check gate",
        )]
    return []


def rule_unapproved_model(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    if not config.approved_models:
        return []
    findings: list[RiskFinding] = []
    for model in agent.models:
        if model.model_id not in config.approved_models:
            findings.append(RiskFinding(
                agent_id=agent.id,
                agent_name=agent.name,
                category=RiskCategory.UNAPPROVED_MODEL,
                severity=RiskSeverity.MEDIUM,
                title=f"Unapproved model: {model.model_id}",
                description=f"Model '{model.model_id}' from '{model.provider}' is not in the approved list",
                evidence=f"Model: {model.provider}/{model.model_id}",
                recommendation=f"Use an approved model: {config.approved_models}",
            ))
    return findings


def rule_unapproved_tool(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    if not config.approved_tools:
        return []
    findings: list[RiskFinding] = []
    for tool in agent.tools:
        if tool.name not in config.approved_tools:
            findings.append(RiskFinding(
                agent_id=agent.id,
                agent_name=agent.name,
                category=RiskCategory.UNAPPROVED_TOOL,
                severity=RiskSeverity.MEDIUM,
                title=f"Unapproved tool: {tool.name}",
                description=f"Tool '{tool.name}' is not in the approved list",
                evidence=f"Tool: {tool.name} ({tool.tool_type.value})",
                recommendation=f"Review and add to approved tools or remove from agent",
            ))
    return findings


def rule_no_owner(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    if not config.require_owner:
        return []
    if not agent.has_owner:
        return [RiskFinding(
            agent_id=agent.id,
            agent_name=agent.name,
            category=RiskCategory.NO_OWNER,
            severity=RiskSeverity.MEDIUM,
            title="No owner assigned",
            description="Agent has no owner — accountability gap",
            recommendation="Assign an owner to this agent",
        )]
    return []


def rule_external_action(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    if agent.has_external_actions:
        return [RiskFinding(
            agent_id=agent.id,
            agent_name=agent.name,
            category=RiskCategory.EXTERNAL_ACTION,
            severity=RiskSeverity.HIGH,
            title="Agent can take external actions",
            description=f"Agent has {len(agent.external_tools)} external tool(s)",
            evidence=f"External tools: {[t.name for t in agent.external_tools]}",
            recommendation="Review external tool access and add approval gates",
        )]
    return []


def rule_data_exfiltration(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    has_network = any(
        PermissionScope.NETWORK in p.scopes for p in agent.permissions
    )
    has_read = any(
        PermissionScope.READ in p.scopes for p in agent.permissions
    )
    if has_network and has_read:
        return [RiskFinding(
            agent_id=agent.id,
            agent_name=agent.name,
            category=RiskCategory.DATA_EXFILTRATION,
            severity=RiskSeverity.CRITICAL,
            title="Potential data exfiltration risk",
            description="Agent has both network access and filesystem read — could exfiltrate data",
            evidence="Permissions: network + read",
            recommendation="Separate network and read agents, or add DLP controls",
        )]
    return []


def rule_prompt_injection(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    # Heuristic: agents with WebFetch/WebSearch + Bash are high risk
    tool_names = {t.name for t in agent.tools}
    web_tools = tool_names & {"WebFetch", "WebSearch"}
    exec_tools = tool_names & {"Bash", "Write", "Edit"}
    if web_tools and exec_tools:
        return [RiskFinding(
            agent_id=agent.id,
            agent_name=agent.name,
            category=RiskCategory.PROMPT_INJECTION,
            severity=RiskSeverity.HIGH,
            title="Prompt injection risk: web input + code execution",
            description="Agent fetches external content and can execute/write — prompt injection vector",
            evidence=f"Web: {web_tools}, Exec: {exec_tools}",
            recommendation="Add input sanitization or separate web-reading from code-execution agents",
        )]
    return []


def rule_unbounded_delegation(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    for deleg in agent.delegations:
        if deleg.max_depth is None:
            findings.append(RiskFinding(
                agent_id=agent.id,
                agent_name=agent.name,
                category=RiskCategory.UNBOUNDED_DELEGATION,
                severity=RiskSeverity.HIGH,
                title=f"Unbounded delegation to '{deleg.to_agent}'",
                description=f"Delegation from '{deleg.from_agent}' to '{deleg.to_agent}' has no depth limit",
                evidence=f"Delegation type: {deleg.delegation_type}, max_depth: None",
                recommendation="Set a max_depth on delegation links",
            ))
    return findings


def rule_intent_laundering(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    """Flag agents that delegate to external-tool-capable agents without authority scope."""
    findings: list[RiskFinding] = []
    for deleg in agent.delegations:
        if not deleg.authority_scope and deleg.delegation_type in ("spawn", "route", "escalate"):
            findings.append(RiskFinding(
                agent_id=agent.id,
                agent_name=agent.name,
                category=RiskCategory.INTENT_LAUNDERING,
                severity=RiskSeverity.HIGH,
                title=f"Intent laundering risk: delegation to '{deleg.to_agent}' without authority scope",
                description=(
                    f"Agent delegates to '{deleg.to_agent}' via '{deleg.delegation_type}' "
                    f"without specifying authority_scope. The downstream agent may perform "
                    f"actions beyond what the original principal intended."
                ),
                evidence=f"Delegation: {deleg.from_agent} → {deleg.to_agent}, authority_scope: []",
                recommendation="Add explicit authority_scope to delegation links to constrain downstream actions",
                source=FindingSource.STATIC_ANALYSIS,
                confidence=0.7,
            ))
    return findings


def rule_missing_trace(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    # In static analysis, no agent has runtime traces — flag as info
    return [RiskFinding(
        agent_id=agent.id,
        agent_name=agent.name,
        category=RiskCategory.MISSING_TRACE,
        severity=RiskSeverity.LOW,
        title="No runtime tracing configured",
        description="Agent has no runtime tracing — harder to audit behavior",
        recommendation="Instrument with agent-aibom runtime SDK",
    )]


def rule_stale_dependency(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    for dep in agent.dependencies:
        if dep.cve_ids:
            findings.append(RiskFinding(
                agent_id=agent.id,
                agent_name=agent.name,
                category=RiskCategory.STALE_DEPENDENCY,
                severity=RiskSeverity.LOW,
                title=f"Dependency '{dep.name}' has known CVEs",
                description=f"{dep.name} {dep.version or ''} has {len(dep.cve_ids)} CVE(s)",
                evidence=f"CVEs: {dep.cve_ids}",
                recommendation=f"Upgrade {dep.name} to a patched version",
            ))
    return findings


def rule_secret_exposure(agent: AgentIdentity, config: RiskConfig) -> list[RiskFinding]:
    # Check description, metadata, and tool parameters for secrets
    text_to_scan = " ".join([
        agent.description,
        agent.role,
        agent.goal,
        agent.backstory,
        str(agent.metadata),
    ])
    for pattern in SECRET_PATTERNS:
        if pattern.search(text_to_scan):
            return [RiskFinding(
                agent_id=agent.id,
                agent_name=agent.name,
                category=RiskCategory.SECRET_EXPOSURE,
                severity=RiskSeverity.CRITICAL,
                title="Potential secret in agent definition",
                description="Agent definition may contain hardcoded secrets",
                recommendation="Move secrets to environment variables or a vault",
            )]
    return []


# Registry of all rules
ALL_RULES = [
    rule_excessive_permissions,
    rule_missing_approval_gate,
    rule_unapproved_model,
    rule_unapproved_tool,
    rule_no_owner,
    rule_external_action,
    rule_data_exfiltration,
    rule_prompt_injection,
    rule_unbounded_delegation,
    rule_intent_laundering,
    rule_missing_trace,
    rule_stale_dependency,
    rule_secret_exposure,
]
