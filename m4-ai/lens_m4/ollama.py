"""Optional local Ollama backend for NL -> SPARQL.

Used only when a local Ollama server is reachable; otherwise the deterministic
template generator handles the question. Whatever Ollama returns is held to the
same safety bar as any other generated SPARQL.
"""

from __future__ import annotations

import os
import re

import requests

_SCHEMA = """You translate questions into a single SPARQL SELECT query over this schema.
Prefixes:
  lens:   <https://lens.example/ontology/>
  lensid: <https://lens.example/id/>
  rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
Classes/properties:
  a legal entity (cmns-org:LegalEntity) has rdfs:label, lens:sector,
    lens:counterpartyType, lens:isSubsidiaryOf (-> parent), lens:status.
  a loan (fibo loan) has lens:borrower, lens:lender, lens:principalAmount, lens:status.
  a guaranty has lens:guarantor, lens:guaranteedLoan, lens:guaranteedAmount, lens:status.
  collateral has lens:pledgedBy, lens:securesLoan, lens:collateralIssuer, lens:status.
  a lens:Limit has lens:limitAmount; entities link via lens:hasLimit.
Rules: output ONLY a read-only SELECT query, no INSERT/DELETE/SERVICE, only these prefixes."""

_CODE_RE = re.compile(r"```(?:sparql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def base_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def model() -> str:
    return os.environ.get("OLLAMA_MODEL", "llama3.2")


def is_available() -> bool:
    if os.environ.get("LENS_DISABLE_OLLAMA"):
        return False
    try:
        return requests.get(f"{base_url()}/api/tags", timeout=2).ok
    except requests.RequestException:
        return False


def _extract_sparql(text: str) -> str | None:
    m = _CODE_RE.search(text)
    candidate = (m.group(1) if m else text).strip()
    upper = candidate.upper()
    if "SELECT" in upper or "ASK" in upper:
        return candidate
    return None


def generate(question: str) -> str | None:
    """Ask the local model for a SPARQL query, or None if unavailable/unusable."""
    if not is_available():
        return None
    prompt = f"{_SCHEMA}\n\nQuestion: {question}\nSPARQL:"
    try:
        resp = requests.post(
            f"{base_url()}/api/generate",
            json={"model": model(), "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None
    return _extract_sparql(resp.json().get("response", ""))
