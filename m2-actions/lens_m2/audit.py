"""Append-only, tamper-evident audit log for every guarded action.

One JSON object per line (JSON Lines) so it is greppable and append-safe. Every
action — accepted or rejected — is recorded; a clean rejection with a readable
reason is a first-class, audited outcome.

**Tamper-evidence:** records form a hash chain. Each line carries a monotonic
``seq``, the ``prev_hash`` of the line before it, and an ``entry_hash`` over its
own canonical content. :meth:`AuditLog.verify` recomputes the chain and detects
any edit, deletion, reordering, or insertion after the fact — the integrity
property a real audit trail needs. Each record also carries a ``correlation_id``
(see :mod:`lens_m2.obs`) so an action ties back to its request and logs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import obs

GENESIS_HASH = "0" * 64


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _digest(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


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
    correlation_id: str = field(default_factory=obs.correlation_id)


@dataclass(frozen=True)
class ChainStatus:
    ok: bool
    length: int
    problems: list[str] = field(default_factory=list)


class AuditLog:
    """JSON-lines, hash-chained audit log writer/reader."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seq, self._last_hash = self._load_tail()

    @property
    def path(self) -> Path:
        return self._path

    def _load_tail(self) -> tuple[int, str]:
        """Resume an existing chain: return (next seq, last entry_hash)."""
        last_seq, last_hash = -1, GENESIS_HASH
        if self._path.exists():
            with self._path.open(encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    last_seq = rec.get("seq", last_seq + 1)
                    last_hash = rec.get("entry_hash", last_hash)
        return last_seq + 1, last_hash

    def record(self, record: AuditRecord) -> AuditRecord:
        body = asdict(record)
        body["seq"] = self._seq
        body["prev_hash"] = self._last_hash
        entry_hash = _digest(body)
        line = {**body, "entry_hash": entry_hash}
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
        self._seq += 1
        self._last_hash = entry_hash
        return record

    def entries(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def verify(self) -> ChainStatus:
        """Recompute the hash chain; report any break (tamper/gap/reorder)."""
        problems: list[str] = []
        prev_hash = GENESIS_HASH
        rows = self.entries()
        for i, row in enumerate(rows):
            stored = row.get("entry_hash")
            body = {k: v for k, v in row.items() if k != "entry_hash"}
            if body.get("seq") != i:
                problems.append(f"row {i}: seq {body.get('seq')} out of order")
            if body.get("prev_hash") != prev_hash:
                problems.append(f"row {i}: prev_hash does not chain")
            if _digest(body) != stored:
                problems.append(f"row {i}: entry_hash mismatch (content altered)")
            prev_hash = stored or ""
        return ChainStatus(ok=not problems, length=len(rows), problems=problems)
