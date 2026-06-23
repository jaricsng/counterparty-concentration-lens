"""Append-only audit log for every guarded action (who / what / when / result).

One JSON object per line (JSON Lines) so it is greppable and append-safe. Every
action — accepted or rejected — is recorded; a clean rejection with a readable
reason is a first-class, audited outcome.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class AuditRecord:
    action: str
    target: str
    actor: str
    role: str
    outcome: str  # accepted | rejected
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_now)


class AuditLog:
    """JSON-lines audit log writer/reader."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, record: AuditRecord) -> AuditRecord:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), sort_keys=True) + "\n")
        return record

    def entries(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
