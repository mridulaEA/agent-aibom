"""Risk scoring engine — runs all rules and computes aggregate scores."""

from __future__ import annotations

from agent_aibom.core.config import RiskConfig
from agent_aibom.core.models import (
    AgenticBOM,
    RiskFinding,
    RiskScore,
    RiskSeverity,
)
from agent_aibom.risk.rules import ALL_RULES

SEVERITY_WEIGHTS: dict[RiskSeverity, float] = {
    RiskSeverity.CRITICAL: 10.0,
    RiskSeverity.HIGH: 7.0,
    RiskSeverity.MEDIUM: 4.0,
    RiskSeverity.LOW: 1.0,
    RiskSeverity.INFO: 0.0,
}


class RiskEngine:
    """Evaluates all agents in a BOM against risk rules and computes scores."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def score(self, bom: AgenticBOM) -> tuple[RiskScore, list[RiskFinding]]:
        """Run all rules against all agents, return aggregate score and findings."""
        all_findings: list[RiskFinding] = []

        for agent in bom.agents:
            for rule_fn in ALL_RULES:
                try:
                    findings = rule_fn(agent, self.config)
                    all_findings.extend(findings)
                except Exception:
                    pass  # Don't let one broken rule kill the whole assessment

        risk_score = self._compute_score(all_findings)
        return risk_score, all_findings

    def _compute_score(self, findings: list[RiskFinding]) -> RiskScore:
        if not findings:
            return RiskScore(overall=0.0, grade="A")

        # Count by severity
        counts: dict[RiskSeverity, int] = {}
        for sev in RiskSeverity:
            counts[sev] = sum(1 for f in findings if f.severity == sev)

        # Weighted sum
        weighted = sum(
            SEVERITY_WEIGHTS[sev] * count
            for sev, count in counts.items()
        )

        # Normalize to 0-10 scale
        # Max possible = 10 * total_findings (if all were critical)
        max_possible = 10.0 * len(findings) if findings else 1.0
        overall = min(10.0, (weighted / max_possible) * 10.0)

        # Breakdown by category
        breakdown: dict[str, float] = {}
        for finding in findings:
            cat = finding.category.value
            breakdown[cat] = breakdown.get(cat, 0) + SEVERITY_WEIGHTS[finding.severity]

        grade = RiskScore.compute_grade(overall)

        return RiskScore(
            overall=round(overall, 2),
            breakdown=breakdown,
            findings_count=counts,
            grade=grade,
        )
