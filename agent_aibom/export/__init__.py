"""Export engine — dispatch BOM to format-specific exporters."""

from __future__ import annotations

from pathlib import Path

from agent_aibom.core.config import RiskConfig
from agent_aibom.core.models import AgenticBOM, ExportFormat
from agent_aibom.export.json_export import JsonExporter
from agent_aibom.export.sarif_export import SarifExporter
from agent_aibom.export.csv_export import CsvExporter


class ExportEngine:
    """Dispatches BOM export to the correct format handler."""

    EXPORTERS = {
        ExportFormat.JSON: JsonExporter,
        ExportFormat.SARIF: SarifExporter,
        ExportFormat.CSV: CsvExporter,
    }

    def __init__(self, risk_config: RiskConfig | None = None) -> None:
        self.risk_config = risk_config

    def export(
        self,
        bom: AgenticBOM,
        fmt: ExportFormat,
        output_dir: Path,
    ) -> Path:
        """Export BOM in the given format. Returns path to output file.

        If format is SARIF and bom has no risk findings, runs risk scoring first.
        """
        # SARIF needs risk findings — run scoring if missing
        if fmt == ExportFormat.SARIF and not bom.risk_findings:
            from agent_aibom.risk.scorer import RiskEngine
            engine = RiskEngine(self.risk_config or RiskConfig())
            score, findings = engine.score(bom)
            bom.risk_findings = findings
            bom.risk_score = score

        exporter_cls = self.EXPORTERS.get(fmt)
        if not exporter_cls:
            raise ValueError(f"Unsupported export format: {fmt.value}")

        exporter = exporter_cls()
        return exporter.export(bom, output_dir)

    def export_all(
        self,
        bom: AgenticBOM,
        formats: list[ExportFormat],
        output_dir: Path,
    ) -> list[Path]:
        """Export BOM in multiple formats. Returns list of output paths."""
        paths: list[Path] = []
        for fmt in formats:
            paths.append(self.export(bom, fmt, output_dir))
        return paths


__all__ = ["ExportEngine", "JsonExporter", "SarifExporter", "CsvExporter"]
