"""M0 CLI entry points handle a missing Fuseki gracefully (clean exit, message)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

M0 = Path(__file__).resolve().parent.parent  # m0-ontology/


def _run(args: list[str], env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=M0,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_run_money_shot_unreachable_fuseki_exits_2() -> None:
    result = _run(["scripts.run_money_shot"], {"FUSEKI_BASE_URL": "http://localhost:9"})
    assert result.returncode == 2
    assert "not reachable" in (result.stdout + result.stderr).lower()
