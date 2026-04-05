"""Policy definitions and evaluation for organizational governance."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent_aibom.core.models import (
    AgenticBOM,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)


class PolicySet(BaseModel):
    """Organizational policies for agent governance."""
    approved_models: list[str] = Field(default_factory=list)
    approved_tools: list[str] = Field(default_factory=list)
    max_delegation_depth: int = 5
    require_owner: bool = True
    require_approval_for_external: bool = True
    max_tools_per_agent: int = 50
    forbidden_permission_combos: list[list[str]] = Field(
        default_factory=lambda: [["network", "execute"]]
    )

    def evaluate(self, bom: AgenticBOM) -> list[RiskFinding]:
        """Evaluate BOM against all policies, return violations."""
        findings: list[RiskFinding] = []

        for agent in bom.agents:
            # Check tool count
            if len(agent.tools) > self.max_tools_per_agent:
                findings.append(RiskFinding(
                    agent_id=agent.id,
                    agent_name=agent.name,
                    category=RiskCategory.EXCESSIVE_PERMISSIONS,
                    severity=RiskSeverity.MEDIUM,
                    title=f"Too many tools: {len(agent.tools)}",
                    description=f"Agent has {len(agent.tools)} tools (max: {self.max_tools_per_agent})",
                    recommendation="Reduce tool count or split into specialized agents",
                ))

            # Check delegation depth
            for deleg in agent.delegations:
                if deleg.max_depth is not None and deleg.max_depth > self.max_delegation_depth:
                    findings.append(RiskFinding(
                        agent_id=agent.id,
                        agent_name=agent.name,
                        category=RiskCategory.UNBOUNDED_DELEGATION,
                        severity=RiskSeverity.MEDIUM,
                        title=f"Delegation depth {deleg.max_depth} exceeds policy max {self.max_delegation_depth}",
                        description=f"Delegation to '{deleg.to_agent}' allows depth {deleg.max_depth}",
                        recommendation=f"Reduce max_depth to {self.max_delegation_depth} or less",
                    ))

        return findings
