# M2 actions API (guarded SHACL-validated writes). Build from the repo root:
#   docker build -f m6-infra/docker/api.Dockerfile -t lens/api:0.1.0 .
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/m2-actions \
    FUSEKI_BASE_URL=http://fuseki:3030 \
    LENS_AUDIT_LOG=/tmp/audit.jsonl

WORKDIR /app
RUN groupadd -r lens && useradd -r -g lens -d /app lens

COPY m2-actions/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt

COPY m2-actions/ ./m2-actions/

USER lens
EXPOSE 8000
CMD ["uvicorn", "--factory", "lens_m2.app:build_default_app", \
     "--host", "0.0.0.0", "--port", "8000"]
