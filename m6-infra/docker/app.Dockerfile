# M5 Streamlit demo app. Build from the repo root:
#   docker build -f m6-infra/docker/app.Dockerfile -t lens/app:0.1.0 .
#
# Bundles the `opa` binary so the M3 policy (role scoping) works in-cluster.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/m0-ontology:/app/m1-ingestion:/app/m2-actions:/app/m3-security:/app/m4-ai:/app/m5-app \
    FUSEKI_BASE_URL=http://fuseki:3030 \
    LENS_AUDIT_LOG=/tmp/audit.jsonl \
    OPA_BIN=/usr/local/bin/opa

WORKDIR /app
RUN groupadd -r lens && useradd -r -g lens -d /app lens

# OPA static binary for the M3 authorization policy.
ARG OPA_VERSION=v1.17.1
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL -o /usr/local/bin/opa \
       "https://openpolicyagent.org/downloads/${OPA_VERSION}/opa_linux_amd64_static" \
    && chmod +x /usr/local/bin/opa \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY m5-app/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt "pyshacl==0.30.1"

COPY m0-ontology/lens_m0/ ./m0-ontology/lens_m0/
COPY m1-ingestion/lens_m1/ ./m1-ingestion/lens_m1/
COPY m2-actions/lens_m2/ ./m2-actions/lens_m2/
COPY m3-security/ ./m3-security/
COPY m4-ai/lens_m4/ ./m4-ai/lens_m4/
COPY m5-app/ ./m5-app/

USER lens
EXPOSE 8501
CMD ["streamlit", "run", "m5-app/streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
