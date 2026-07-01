"""Maker-checker (four-eyes) approval workflow for guarded state changes.

A **maker** submits a change — it does *not* take effect. A different **checker**
with authority then approves or rejects it; on approval the change runs through the
normal guarded path (validate → write → audit). Segregation of duties is enforced:
the checker must differ from the maker. Every step (submit / approve / reject) is
written to the tamper-evident audit trail.

The pending queue is in-memory for this single-process prototype (it lives on the
``ActionService`` in the cached app context). Deliberately simple — see SECURITY.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

# Roles permitted to approve a change (a maker with a lesser role cannot self-approve).
CHECKER_ROLES = frozenset({"group_risk"})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def new_pending_id() -> str:
    return "PC-" + uuid.uuid4().hex[:8]


@dataclass(frozen=True)
class PendingChange:
    id: str
    kind: str  # loan | entity | guaranty | collateral | limit
    subject_id: str
    maker: str
    maker_role: str
    status: str = "pending"  # pending | approved | rejected
    decided_by: str | None = None
    reason: str = ""
    created_at: str = field(default_factory=_now)
