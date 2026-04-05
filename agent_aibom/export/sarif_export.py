"""SARIF 2.1.0 exporter — maps risk findings to SARIF results."""

from __future__ import annotations

import json
from pathlib import Path

from agent_aibom.core.models import AgenticBOM, RiskFinding, RiskSeverity


SEVERITY_TO_SARIF_LEVEL = {
    RiskSeverity.CRITICAL: "error",
    RiskSeverity.HIGH: "error",
    RiskSeverity.MEDIUM: "warning",
    RiskSeverity.LOW: "note",
    RiskSeverity.INFO: "note",
}


class SarifExporter:
    """Export risk findings as SARIF 2.1.0 JSON."""

    def export(self, bom: AgenticBOM, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "agent-aibom.sarif"

        # Build rules from unique categories
        rules: list[dict] = []
        rule_index: dict[str, int] = {}
        for finding in bom.risk_findings:
            rule_id = finding.category.value
            if rule_id not in rule_index:
                rule_index[rule_id] = len(rules)
                rules.append({
                    "id": rule_id,
                    "name": rule_id.replace("-", " ").title(),
                    "shortDescription": {"text": rule_id},
                    "defaultConfiguration": {
                        "level": SEVERITY_TO_SARIF_LEVEL.get(finding.severity, "note"),
                    },
                })

        # Build results
        results: list[dict] = []
        for finding in bom.risk_findings:
            result: dict = {
                "ruleId": finding.category.value,
                "ruleIndex": rule_index[finding.category.value],
                "level": SEVERITY_TO_SARIF_LEVEL.get(finding.severity, "note"),
                "message": {
                    "text": f"[{finding.agent_name}] {finding.title}: {finding.description}",
                },
                "properties": {
                    "agent": finding.agent_name,
                    "severity": finding.severity.value,
                    "source": finding.source.value,
                    "confidence": finding.confidence,
                },
            }
            if finding.source_file:
                location: dict = {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.source_file},
                    }
                }
                if finding.source_line:
                    location["physicalLocation"]["region"] = {
                        "startLine": finding.source_line,
                    }
                result["locations"] = [location]

            if finding.recommendation:
                result["fixes"] = [{
                    "description": {"text": finding.recommendation},
                }]

            results.append(result)

        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "agent-aibom",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/agent-aibom/agent-aibom",
                        "rules": rules,
                    }
                },
                "results": results,
            }],
        }

        path.write_text(json.dumps(sarif, indent=2))
        return path
