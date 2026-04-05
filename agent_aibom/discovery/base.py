"""Abstract base class for all discovery scanners."""

from __future__ import annotations

import abc
from pathlib import Path

from agent_aibom.core.config import ScannerOverride
from agent_aibom.core.models import AgentFramework, AgentIdentity


class AbstractScanner(abc.ABC):
    """Base class for framework-specific agent scanners."""

    def __init__(self, override: ScannerOverride | None = None) -> None:
        self.override = override or ScannerOverride()

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable scanner name."""

    @property
    @abc.abstractmethod
    def framework(self) -> AgentFramework:
        """Framework this scanner detects."""

    @abc.abstractmethod
    def scan(self, path: Path) -> list[AgentIdentity]:
        """Scan a directory tree and return discovered agents."""

    def _should_exclude(self, path: Path, default_excludes: list[str]) -> bool:
        """Check if a path matches any exclusion pattern."""
        excludes = default_excludes + self.override.extra_exclude
        path_str = str(path)
        return any(pat in path_str for pat in excludes)

    def _resolve_files(
        self, root: Path, default_globs: list[str], default_excludes: list[str],
    ) -> list[Path]:
        """Resolve files using override include_globs if set, else default_globs."""
        globs = self.override.include_globs if self.override.include_globs else default_globs
        files: list[Path] = []
        for pattern in globs:
            for f in root.glob(pattern):
                if not self._should_exclude(f, default_excludes):
                    files.append(f)
        return sorted(set(files))
