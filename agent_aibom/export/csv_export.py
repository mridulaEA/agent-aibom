"""CSV exporter — flat agent-per-row table."""

from __future__ import annotations

import csv
from pathlib import Path

from agent_aibom.core.models import AgenticBOM


class CsvExporter:
    """Export BOM as a flat CSV with one row per agent."""

    COLUMNS = [
        "name",
        "framework",
        "description",
        "tool_count",
        "external_tool_count",
        "permission_count",
        "delegation_count",
        "model_count",
        "has_external_actions",
        "has_owner",
        "owner",
        "source_file",
        "tags",
    ]

    def export(self, bom: AgenticBOM, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "agent-aibom.csv"

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
            writer.writeheader()
            for agent in bom.agents:
                writer.writerow({
                    "name": agent.name,
                    "framework": agent.framework.value,
                    "description": agent.description[:200],
                    "tool_count": len(agent.tools),
                    "external_tool_count": len(agent.external_tools),
                    "permission_count": len(agent.permissions),
                    "delegation_count": len(agent.delegations),
                    "model_count": len(agent.models),
                    "has_external_actions": agent.has_external_actions,
                    "has_owner": agent.has_owner,
                    "owner": agent.owner or "",
                    "source_file": agent.source_file or "",
                    "tags": ";".join(agent.tags),
                })

        return path
