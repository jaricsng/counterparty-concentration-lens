"""M1 CLI entry points: argparse + graceful failure, run as a user would.

Exercised via subprocess so a regression in argument parsing, exit codes, or the
"Fuseki not reachable" path is caught (the library logic is tested elsewhere).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

M1 = Path(__file__).resolve().parent.parent  # m1-ingestion/
REPO = M1.parent


def _run(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=M1,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_generate_data_is_reproducible() -> None:
    # regenerating the committed datasets must be a no-op (determinism guard)
    result = _run(["scripts.generate_data"])
    assert result.returncode == 0
    diff = subprocess.run(
        ["git", "diff", "--quiet", "--", "m1-ingestion/data"], cwd=REPO, check=False
    )
    assert diff.returncode == 0, "generated data drifted from the committed CSVs"


def test_show_metrics_runs_without_fuseki() -> None:
    assert _run(["scripts.show_metrics"]).returncode == 0


def test_load_data_unreachable_fuseki_exits_2() -> None:
    result = _run(
        ["scripts.load_data", "--dataset", "calm"], {"FUSEKI_BASE_URL": "http://localhost:9"}
    )
    assert result.returncode == 2


def test_load_data_rejects_unknown_dataset() -> None:
    assert _run(["scripts.load_data", "--dataset", "bogus"]).returncode == 2
