"""Evaluate the OPA/Rego authorization policy from Python.

The policy is the source of truth and lives in ``policies/authz.rego``. This
module shells out to the ``opa`` binary (``opa eval``) — it does NOT reimplement
the rules — so authorization stays external to the application code.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - fixed `opa` binary, no shell; input via stdin JSON only
from dataclasses import dataclass
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
POLICY_DIR = MODULE_ROOT / "policies"


class PolicyUnavailable(RuntimeError):
    """Raised when the OPA binary is not available to evaluate the policy."""


def opa_path() -> str | None:
    return os.environ.get("OPA_BIN") or shutil.which("opa")


@dataclass(frozen=True)
class PolicyEngine:
    """Thin wrapper over ``opa eval`` for the lens.authz policy."""

    policy_dir: Path = POLICY_DIR

    def _eval(self, query: str, input_doc: dict[str, object]) -> object:
        binary = opa_path()
        if binary is None:
            raise PolicyUnavailable("opa binary not found (install OPA or set OPA_BIN)")
        proc = subprocess.run(  # noqa: S603 # nosec B603 - fixed args, no shell; input via stdin
            [binary, "eval", "-f", "json", "-d", str(self.policy_dir), "-I", query],
            input=json.dumps(input_doc),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            raise PolicyUnavailable(f"opa eval failed: {proc.stderr.strip()[:200]}")
        payload = json.loads(proc.stdout)
        results = payload.get("result", [])
        if not results:
            return None
        return results[0]["expressions"][0]["value"]

    def visible_groups(
        self, role: str, portfolios: list[str], candidate_groups: list[str]
    ) -> set[str]:
        """The subset of ``candidate_groups`` this user may see."""
        value = self._eval(
            "data.lens.authz.visible_groups",
            {"role": role, "portfolios": portfolios, "candidate_groups": candidate_groups},
        )
        return set(value) if isinstance(value, list) else set()

    def allow(self, role: str, portfolios: list[str], group: str) -> bool:
        """Whether this user may open a single group."""
        value = self._eval(
            "data.lens.authz.allow",
            {"role": role, "portfolios": portfolios, "group": group},
        )
        return bool(value)
