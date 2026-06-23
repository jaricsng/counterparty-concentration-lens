"""Minimal HTTP service wrapping the M4 grounded NL agent (the `agent` image).

Exposes POST /ask {question} -> the validated, read-only SPARQL answer. Kept in
m6-infra so it deploys the M4 library without adding a web dependency to M4.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from lens_m0.fuseki import FusekiRunner
from lens_m4 import agent
from pydantic import BaseModel

_PREFIX = (
    "PREFIX lens: <https://lens.example/ontology/>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
)


def _runner() -> FusekiRunner:
    base = os.environ.get("FUSEKI_BASE_URL", "http://fuseki:3030").rstrip("/")
    ds = os.environ.get("FUSEKI_DATASET", "lens")
    return FusekiRunner(query_url=f"{base}/{ds}/query", gsp_url=f"{base}/{ds}/data")


def _label_index(runner: FusekiRunner) -> dict[str, str]:
    rows = runner.select(
        _PREFIX + "SELECT ?e ?name WHERE { ?e a <https://www.omg.org/spec/Commons/Organizations/"
        "LegalEntity> ; rdfs:label ?name . FILTER NOT EXISTS { ?e lens:isSubsidiaryOf ?p } }"
    )
    index: dict[str, str] = {}
    for r in rows:
        head = (r.get("e") or "").rsplit("/", 1)[-1]
        name = (r.get("name") or "").lower()
        if name:
            index[name] = head
            index[name.split()[0]] = head
    return index


class Ask(BaseModel):
    question: str


def build_app() -> FastAPI:
    app = FastAPI(title="Lens NL Agent (M4)", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ask")
    def ask(body: Ask) -> dict[str, Any]:
        runner = _runner()
        res = agent.answer(body.question, runner, label_index=_label_index(runner))
        return {
            "answered": res.answered,
            "engine": res.engine,
            "intent": res.intent,
            "summary": res.summary,
            "sparql": res.sparql,
            "safe": res.safe,
            "rows": res.rows,
        }

    return app
