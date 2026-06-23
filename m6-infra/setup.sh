#!/usr/bin/env bash
# Stand up the Lens on a local k3d cluster with OPA Gatekeeper admission control.
#
#   ./m6-infra/setup.sh            # full setup
#   ./m6-infra/setup.sh images     # just (re)build + import images
#
# Prereqs: docker, k3d, kubectl. Argo CD is optional (see ARGO=1 below).
set -euo pipefail
cd "$(dirname "$0")/.."

GK_VERSION="${GK_VERSION:-v3.22.2}"
CLUSTER="lens"

build_images() {
  echo "==> Building images"
  docker build -f m6-infra/docker/api.Dockerfile   -t lens/api:0.1.0   .
  docker build -f m6-infra/docker/agent.Dockerfile -t lens/agent:0.1.0 .
  docker build -f m6-infra/docker/app.Dockerfile   -t lens/app:0.1.0   .
  echo "==> Importing images into k3d"
  k3d image import lens/api:0.1.0 lens/agent:0.1.0 lens/app:0.1.0 -c "${CLUSTER}"
}

if [[ "${1:-all}" == "images" ]]; then
  build_images
  exit 0
fi

echo "==> Creating k3d cluster '${CLUSTER}'"
k3d cluster create --config m6-infra/k3d/cluster.yaml || echo "(cluster may already exist)"

build_images

echo "==> Installing OPA Gatekeeper ${GK_VERSION}"
kubectl apply -f \
  "https://raw.githubusercontent.com/open-policy-agent/gatekeeper/${GK_VERSION}/deploy/gatekeeper.yaml"
kubectl -n gatekeeper-system rollout status deploy/gatekeeper-controller-manager --timeout=180s

echo "==> Applying policies (ConstraintTemplates, then Constraints)"
kubectl apply -f m6-infra/policies/templates/
sleep 5  # let the generated Constraint CRDs register
kubectl apply -f m6-infra/policies/constraints/

echo "==> Deploying the Lens workloads"
kubectl apply -k m6-infra/k8s/
kubectl -n lens-demo rollout status deploy/app --timeout=180s || true

if [[ "${ARGO:-0}" == "1" ]]; then
  echo "==> Installing Argo CD"
  kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
  kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=240s
  echo "    Set repoURL in m6-infra/argocd/*.yaml to your fork, then:"
  echo "    kubectl apply -f m6-infra/argocd/"
fi

cat <<'EOF'

==> Done.
  App:    http://localhost:8501   (Streamlit)
  Verify admission control:
    kubectl apply -f m6-infra/examples/bad-privileged-pod.yaml   # -> DENIED by Gatekeeper
  Inspect:
    kubectl -n lens-demo get pods
    kubectl get constraints
EOF
