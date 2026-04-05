"""CLI integration tests via Typer CliRunner."""

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from agent_aibom.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "agent-aibom" in result.stdout


def test_scan_nonexistent_path():
    result = runner.invoke(app, ["scan", "/nonexistent/path/xyz"])
    assert result.exit_code == 1


def test_scan_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["scan", d, "--store-dir", d])
        assert result.exit_code == 0
        assert "0 agents" in result.stdout


def test_scan_quiet():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["scan", d, "--store-dir", d, "--quiet"])
        assert result.exit_code == 0
        assert "urn:uuid:" in result.stdout


def test_risk_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["risk", d, "--store-dir", d])
        assert result.exit_code == 0
        assert "Grade" in result.stdout


def test_export_json():
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "output")
        result = runner.invoke(app, ["export", d, "-f", "json", "-d", out, "--store-dir", d])
        assert result.exit_code == 0
        assert Path(out, "agent-aibom.json").exists()


def test_export_csv():
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "output")
        result = runner.invoke(app, ["export", d, "-f", "csv", "-d", out, "--store-dir", d])
        assert result.exit_code == 0
        assert Path(out, "agent-aibom.csv").exists()


def test_export_sarif():
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "output")
        result = runner.invoke(app, ["export", d, "-f", "sarif", "-d", out, "--store-dir", d])
        assert result.exit_code == 0
        sarif_path = Path(out, "agent-aibom.sarif")
        assert sarif_path.exists()
        data = json.loads(sarif_path.read_text())
        assert data["version"] == "2.1.0"


def test_export_multi_format():
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "output")
        result = runner.invoke(app, ["export", d, "-f", "json,csv", "-d", out, "--store-dir", d])
        assert result.exit_code == 0
        assert Path(out, "agent-aibom.json").exists()
        assert Path(out, "agent-aibom.csv").exists()


def test_export_invalid_format():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["export", d, "-f", "xml", "-d", d])
        assert result.exit_code == 1


def test_graph_permissions():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["graph", d, "--type", "permissions", "--output", "mermaid"])
        assert result.exit_code == 0
        assert "graph TD" in result.stdout


def test_graph_delegations_dot():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["graph", d, "--type", "delegations", "--output", "dot"])
        assert result.exit_code == 0
        assert "digraph" in result.stdout


def test_graph_invalid_type():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["graph", d, "--type", "foo"])
        assert result.exit_code == 1


def test_diff_missing_boms():
    with tempfile.TemporaryDirectory() as d:
        result = runner.invoke(app, ["diff", "urn:uuid:fake1", "urn:uuid:fake2", "--store-dir", d])
        assert result.exit_code == 1


def test_diff_two_scans():
    """Scan twice and diff — should show 0 changes."""
    with tempfile.TemporaryDirectory() as d:
        store = str(Path(d) / "store")
        # First scan
        r1 = runner.invoke(app, ["scan", d, "--store-dir", store, "--quiet"])
        serial1 = r1.stdout.strip()
        # Second scan
        r2 = runner.invoke(app, ["scan", d, "--store-dir", store, "--quiet"])
        serial2 = r2.stdout.strip()

        result = runner.invoke(app, ["diff", serial1, serial2, "--store-dir", store])
        assert result.exit_code == 0
        assert "BOM Diff" in result.stdout
