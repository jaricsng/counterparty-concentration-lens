"""PolicyEngine fails loudly when OPA is absent (no silent allow/deny).

Authorization is external to the app; if the policy engine can't be consulted the
right behaviour is to raise, not to guess. The app layer decides how to degrade.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

M3_ROOT = Path(__file__).resolve().parent.parent
if str(M3_ROOT) not in sys.path:
    sys.path.insert(0, str(M3_ROOT))

from lens_m3 import policy  # noqa: E402
from lens_m3.policy import PolicyEngine, PolicyUnavailable  # noqa: E402


def test_missing_opa_binary_raises_policy_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("OPA_BIN", raising=False)
    monkeypatch.setattr(policy.shutil, "which", lambda _name: None)
    with pytest.raises(PolicyUnavailable):
        PolicyEngine().visible_groups("group_risk", [], ["LE-0001"])
