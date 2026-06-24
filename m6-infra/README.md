# M6 — Infra & delivery (k3d + Argo CD + OPA Gatekeeper)

Containerises the Lens, deploys it to a local **k3d** cluster via **Argo CD**
(GitOps), and enforces **policy-as-code at admission** with **OPA Gatekeeper** —
the same OPA engine used for application authorization in M3.

> Learning prototype on synthetic data. Production-shaped, not production-hardened.

## What's here

```
m6-infra/
├── docker/                # api (M2) · agent (M4) · app (M5) Dockerfiles (+ agent_service.py); Fuseki = official image
├── k8s/                   # namespace + fuseki/api/agent/app Deployments+Services (all policy-COMPLIANT) + kustomization
├── policies/
│   ├── templates/         # Gatekeeper ConstraintTemplates (disallow-privileged, require-limits, allowed-repos, required-labels)
│   ├── constraints/       # the Constraints (deny; audit-first note inside)
│   └── tests/             # gator verify Suite (pass/fail fixtures)
├── argocd/                # Argo CD Applications (workloads + policies)
├── k3d/cluster.yaml       # local cluster config
├── examples/              # a deliberately non-compliant pod (admission demo)
├── tests/                 # pytest: manifest-baseline lint + `gator verify` (runs in the CI integration job)
└── setup.sh               # one-shot: cluster + images + Gatekeeper + policies + workloads (+ Argo)
```

## Policy as code (the headline)

Four admission policies, version-controlled and **unit-tested** with `gator`
(no cluster needed):

| Policy | Rejects |
|---|---|
| `K8sDisallowPrivileged` | privileged containers |
| `K8sContainerLimits` | containers without cpu+memory limits |
| `K8sAllowedRepos` | images not from an approved repo |
| `K8sRequiredLabels` | workloads missing `app.kubernetes.io/part-of` |

```bash
gator verify m6-infra/policies/tests/suite.yaml     # 8 cases (4 policies × pass/fail)
# evaluate manifests directly:
gator test -f m6-infra/k8s/40-app.yaml -f m6-infra/policies/templates -f m6-infra/policies/constraints   # -> no violations
gator test -f m6-infra/examples/bad-privileged-pod.yaml -f m6-infra/policies/templates -f m6-infra/policies/constraints  # -> 5 violations
```

Constraints ship as `enforcementAction: deny`. **Production rollout** should
start at `dryrun` (audit), clear existing violations, then flip to `deny`.

## Run locally

```bash
./m6-infra/setup.sh           # k3d cluster + build/import images + Gatekeeper + policies + workloads
# open http://localhost:8501  (the Streamlit app)

# prove admission control rejects a non-compliant workload:
kubectl apply -f m6-infra/examples/bad-privileged-pod.yaml   # -> denied by Gatekeeper
kubectl -n lens-demo get pods
kubectl get constraints
```

## GitOps (Argo CD)

```bash
ARGO=1 ./m6-infra/setup.sh                    # also installs Argo CD
# point spec.source.repoURL in m6-infra/argocd/*.yaml at your fork, then:
kubectl apply -f m6-infra/argocd/             # lens-app (workloads) + lens-policies (Gatekeeper)
```

A commit to `m6-infra/k8s` (or `m6-infra/policies`) then triggers Argo CD to
reconcile the cluster to match Git — Synced/Healthy.

## CI (DevSecOps)

`.github/workflows/ci.yml`:
- the **integration** job installs `gator` (alongside Fuseki + OPA) and runs the
  M6 pytest checks — a YAML lint asserting every Deployment meets the admission
  baseline (non-root, no privilege, resource limits, approved image, key label),
  plus `gator verify` over the Suite.
- the **container-scan** job — builds the API image, **Trivy** scans it
  (CRITICAL/HIGH, report-only for a prototype), generates a **CycloneDX SBOM**
  and uploads it as an artifact.

## Verify (M6 gates)

- `gator verify` passes (8/8); compliant manifests yield no violations and the
  rogue pod is rejected by all four constraints.
- Images build; Trivy scan + CycloneDX SBOM produced.
- On the cluster: pods run; a privileged/non-compliant manifest is **denied** at
  admission; Argo CD shows Synced/Healthy and reconciles on commit.
- Engineering gates green (ruff/black/mypy/bandit on `agent_service.py`).

> **Honesty:** the scans, policies and SBOM demonstrate the *practice*. This
> remains a synthetic-data learning prototype — production-shaped, not
> production-hardened.
