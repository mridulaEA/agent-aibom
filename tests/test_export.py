"""Tests for export engine."""

import csv
import json

from agent_aibom.core.models import ExportFormat
from agent_aibom.export import ExportEngine
from agent_aibom.export.json_export import JsonExporter
from agent_aibom.export.sarif_export import SarifExporter
from agent_aibom.export.csv_export import CsvExporter


def test_json_export(sample_bom, tmp_dir):
    exporter = JsonExporter()
    path = exporter.export(sample_bom, tmp_dir)
    assert path.exists()
    data = json.loads(path.read_text())
    assert "agents" in data
    assert len(data["agents"]) == 2


def test_csv_export(sample_bom, tmp_dir):
    exporter = CsvExporter()
    path = exporter.export(sample_bom, tmp_dir)
    assert path.exists()
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["name"] in ("test-agent", "orphan-agent")


def test_sarif_export(sample_bom, tmp_dir):
    # SARIF needs risk findings — add some
    from agent_aibom.risk.scorer import RiskEngine
    engine = RiskEngine()
    score, findings = engine.score(sample_bom)
    sample_bom.risk_findings = findings
    sample_bom.risk_score = score

    exporter = SarifExporter()
    path = exporter.export(sample_bom, tmp_dir)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["version"] == "2.1.0"
    assert len(data["runs"]) == 1
    assert len(data["runs"][0]["results"]) > 0


def test_sarif_export_auto_risk(sample_bom, tmp_dir):
    """ExportEngine should auto-run risk for SARIF if findings are empty."""
    engine = ExportEngine()
    path = engine.export(sample_bom, ExportFormat.SARIF, tmp_dir)
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data["runs"][0]["results"]) > 0


def test_export_all(sample_bom, tmp_dir):
    engine = ExportEngine()
    paths = engine.export_all(
        sample_bom,
        [ExportFormat.JSON, ExportFormat.CSV],
        tmp_dir,
    )
    assert len(paths) == 2
    assert all(p.exists() for p in paths)
