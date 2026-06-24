# M4 grounded NL agent service. Build from the repo root:
#   docker build -f m6-infra/docker/agent.Dockerfile -t lens/agent:0.1.0 .
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/m0-ontology:/app/m4-ai \
    FUSEKI_BASE_URL=http://fuseki:3030

WORKDIR /app
RUN groupadd -r lens && useradd -r -g lens -d /app lens

COPY m4-ai/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt \
    "fastapi==0.138.0" "starlette==1.3.1" "uvicorn==0.41.0" "pydantic==2.13.0"

COPY m0-ontology/lens_m0/ ./m0-ontology/lens_m0/
COPY m4-ai/lens_m4/ ./m4-ai/lens_m4/
COPY m6-infra/docker/agent_service.py ./agent_service.py

USER lens
EXPOSE 8000
CMD ["uvicorn", "--factory", "agent_service:build_app", \
     "--host", "0.0.0.0", "--port", "8000"]
