"""BOM registry — local persistence for scan results."""

from __future__ import annotations

import json
import os
from pathlib import Path

from agent_aibom.core.models import AgenticBOM


def _default_store_dir() -> Path:
    env = os.environ.get("AGENT_AIBOM_STORE_DIR")
    if env:
        return Path(env)
    return Path.home() / ".agent-aibom" / "boms"


class BOMRegistry:
    """Persist, list, load, diff, and delete BOMs as JSON files."""

    def __init__(self, store_dir: Path | str | None = None) -> None:
        self.store_dir = Path(store_dir) if store_dir else _default_store_dir()
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, serial: str) -> Path:
        safe = serial.replace(":", "_").replace("/", "_")
        return self.store_dir / f"{safe}.json"

    @staticmethod
    def _is_file_path(ref: str) -> bool:
        """Heuristic: contains '/' or ends with '.json' → file path, else serial."""
        return "/" in ref or ref.endswith(".json")

    def save(self, bom: AgenticBOM) -> Path:
        """Save a BOM to disk. Returns the file path."""
        path = self._path_for(bom.metadata.serial_number)
        data = bom.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    def load(self, ref: str) -> AgenticBOM:
        """Load a BOM by serial number or file path."""
        if self._is_file_path(ref):
            p = Path(ref)
            if not p.exists():
                raise FileNotFoundError(f"BOM file not found: {ref}")
            data = json.loads(p.read_text())
            return AgenticBOM.model_validate(data)
        path = self._path_for(ref)
        if not path.exists():
            raise FileNotFoundError(f"BOM not found in registry: {ref}")
        data = json.loads(path.read_text())
        return AgenticBOM.model_validate(data)

    def list_boms(self) -> list[dict[str, str]]:
        """List all stored BOMs with summary info."""
        results: list[dict[str, str]] = []
        for f in sorted(self.store_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                meta = data.get("metadata", {})
                results.append({
                    "serial_number": meta.get("serial_number", f.stem),
                    "generated_at": meta.get("generated_at", ""),
                    "repository": meta.get("repository", ""),
                    "agent_count": str(len(data.get("agents", []))),
                    "file": str(f),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def delete(self, serial: str) -> bool:
        """Delete a stored BOM. Returns True if deleted."""
        path = self._path_for(serial)
        if path.exists():
            path.unlink()
            return True
        return False

    def diff(self, serial_a: str, serial_b: str) -> dict:
        """Compare two BOMs and return differences."""
        bom_a = self.load(serial_a)
        bom_b = self.load(serial_b)

        agents_a = {a.name for a in bom_a.agents}
        agents_b = {a.name for a in bom_b.agents}

        added = agents_b - agents_a
        removed = agents_a - agents_b
        common = agents_a & agents_b

        changed: list[dict[str, str]] = []
        for name in sorted(common):
            a = bom_a.get_agent(name)
            b = bom_b.get_agent(name)
            if a and b:
                diffs: list[str] = []
                if set(a.tool_names) != set(b.tool_names):
                    diffs.append(f"tools: {a.tool_names} → {b.tool_names}")
                if len(a.permissions) != len(b.permissions):
                    diffs.append(f"permissions: {len(a.permissions)} → {len(b.permissions)}")
                if len(a.delegations) != len(b.delegations):
                    diffs.append(f"delegations: {len(a.delegations)} → {len(b.delegations)}")
                if diffs:
                    changed.append({"agent": name, "changes": "; ".join(diffs)})

        return {
            "bom_a": serial_a,
            "bom_b": serial_b,
            "added": sorted(added),
            "removed": sorted(removed),
            "changed": changed,
            "summary": f"+{len(added)} -{len(removed)} ~{len(changed)} agents",
        }
