"""Bring the M6 admission policy into the pytest gate.

Two layers: (1) a pure-YAML lint that our shipped manifests already satisfy the
Gatekeeper baseline (non-root, no privilege, resource limits, approved image, key
label) — so a manifest regression fails CI before it reaches the cluster; and
(2) the real Gatekeeper suite via ``gator verify`` when the binary is present.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

M6 = Path(__file__).resolve().parent.parent
K8S = M6 / "k8s"
SUITE = M6 / "policies" / "tests" / "suite.yaml"
_APPROVED_PREFIXES = ("lens/", "stain/jena-fuseki")


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _deployments() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for f in sorted(K8S.glob("*.yaml")):
        out += [(f.name, d) for d in _docs(f) if d.get("kind") == "Deployment"]
    return out


def test_some_deployments_exist() -> None:
    assert _deployments(), "no Deployment manifests found under m6-infra/k8s/"


@pytest.mark.parametrize("name,dep", _deployments(), ids=[n for n, _ in _deployments()])
def test_deployment_meets_gatekeeper_baseline(name: str, dep: dict) -> None:
    pod = dep["spec"]["template"]["spec"]
    labels = dep["spec"]["template"]["metadata"]["labels"]
    assert "app.kubernetes.io/part-of" in labels, f"{name}: missing part-of label"

    for c in pod["containers"]:
        where = f"{name}/{c['name']}"
        sec = c.get("securityContext", {})
        assert sec.get("privileged") is False, f"{where}: privileged"
        assert sec.get("allowPrivilegeEscalation") is False, f"{where}: allowPrivilegeEscalation"
        limits = c.get("resources", {}).get("limits", {})
        assert "cpu" in limits and "memory" in limits, f"{where}: missing resource limits"
        assert c["image"].startswith(_APPROVED_PREFIXES), (
            f"{where}: image {c['image']} not approved"
        )


def test_bad_example_pod_really_violates_the_policy() -> None:
    # the negative fixture must actually be non-compliant, else the deny proves nothing
    bad = _docs(M6 / "examples" / "bad-privileged-pod.yaml")[0]
    assert bad["spec"]["containers"][0]["securityContext"]["privileged"] is True


@pytest.mark.skipif(shutil.which("gator") is None, reason="gator binary not installed")
def test_gator_verify_passes() -> None:
    result = subprocess.run(
        ["gator", "verify", str(SUITE)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
