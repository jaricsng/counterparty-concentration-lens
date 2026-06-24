"""The Ollama engine path (mocked): safe output is used; unsafe never executes.

The other agent tests force ``allow_ollama=False`` (template engine). These cover
the LLM branch: a valid generated query is used, and anything unsafe or empty is
discarded in favour of the deterministic template — the LLM can never run an
update or an out-of-schema query against the store. We use the (cheap) wrong-way-
risk question so the assertions are about engine selection, not query cost.
"""

from __future__ import annotations

import pytest
from lens_m0.graph import GraphRunner
from lens_m4 import nl2sparql, ollama
from lens_m4.agent import answer

LABEL_INDEX = {"acme": "LE-0001", "helios": "LE-0010", "vortex": "LE-0020", "nimbus": "LE-0030"}
Q = "show me any wrong-way risk"


@pytest.fixture
def ollama_up(monkeypatch):
    monkeypatch.setattr(ollama, "is_available", lambda: True)


def test_safe_ollama_query_is_used(runner: GraphRunner, ollama_up, monkeypatch) -> None:
    safe = nl2sparql.generate(Q, LABEL_INDEX).sparql
    monkeypatch.setattr(ollama, "generate", lambda _q: safe)
    res = answer(Q, runner, label_index=LABEL_INDEX)
    assert res.engine == "ollama"  # the LLM query was accepted and used
    assert res.answered
    assert res.sparql == safe
    assert len(res.rows) == 1  # executed against the live graph (one WWR on stressed)


def test_unsafe_ollama_output_falls_back_to_template(runner, ollama_up, monkeypatch) -> None:
    monkeypatch.setattr(ollama, "generate", lambda _q: "DELETE WHERE { ?s ?p ?o }")
    res = answer(Q, runner, label_index=LABEL_INDEX)
    assert res.engine == "template"  # the unsafe query is discarded, not executed
    assert res.answered
    assert "DELETE" not in res.sparql


def test_empty_ollama_output_falls_back_to_template(runner, ollama_up, monkeypatch) -> None:
    monkeypatch.setattr(ollama, "generate", lambda _q: None)
    res = answer(Q, runner, label_index=LABEL_INDEX)
    assert res.engine == "template"
    assert res.answered


def test_unsafe_query_is_rejected_and_never_reaches_the_store(monkeypatch) -> None:
    # Defense in depth: an unsafe query is refused before execution.
    monkeypatch.setattr(
        nl2sparql, "generate", lambda *a, **k: nl2sparql.NLQuery(Q, "x", "template", "DROP DEFAULT")
    )

    class _NoRun:
        def select(self, _q):
            raise AssertionError("an unsafe query must never reach the store")

    res = answer(Q, _NoRun(), label_index=LABEL_INDEX, allow_ollama=False)
    assert not res.answered
    assert not res.safe
    assert "rejected by the safety check" in res.summary
