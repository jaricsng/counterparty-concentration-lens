"""Deterministic natural-language -> SPARQL generator (grounded in the schema).

Maps a question to one of a fixed set of intents and emits SPARQL over the known
lens vocabulary. Offline and deterministic, so the demo always works; an optional
local Ollama model (see :mod:`lens_m4.ollama`) can be tried first, but its output
is held to the same safety bar. The generated SPARQL is returned for
transparency and must pass :func:`lens_m4.safety.is_safe` before execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PREFIXES = (
    "PREFIX lens: <https://lens.example/ontology/>\n"
    "PREFIX lensid: <https://lens.example/id/>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
)


def _q(body: str) -> str:
    """Prepend the standard prefixes to a query body."""
    return _PREFIXES + body


# Connected exposure for one group head (status-aware; __HEAD__ = a group id).
_EXPOSURE_TO_GROUP = """SELECT (COALESCE(SUM(?amt), 0) AS ?connected) WHERE {
  SELECT DISTINCT ?src ?amt WHERE {
    VALUES ?head { lensid:__HEAD__ }
    { ?src lens:borrower ?m ; lens:principalAmount ?amt ; lens:status "active" .
      ?m lens:isSubsidiaryOf* ?head . }
    UNION
    { ?src lens:guarantor ?m ; lens:guaranteedAmount ?amt ; lens:guaranteedLoan ?gl ;
           lens:status "active" . ?gl lens:borrower ?gb ; lens:status "active" .
      ?m lens:isSubsidiaryOf* ?head . FILTER NOT EXISTS { ?gb lens:isSubsidiaryOf* ?head } }
    UNION
    { ?col lens:securesLoan ?ml , ?src ; lens:status "active" .
      ?ml lens:borrower ?mb ; lens:status "active" . ?mb lens:isSubsidiaryOf* ?head .
      FILTER(?ml != ?src) ?src lens:borrower ?eb ; lens:status "active" .
      FILTER NOT EXISTS { ?eb lens:isSubsidiaryOf* ?head } ?src lens:principalAmount ?amt . }
  }
}"""

# Top connected counterparties by risk-owner attribution.
_TOP_COUNTERPARTIES = """SELECT ?owner ?ownerName (SUM(?amt) AS ?exposure) WHERE {
  ?loan lens:borrower ?b ; lens:principalAmount ?amt ; lens:status "active" .
  ?b lens:isSubsidiaryOf* ?bubo . FILTER NOT EXISTS { ?bubo lens:isSubsidiaryOf ?bp }
  OPTIONAL { ?g lens:guaranteedLoan ?loan ; lens:guarantor ?gtor .
    ?gtor lens:isSubsidiaryOf* ?gubo . FILTER NOT EXISTS { ?gubo lens:isSubsidiaryOf ?gp }
    FILTER(?gubo != ?bubo) }
  BIND(COALESCE(?gubo, ?bubo) AS ?owner)
  OPTIONAL { ?owner rdfs:label ?ownerName }
} GROUP BY ?owner ?ownerName ORDER BY DESC(?exposure) LIMIT 10"""

# Names whose connected utilisation is at/above a threshold (__THRESHOLD__).
_NEAR_LIMIT = """SELECT ?entity ?entityName ?connected ?limit WHERE {
  ?entity lens:hasLimit/lens:limitAmount ?limit .
  OPTIONAL { ?entity rdfs:label ?entityName }
  { SELECT ?entity (SUM(?contrib) AS ?connected) WHERE {
      SELECT DISTINCT ?entity ?src ?contrib WHERE {
        ?entity lens:hasLimit ?anyLimit .
        { ?m lens:isSubsidiaryOf* ?entity .
          ?src lens:borrower ?m ; lens:principalAmount ?contrib ; lens:status "active" . }
        UNION { ?m lens:isSubsidiaryOf* ?entity .
          ?src lens:guarantor ?m ; lens:guaranteedAmount ?contrib ; lens:guaranteedLoan ?gl .
          ?gl lens:borrower ?gb . FILTER NOT EXISTS { ?gb lens:isSubsidiaryOf* ?entity } }
      } } GROUP BY ?entity }
  FILTER(?connected >= __THRESHOLD__ * ?limit)
} ORDER BY DESC(?connected / ?limit)"""

# Guarantees touching a group (as guarantor or as the guaranteed borrower).
_GUARANTEE_CHAINS = """SELECT ?guaranty ?guarantorName ?borrowerName ?amount WHERE {
  VALUES ?head { lensid:__HEAD__ }
  ?guaranty lens:guarantor ?gtor ; lens:guaranteedLoan ?loan ; lens:guaranteedAmount ?amount ;
            lens:status "active" .
  ?loan lens:borrower ?b .
  { ?gtor lens:isSubsidiaryOf* ?head } UNION { ?b lens:isSubsidiaryOf* ?head }
  OPTIONAL { ?gtor rdfs:label ?guarantorName }
  OPTIONAL { ?b rdfs:label ?borrowerName }
}"""

_SECTOR = """SELECT ?sector (SUM(?amt) AS ?exposure) WHERE {
  ?loan lens:borrower ?b ; lens:principalAmount ?amt ; lens:status "active" .
  ?b lens:isSubsidiaryOf* ?bubo . FILTER NOT EXISTS { ?bubo lens:isSubsidiaryOf ?bp }
  OPTIONAL { ?g lens:guaranteedLoan ?loan ; lens:guarantor ?gtor .
    ?gtor lens:isSubsidiaryOf* ?gubo . FILTER NOT EXISTS { ?gubo lens:isSubsidiaryOf ?gp }
    FILTER(?gubo != ?bubo) }
  BIND(COALESCE(?gubo, ?bubo) AS ?owner) ?owner lens:sector ?sector .
} GROUP BY ?sector ORDER BY DESC(?exposure)"""

# Country / rating concentration — same risk-owner attribution as _SECTOR.
_COUNTRY = """SELECT ?country (SUM(?amt) AS ?exposure) WHERE {
  ?loan lens:borrower ?b ; lens:principalAmount ?amt ; lens:status "active" .
  ?b lens:isSubsidiaryOf* ?bubo . FILTER NOT EXISTS { ?bubo lens:isSubsidiaryOf ?bp }
  OPTIONAL { ?g lens:guaranteedLoan ?loan ; lens:guarantor ?gtor .
    ?gtor lens:isSubsidiaryOf* ?gubo . FILTER NOT EXISTS { ?gubo lens:isSubsidiaryOf ?gp }
    FILTER(?gubo != ?bubo) }
  BIND(COALESCE(?gubo, ?bubo) AS ?owner) ?owner lens:country ?country .
} GROUP BY ?country ORDER BY DESC(?exposure)"""

_RATING = """SELECT ?rating (SUM(?amt) AS ?exposure) WHERE {
  ?loan lens:borrower ?b ; lens:principalAmount ?amt ; lens:status "active" .
  ?b lens:isSubsidiaryOf* ?bubo . FILTER NOT EXISTS { ?bubo lens:isSubsidiaryOf ?bp }
  OPTIONAL { ?g lens:guaranteedLoan ?loan ; lens:guarantor ?gtor .
    ?gtor lens:isSubsidiaryOf* ?gubo . FILTER NOT EXISTS { ?gubo lens:isSubsidiaryOf ?gp }
    FILTER(?gubo != ?bubo) }
  BIND(COALESCE(?gubo, ?bubo) AS ?owner) ?owner lens:rating ?rating .
} GROUP BY ?rating ORDER BY DESC(?exposure)"""

# Credit-risk (EAD/EL/capital) is a COMPUTED intent: this representative query
# returns per-borrower gross exposure + rating; the agent nets collateral and
# applies the credit_risk PD / risk-weight parameters (see lens_m1.credit_risk).
_CREDIT = """SELECT ?cp ?name ?rating (SUM(?amt) AS ?gross) WHERE {
  ?ln lens:borrower ?cp ; lens:principalAmount ?amt ; lens:status "active" .
  OPTIONAL { ?cp rdfs:label ?name }
  OPTIONAL { ?cp lens:rating ?rating }
} GROUP BY ?cp ?name ?rating ORDER BY DESC(?gross)"""

_WWR = """SELECT ?loan ?borrowerName ?issuerName WHERE {
  ?collateral lens:collateralIssuer ?issuer ; lens:securesLoan ?loan ; lens:status "active" .
  ?loan lens:borrower ?borrower ; lens:status "active" .
  ?borrower lens:isSubsidiaryOf* ?group . FILTER NOT EXISTS { ?group lens:isSubsidiaryOf ?p }
  ?issuer lens:isSubsidiaryOf* ?group .
  OPTIONAL { ?borrower rdfs:label ?borrowerName }
  OPTIONAL { ?issuer rdfs:label ?issuerName }
}"""

# Net (post-credit-risk-mitigation) exposure: gross minus dedicated collateral
# (counted once, post-haircut). Mirrors lens_m2.derived.net_exposures.
_NET_EXPOSURE = """SELECT ?entityName ?gross ?mitigant (?gross - ?mitigant AS ?net) WHERE {
  { SELECT ?cp (SUM(?elig) AS ?mitigant) WHERE {
      { SELECT ?col (SAMPLE(?b) AS ?cp) (SAMPLE(?val) AS ?v) (SAMPLE(?hc) AS ?h)
               (COUNT(DISTINCT ?b) AS ?nb) WHERE {
          ?col lens:collateralValue ?val ; lens:haircut ?hc ;
               lens:securesLoan ?l ; lens:status "active" .
          ?l lens:borrower ?b ; lens:status "active" .
      } GROUP BY ?col }
      FILTER(?nb = 1)
      BIND(?v * (1 - ?h) AS ?elig)
  } GROUP BY ?cp }
  { SELECT ?cp (SUM(?amt) AS ?gross) WHERE {
      ?ln lens:borrower ?cp ; lens:principalAmount ?amt ; lens:status "active" .
  } GROUP BY ?cp }
  ?cp rdfs:label ?entityName .
} ORDER BY DESC(?net)"""


@dataclass(frozen=True)
class NLQuery:
    question: str
    intent: str
    engine: str  # template | ollama
    sparql: str
    params: dict[str, str] = field(default_factory=dict)


def _resolve_group(question: str, label_index: dict[str, str]) -> str | None:
    """Find the first known group name mentioned in the question."""
    q = question.lower()
    for name in sorted(label_index, key=len, reverse=True):
        if name and name in q:
            return label_index[name]
    return None


def _threshold(question: str) -> str:
    """Extract a percentage threshold; default 75% (the amber band)."""
    m = re.search(r"(\d{1,3})\s*%", question)
    if m:
        return str(int(m.group(1)) / 100)
    return "0.75"


def generate(question: str, label_index: dict[str, str] | None = None) -> NLQuery | None:
    """Map a question to a grounded SPARQL query (template engine)."""
    label_index = label_index or {}
    q = question.lower()

    if any(w in q for w in ("wrong-way", "wrong way", "same issuer", "same-issuer")):
        return NLQuery(question, "wrong_way_risk", "template", _q(_WWR))

    if "sector" in q:
        return NLQuery(question, "sector_concentration", "template", _q(_SECTOR))

    if any(w in q for w in ("country", "countries", "geograph", "jurisdiction")):
        return NLQuery(question, "country_concentration", "template", _q(_COUNTRY))

    # Capital keywords are specific phrases (bare "capital" collides with entity
    # names like "Nimbus Capital Partners").
    _capital_kw = (
        "rwa",
        "risk-weight",
        "risk weight",
        "risk-weighted",
        "regulatory capital",
        "capital requirement",
        "capital ratio",
        "capital charge",
        "how much capital",
    )
    _el_kw = ("expected loss", "ecl", "provision")
    if any(w in q for w in _capital_kw + _el_kw):
        intent = "capital" if any(w in q for w in _capital_kw) else "expected_loss"
        return NLQuery(question, intent, "template", _q(_CREDIT))

    if any(w in q for w in ("rating", "grade", "investment grade", "credit quality")):
        return NLQuery(question, "rating_concentration", "template", _q(_RATING))

    if (
        any(w in q for w in ("within", "near", "approaching", "close to", "watchlist"))
        and "limit" in q
    ):
        thr = _threshold(question)
        return NLQuery(
            question,
            "near_limit",
            "template",
            _q(_NEAR_LIMIT.replace("__THRESHOLD__", thr)),
            {"threshold": thr},
        )

    if any(
        w in q
        for w in (
            "net exposure",
            "post-collateral",
            "after collateral",
            "collateral",
            "netting",
            "mitigant",
            "post-crm",
        )
    ):
        return NLQuery(question, "net_exposure", "template", _q(_NET_EXPOSURE))

    if any(w in q for w in ("top", "largest", "biggest")):
        return NLQuery(question, "top_counterparties", "template", _q(_TOP_COUNTERPARTIES))

    if "guarantee" in q or "guaranty" in q or "chain" in q:
        head = _resolve_group(question, label_index)
        if head:
            return NLQuery(
                question,
                "guarantee_chains",
                "template",
                _q(_GUARANTEE_CHAINS.replace("__HEAD__", head)),
                {"group": head},
            )

    if "exposure" in q or "exposed" in q:
        head = _resolve_group(question, label_index)
        if head:
            return NLQuery(
                question,
                "exposure_to_group",
                "template",
                _q(_EXPOSURE_TO_GROUP.replace("__HEAD__", head)),
                {"group": head},
            )

    return None
