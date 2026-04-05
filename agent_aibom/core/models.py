"""Core Pydantic models for Agentic AI Bill of Materials."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class AgentFramework(str, Enum):
    CLAUDE_CODE = "claude-code"
    CREWAI = "crewai"
    LANGGRAPH = "langgraph"
    AUTOGEN = "autogen"
    SEMANTIC_KERNEL = "semantic-kernel"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class ToolType(str, Enum):
    MCP = "mcp"
    API = "api"
    CLI = "cli"
    DATABASE = "database"
    FILE_SYSTEM = "file-system"
    BROWSER = "browser"
    CODE_EXECUTION = "code-execution"
    CUSTOM = "custom"


class PermissionScope(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"
    NETWORK = "network"
    FULL = "full"


class RiskSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RiskCategory(str, Enum):
    EXCESSIVE_PERMISSIONS = "excessive-permissions"
    MISSING_APPROVAL_GATE = "missing-approval-gate"
    UNAPPROVED_MODEL = "unapproved-model"
    UNAPPROVED_TOOL = "unapproved-tool"
    NO_OWNER = "no-owner"
    EXTERNAL_ACTION = "external-action"
    DATA_EXFILTRATION = "data-exfiltration"
    PROMPT_INJECTION = "prompt-injection"
    UNBOUNDED_DELEGATION = "unbounded-delegation"
    MISSING_TRACE = "missing-trace"
    STALE_DEPENDENCY = "stale-dependency"
    SECRET_EXPOSURE = "secret-exposure"


class ExportFormat(str, Enum):
    JSON = "json"
    CYCLONEDX = "cyclonedx"
    SPDX = "spdx"
    SARIF = "sarif"
    MERMAID = "mermaid"
    DOT = "dot"
    CSV = "csv"


# --- Core Components ---

class Tool(BaseModel):
    """A tool or capability available to an agent."""
    name: str
    description: str = ""
    tool_type: ToolType = ToolType.CUSTOM
    endpoint: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    external: bool = False
    requires_approval: bool = False
    tags: list[str] = Field(default_factory=list)


class Permission(BaseModel):
    """A permission scope granted to an agent."""
    resource: str
    scopes: list[PermissionScope]
    conditions: dict[str, Any] = Field(default_factory=dict)
    granted_by: str | None = None
    expires_at: datetime | None = None


class MemoryStore(BaseModel):
    """A memory or knowledge store used by an agent."""
    name: str
    store_type: str  # e.g., "vector-db", "sqlite", "redis", "file-system"
    location: str = ""
    persistent: bool = True
    shared_with: list[str] = Field(default_factory=list)
    contains_pii: bool = False
    retention_days: int | None = None


class ApprovalGate(BaseModel):
    """An approval gate or checkpoint in agent workflow."""
    name: str
    gate_type: str  # e.g., "human-in-loop", "policy-check", "budget-limit"
    required: bool = True
    approvers: list[str] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)


class DelegationLink(BaseModel):
    """A delegation relationship between agents."""
    from_agent: str
    to_agent: str
    delegation_type: str  # e.g., "spawn", "route", "escalate", "collaborate"
    tools_delegated: list[str] = Field(default_factory=list)
    permissions_inherited: bool = False
    max_depth: int | None = None


class ModelBinding(BaseModel):
    """An LLM model binding for an agent."""
    provider: str  # e.g., "anthropic", "openai", "google", "ollama"
    model_id: str  # e.g., "claude-opus-4-6", "gpt-4o"
    version: str | None = None
    endpoint: str | None = None
    approved: bool = True
    cost_per_1k_tokens: float | None = None


class Dependency(BaseModel):
    """A software dependency used by the agent."""
    name: str
    version: str | None = None
    package_manager: str = ""  # pip, npm, cargo, etc.
    license: str | None = None
    cve_ids: list[str] = Field(default_factory=list)


# --- Agent Identity ---

class AgentIdentity(BaseModel):
    """Complete identity record for a single agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    version: str = "1.0.0"
    framework: AgentFramework = AgentFramework.UNKNOWN
    owner: str | None = None
    team: str | None = None
    source_file: str | None = None
    repository: str | None = None

    # What this agent is for
    role: str = ""
    goal: str = ""
    backstory: str = ""

    # What it can do
    tools: list[Tool] = Field(default_factory=list)
    permissions: list[Permission] = Field(default_factory=list)
    models: list[ModelBinding] = Field(default_factory=list)

    # What it remembers
    memory_stores: list[MemoryStore] = Field(default_factory=list)

    # How it's governed
    approval_gates: list[ApprovalGate] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)

    # What it depends on
    dependencies: list[Dependency] = Field(default_factory=list)
    delegations: list[DelegationLink] = Field(default_factory=list)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self.tools]

    @property
    def external_tools(self) -> list[Tool]:
        return [t for t in self.tools if t.external]

    @property
    def has_external_actions(self) -> bool:
        return any(t.external for t in self.tools)

    @property
    def has_owner(self) -> bool:
        return self.owner is not None and self.owner.strip() != ""


# --- Risk ---

class FindingSource(str, Enum):
    STATIC_ANALYSIS = "static-analysis"
    HEURISTIC = "heuristic"
    RUNTIME = "runtime"
    POLICY = "policy"
    MANUAL = "manual"


class RiskFinding(BaseModel):
    """A single risk finding for an agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    agent_name: str
    category: RiskCategory
    severity: RiskSeverity
    title: str
    description: str
    evidence: str = ""
    recommendation: str = ""
    source: FindingSource = FindingSource.STATIC_ANALYSIS
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_file: str | None = None
    source_line: int | None = None
    cwe_id: str | None = None
    owasp_ref: str | None = None
    auto_fixable: bool = False


class RiskScore(BaseModel):
    """Aggregate risk score for an agent or BOM."""
    overall: float = Field(ge=0.0, le=10.0)
    breakdown: dict[str, float] = Field(default_factory=dict)
    findings_count: dict[RiskSeverity, int] = Field(default_factory=dict)
    grade: str = ""  # A, B, C, D, F

    @staticmethod
    def compute_grade(score: float) -> str:
        if score <= 2.0:
            return "A"
        elif score <= 4.0:
            return "B"
        elif score <= 6.0:
            return "C"
        elif score <= 8.0:
            return "D"
        return "F"


# --- Runtime Traces ---

class RuntimeTrace(BaseModel):
    """A single runtime execution trace."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    agent_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    tool_used: str | None = None
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: float | None = None
    success: bool = True
    error: str | None = None
    parent_trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- The BOM ---

class BOMMetadata(BaseModel):
    """Metadata for the Agentic AI BOM."""
    bom_version: str = "1.0.0"
    spec_version: str = "1.0.0"
    serial_number: str = Field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generator: str = "agent-aibom"
    generator_version: str = "1.0.0"
    repository: str | None = None
    branch: str | None = None
    commit_sha: str | None = None


class AgenticBOM(BaseModel):
    """The complete Agentic AI Bill of Materials."""
    metadata: BOMMetadata = Field(default_factory=BOMMetadata)
    agents: list[AgentIdentity] = Field(default_factory=list)
    delegations: list[DelegationLink] = Field(default_factory=list)
    risk_findings: list[RiskFinding] = Field(default_factory=list)
    risk_score: RiskScore | None = None
    runtime_traces: list[RuntimeTrace] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)

    @property
    def agent_count(self) -> int:
        return len(self.agents)

    @property
    def tool_count(self) -> int:
        return sum(len(a.tools) for a in self.agents)

    @property
    def agents_without_owners(self) -> list[AgentIdentity]:
        return [a for a in self.agents if not a.has_owner]

    @property
    def agents_with_external_actions(self) -> list[AgentIdentity]:
        return [a for a in self.agents if a.has_external_actions]

    @property
    def critical_findings(self) -> list[RiskFinding]:
        return [f for f in self.risk_findings if f.severity == RiskSeverity.CRITICAL]

    def get_agent(self, name: str) -> AgentIdentity | None:
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def summary(self) -> dict[str, Any]:
        return {
            "serial_number": self.metadata.serial_number,
            "generated_at": self.metadata.generated_at.isoformat(),
            "repository": self.metadata.repository,
            "agent_count": self.agent_count,
            "tool_count": self.tool_count,
            "delegation_count": len(self.delegations),
            "agents_without_owners": len(self.agents_without_owners),
            "agents_with_external_actions": len(self.agents_with_external_actions),
            "risk_score": self.risk_score.overall if self.risk_score else None,
            "risk_grade": self.risk_score.grade if self.risk_score else None,
            "findings": {
                "critical": len([f for f in self.risk_findings if f.severity == RiskSeverity.CRITICAL]),
                "high": len([f for f in self.risk_findings if f.severity == RiskSeverity.HIGH]),
                "medium": len([f for f in self.risk_findings if f.severity == RiskSeverity.MEDIUM]),
                "low": len([f for f in self.risk_findings if f.severity == RiskSeverity.LOW]),
                "info": len([f for f in self.risk_findings if f.severity == RiskSeverity.INFO]),
            },
        }
