"""Configuration for Agent AIBOM."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ScannerOverride(BaseModel):
    """Per-scanner include/exclude overrides."""
    include_globs: list[str] = Field(default_factory=list)
    extra_exclude: list[str] = Field(default_factory=list)
    enabled: bool = True


class ScanConfig(BaseModel):
    """Configuration for agent discovery scanning."""
    scan_paths: list[str] = Field(default_factory=lambda: ["."])
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules", ".venv", "venv", "__pycache__",
            ".git", ".pytest_cache", "*.egg-info", "dist", "build",
        ]
    )
    frameworks: list[str] = Field(
        default_factory=lambda: [
            "claude-code", "crewai", "langgraph", "autogen", "mcp", "generic",
        ]
    )
    max_depth: int = 10
    follow_symlinks: bool = True
    scanner_overrides: dict[str, ScannerOverride] = Field(default_factory=dict)
    store_dir: str | None = None


class RiskConfig(BaseModel):
    """Configuration for risk scoring."""
    approved_models: list[str] = Field(default_factory=list)
    approved_tools: list[str] = Field(default_factory=list)
    max_permission_scope: str = "write"
    require_owner: bool = True
    require_approval_gates: bool = True
    external_action_threshold: str = "high"
    custom_rules: list[dict[str, Any]] = Field(default_factory=list)


class ExportConfig(BaseModel):
    """Configuration for BOM export."""
    output_dir: str = "./aibom-output"
    formats: list[str] = Field(default_factory=lambda: ["json"])
    include_traces: bool = False
    include_risk: bool = True
    pretty_print: bool = True


class DashboardConfig(BaseModel):
    """Configuration for the web dashboard."""
    host: str = "127.0.0.1"
    port: int = 8200
    auto_open: bool = True


class Neo4jConfig(BaseModel):
    """Configuration for Neo4j graph database."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "agent-aibom"
    database: str = "neo4j"


class GrafanaConfig(BaseModel):
    """Configuration for Grafana integration."""
    url: str = "http://localhost:3000"
    api_key: str = ""
    dashboard_uid: str = "agent-aibom"


class APIConfig(BaseModel):
    """Configuration for the REST API server."""
    host: str = "127.0.0.1"
    port: int = 8201
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    api_key: str | None = None


class Settings(BaseModel):
    """Root settings for Agent AIBOM."""
    scan: ScanConfig = Field(default_factory=ScanConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    grafana: GrafanaConfig = Field(default_factory=GrafanaConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    @classmethod
    def from_file(cls, path: str | Path) -> Settings:
        import yaml
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    def to_file(self, path: str | Path) -> None:
        import yaml
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)

    def resolve_store_dir(self) -> Path:
        """Resolve BOM store directory: CLI flag > env var > config > default."""
        env = os.environ.get("AGENT_AIBOM_STORE_DIR")
        if self.scan.store_dir:
            return Path(self.scan.store_dir)
        if env:
            return Path(env)
        return Path.home() / ".agent-aibom" / "boms"
