"""Demo users and their portfolio assignments (synthetic).

Maps each demo principal to a role and, for relationship managers, the
counterparty groups (by ultimate-parent id) they manage. The app's role selector
uses this so the same "show exposures" view returns different result sets per
user — the M3 demo point.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    name: str
    role: str  # group_risk | relationship_manager
    portfolios: list[str] = field(default_factory=list)  # group head ids


# Group heads: LE-0001 Acme, LE-0010 Helios, LE-0020 Vortex, LE-0030 Nimbus, …
DEMO_USERS: dict[str, Principal] = {
    "Dana — Group Risk": Principal("Dana", "group_risk"),
    "Bob — RM, Property desk": Principal(
        "Bob",
        "relationship_manager",
        ["LE-0001", "LE-0010"],  # Acme, Helios
    ),
    "Carol — RM, Funds desk": Principal(
        "Carol",
        "relationship_manager",
        ["LE-0020", "LE-0030"],  # Vortex, Nimbus
    ),
}

DEFAULT_USER = "Dana — Group Risk"
