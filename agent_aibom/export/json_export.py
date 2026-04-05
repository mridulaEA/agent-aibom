"""JSON exporter — native BOM format using Pydantic serialization."""

from __future__ import annotations

import json
from pathlib import Path

from agent_aibom.core.models import AgenticBOM


class JsonExporter:
    """Export BOM as pretty-printed JSON."""

    def export(self, bom: AgenticBOM, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "agent-aibom.json"
        data = bom.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2, default=str))
        return path
