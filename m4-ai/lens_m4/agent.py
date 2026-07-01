"""Grounded NL query agent: generate -> safety-check -> execute -> scope -> summarise.

The single entry point the app calls. It never executes SPARQL that fails the
safety check, and applies the M3 visible-group scope to row results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from lens_m1.credit_risk import CAPITAL_RATIO, expected_loss, rw_for

from . import nl2sparql, ollama
from .safety import is_safe


class Runner(Protocol):
    def select(self, query: str) -> list[dict[str, str | None]]: ...


# Dedicated-collateral mitigant per counterparty (mirrors lens_m2.derived); used
# to net EAD before applying the credit_risk parameters in the computed intents.
_MITIGANT_Q = (
    "PREFIX lens: <https://lens.example/ontology/>\n"
    "SELECT ?cp (SUM(?elig) AS ?mit) WHERE {\n"
    "  { SELECT ?col (SAMPLE(?b) AS ?cp) (SAMPLE(?val) AS ?v) (SAMPLE(?hc) AS ?h)\n"
    "           (COUNT(DISTINCT ?b) AS ?nb) WHERE {\n"
    "    ?col lens:collateralValue ?val ; lens:haircut ?hc ; lens:securesLoan ?l ;\n"
    '         lens:status "active" .\n'
    '    ?l lens:borrower ?b ; lens:status "active" .\n'
    "  } GROUP BY ?col } FILTER(?nb = 1) BIND(?v * (1 - ?h) AS ?elig)\n"
    "} GROUP BY ?cp"
)


def _credit_risk_rows(runner: Runner, gross_query: str) -> list[dict[str, str | None]]:
    """Per-borrower net EAD / EL / capital, computed with the credit_risk parameters.

    EAD = gross - dedicated collateral mitigant; EL/capital via lens_m1.credit_risk.
    Computed (not pure SPARQL) because PD / risk-weight are parametric.
    """
    mit = {_local(r.get("cp")): Decimal(r.get("mit") or 0) for r in runner.select(_MITIGANT_Q)}
    rows: list[dict[str, str | None]] = []
    for r in runner.select(gross_query):
        cp = _local(r.get("cp"))
        rating = r.get("rating")
        ead = max(Decimal(0), Decimal(r.get("gross") or 0) - mit.get(cp, Decimal(0)))
        rows.append(
            {
                "entity": cp,
                "name": r.get("name"),
                "rating": rating or "unrated",
                "ead": str(ead),
                "el": str(expected_loss(ead, rating)),
                "capital": str(CAPITAL_RATIO * rw_for(rating) * ead),
            }
        )
    return sorted(rows, key=lambda x: Decimal(x["el"] or "0"), reverse=True)


def _stress_rows(scenario_key: str) -> list[dict[str, str | None]]:
    """Per-counterparty expected-loss base vs shocked for a named scenario.

    A computed what-if on the bundled 'stressed' base (the agent has no session
    dataset). Uses the lens_m1 scenario engine; clearly framed as a what-if.
    """
    from lens_m1 import datasets, scenarios

    spec = datasets.get_dataset("stressed")
    label = scenarios.SCENARIOS.get(scenario_key, scenarios.SCENARIOS["base"]).label
    return [
        {
            "entity": d.entity,
            "rating": f"{d.rating_base}->{d.rating_shocked}",
            "el_base": str(d.el_base),
            "el_shocked": str(d.el_shocked),
            "delta": str(d.delta),
            "scenario": label,
        }
        for d in scenarios.expected_loss_deltas(spec, scenario_key)
    ]


def _xva_rows() -> list[dict[str, str | None]]:
    """Per-counterparty PFE / EPE / CVA on the stressed base (analytical, illustrative)."""
    from lens_m1 import datasets, xva

    spec = datasets.get_dataset("stressed")
    return [
        {
            "entity": r.entity,
            "rating": r.rating,
            "ead": str(r.ead),
            "peak_pfe": str(r.peak_pfe),
            "epe": str(r.epe),
            "cva": str(r.cva),
        }
        for r in xva.portfolio_xva(spec)
    ]


def _general_wwr_rows() -> list[dict[str, str | None]]:
    """General (correlation-proxy) wrong-way risk on the stressed base."""
    from lens_m1 import datasets, metrics

    spec = datasets.get_dataset("stressed")
    return [
        {"loan": f["loan"], "borrower": f["borrower"], "issuer": f["issuer"], "driver": f["driver"]}
        for f in metrics.general_wwr_flags(spec)
    ]


def _reverse_stress_rows(preset: str) -> list[dict[str, str | None]]:
    """Mildest shock reaching a target outcome, on the stressed base (deterministic search)."""
    from decimal import Decimal

    from lens_m1 import datasets
    from lens_m1 import reverse_stress as rs

    spec = datasets.get_dataset("stressed")
    if preset == "capital":
        r = rs.min_shock(spec, "capital_pct_eligible", Decimal("0.15"))
    elif preset == "breaches":
        r = rs.min_shock(spec, "limit_breaches", Decimal(6))
    else:
        r = rs.multiplier_target(spec, "expected_loss", 2.0)
    return [
        {
            "metric": rs.METRIC_LABELS[r.metric],
            "shock": r.shock_label,
            "base": str(r.base_value),
            "achieved": str(r.achieved),
            "feasible": str(r.feasible),
        }
    ]


def _macro_rows(scenario_key: str) -> list[dict[str, str | None]]:
    """Per-sector macro-stress EL impact on the stressed base (correlated factor model)."""
    from lens_m1 import datasets, macro

    spec = datasets.get_dataset("stressed")
    label = macro.MACRO_SCENARIOS.get(scenario_key, macro.MACRO_SCENARIOS["recession"]).label
    base, shocked = macro.compare(spec, scenario_key)
    return [
        {
            "sector": si.sector,
            "notches": str(si.notches),
            "el_base": str(si.el_base),
            "el_shocked": str(si.el_shocked),
            "delta": str(si.delta),
            "scenario": label,
            "total_base": str(base.total_el),
            "total_shocked": str(shocked.total_el),
        }
        for si in macro.sector_impacts(spec, scenario_key)
    ]


def _xva_full_rows() -> list[dict[str, str | None]]:
    """Full xVA breakdown (CVA/DVA/FVA/MVA/KVA + total) on the stressed base."""
    from lens_m1 import datasets, xva

    spec = datasets.get_dataset("stressed")
    return [
        {
            "entity": r.entity,
            "rating": r.rating,
            "cva": str(r.cva),
            "dva": str(r.dva),
            "fva": str(r.fva),
            "mva": str(r.mva),
            "kva": str(r.kva),
            "total": str(r.total_xva),
        }
        for r in xva.portfolio_xva_breakdown(spec)
    ]


def _contagion_rows() -> list[dict[str, str | None]]:
    """Systemic default-cascade ranking on the stressed base (deterministic two-hop)."""
    from lens_m1 import contagion, datasets

    spec = datasets.get_dataset("stressed")
    return [
        {
            "entity": c.seed,
            "direct": str(c.direct_loss),
            "contagion": str(c.contagion_loss),
            "total": str(c.total_loss),
            "amplification": f"{float(c.amplification):.1f}",
        }
        for c in contagion.systemic_ranking(spec)
    ]


def _contagion_multiround_rows() -> list[dict[str, str | None]]:
    """Multi-round (fire-sale) cascade ranking on the stressed base."""
    from lens_m1 import contagion, datasets

    spec = datasets.get_dataset("stressed")
    return [
        {
            "entity": r.seed,
            "rounds": str(r.rounds),
            "defaulted": str(r.defaulted),
            "second_order": str(r.second_order),
            "firesale": str(r.firesale_haircut),
            "total": str(r.total_loss),
        }
        for r in contagion.systemic_ranking_multiround(spec)
    ]


def _ifrs9_rows() -> list[dict[str, str | None]]:
    """Per-counterparty IFRS-9 stage + recognised ECL on the stressed base (simplified)."""
    from lens_m1 import datasets, ifrs9

    spec = datasets.get_dataset("stressed")
    return [
        {
            "entity": r.entity,
            "rating": r.rating,
            "stage": str(r.stage),
            "ecl_12m": str(r.ecl_12m),
            "ecl_lifetime": str(r.ecl_lifetime),
            "ecl": str(r.ecl_recognised),
        }
        for r in ifrs9.portfolio_ecl(spec)
    ]


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answered: bool
    engine: str  # template | ollama | none
    intent: str
    sparql: str
    summary: str
    rows: list[dict[str, str | None]] = field(default_factory=list)
    safe: bool = True


def _local(iri: str | None) -> str:
    return iri.rsplit("/", 1)[-1] if iri else ""


def _scope_rows(
    rows: list[dict[str, str | None]],
    visible_groups: set[str] | None,
    member_to_head: dict[str, str] | None,
) -> list[dict[str, str | None]]:
    """Drop rows whose entity/owner is not in the caller's visible group set."""
    if visible_groups is None:
        return rows
    member_to_head = member_to_head or {}
    kept = []
    for row in rows:
        ids = [_local(row.get(k)) for k in ("owner", "entity", "head") if row.get(k)]
        heads = {member_to_head.get(i, i) for i in ids}
        if not ids or heads & visible_groups:
            kept.append(row)
    return kept


def _money(value: str | None) -> str:
    return f"SGD {Decimal(value or 0) / 1_000_000:.1f}M"


def _summarise(intent: str, rows: list[dict[str, str | None]], params: dict[str, str]) -> str:
    if intent == "exposure_to_group":
        connected = rows[0].get("connected") if rows else "0"
        return f"Connected exposure to {params.get('group', 'the group')}: {_money(connected)}."
    if intent == "top_counterparties":
        names_amounts = ", ".join(
            f"{r.get('ownerName') or _local(r.get('owner'))} ({_money(r.get('exposure'))})"
            for r in rows[:3]
        )
        if not rows:
            return "No exposures."
        return f"Top counterparties by connected exposure: {names_amounts}."
    if intent == "near_limit":
        if not rows:
            return "None near limit."
        near = ", ".join(r.get("entityName") or _local(r.get("entity")) for r in rows)
        return f"{len(rows)} name(s) at/above the threshold: {near}."
    if intent == "guarantee_chains":
        return f"{len(rows)} guarantee(s) touch this group." if rows else "No guarantees found."
    if intent == "sector_concentration":
        sector_total = sum((Decimal(r.get("exposure") or 0) for r in rows), Decimal(0))
        top_sector = max(rows, key=lambda r: Decimal(r.get("exposure") or 0)) if rows else None
        if top_sector is not None and sector_total:
            share = float(Decimal(top_sector.get("exposure") or 0) / sector_total) * 100
            name = top_sector.get("sector")
            return f"Largest sector: {name} at {share:.0f}% of connected exposure."
        return "No sector data."
    if intent in ("country_concentration", "rating_concentration"):
        dim = "country" if intent == "country_concentration" else "rating"
        total = sum((Decimal(r.get("exposure") or 0) for r in rows), Decimal(0))
        top = max(rows, key=lambda r: Decimal(r.get("exposure") or 0)) if rows else None
        if top is not None and total:
            share = float(Decimal(top.get("exposure") or 0) / total) * 100
            return f"Largest {dim}: {top.get(dim)} at {share:.0f}% of connected exposure."
        return f"No {dim} data."
    if intent == "wrong_way_risk":
        return (
            f"{len(rows)} structural wrong-way-risk flag(s)."
            if rows
            else "No wrong-way-risk flags."
        )
    if intent == "net_exposure":
        if not rows:
            return "No counterparties have eligible collateral."
        top = rows[0]
        name = top.get("entityName") or "a counterparty"
        return (
            f"{len(rows)} name(s) collateralised. Largest net (post-collateral): "
            f"{name} {_money(top.get('gross'))} gross -> {_money(top.get('net'))} net."
        )
    if intent == "expected_loss":
        if not rows:
            return "No exposures."
        total = sum((Decimal(r.get("el") or 0) for r in rows), Decimal(0))
        top = rows[0]
        return (
            f"Total expected loss: {_money(str(total))}. Largest contributor: "
            f"{top.get('name')} ({top.get('rating')}) at {_money(top.get('el'))}."
        )
    if intent == "capital":
        if not rows:
            return "No exposures."
        total = sum((Decimal(r.get("capital") or 0) for r in rows), Decimal(0))
        return f"Total capital (8% of RWA): {_money(str(total))} across {len(rows)} counterparties."
    if intent == "stress":
        if not rows:
            return "No scenario impact."
        base = sum((Decimal(r.get("el_base") or 0) for r in rows), Decimal(0))
        shocked = sum((Decimal(r.get("el_shocked") or 0) for r in rows), Decimal(0))
        top = max(rows, key=lambda r: Decimal(r.get("delta") or 0))
        label = rows[0].get("scenario") or "Scenario"
        return (
            f"{label} (stressed base): expected loss "
            f"{_money(str(base))} -> {_money(str(shocked))}. "
            f"Biggest mover: {top.get('entity')} ({top.get('rating')})."
        )
    if intent == "xva":
        if not rows:
            return "No exposures."
        total = sum((Decimal(r.get("cva") or 0) for r in rows), Decimal(0))
        top = max(rows, key=lambda r: Decimal(r.get("cva") or 0))
        return (
            f"Total CVA (stressed base): {_money(str(total))}. Largest: "
            f"{top.get('entity')} ({top.get('rating')}) {_money(top.get('cva'))}, "
            f"peak PFE {_money(top.get('peak_pfe'))}."
        )
    if intent == "ifrs9":
        if not rows:
            return "No exposures."
        total = sum((Decimal(r.get("ecl") or 0) for r in rows), Decimal(0))
        stage2 = sum(1 for r in rows if r.get("stage") == "2")
        stage3 = sum(1 for r in rows if r.get("stage") == "3")
        return (
            f"Total recognised ECL (stressed base): {_money(str(total))}. "
            f"Stage 2: {stage2} names, Stage 3: {stage3} (lifetime ECL)."
        )
    if intent == "general_wwr":
        if not rows:
            return "No general (correlation-proxy) wrong-way risk found."
        top = rows[0]
        return (
            f"{len(rows)} general wrong-way-risk flag(s) — e.g. loan {top.get('loan')}: "
            f"collateral issuer {top.get('issuer')} shares the borrower's "
            f"{top.get('driver')} (different group)."
        )
    if intent == "reverse_stress":
        if not rows:
            return "No exposures."
        r = rows[0]
        return f"Mildest shock to reach that {r.get('metric')} target: {r.get('shock')}."
    if intent == "macro":
        if not rows:
            return "No exposures."
        label = rows[0].get("scenario") or "Macro scenario"
        base_total = rows[0].get("total_base")
        shocked_total = rows[0].get("total_shocked")
        top = max(rows, key=lambda r: Decimal(r.get("delta") or 0))
        return (
            f"{label} (stressed base): expected loss {_money(base_total)} -> "
            f"{_money(shocked_total)}. Hardest-hit sector: {top.get('sector')} "
            f"(−{top.get('notches')} notches)."
        )
    if intent == "xva_full":
        if not rows:
            return "No exposures."
        tot = sum((Decimal(r.get("total") or 0) for r in rows), Decimal(0))
        cva = sum((Decimal(r.get("cva") or 0) for r in rows), Decimal(0))
        fva = sum((Decimal(r.get("fva") or 0) for r in rows), Decimal(0))
        kva = sum((Decimal(r.get("kva") or 0) for r in rows), Decimal(0))
        return (
            f"Portfolio total xVA (stressed base): {_money(str(tot))} "
            f"(CVA {_money(str(cva))}, FVA {_money(str(fva))}, KVA {_money(str(kva))})."
        )
    if intent == "contagion_multiround":
        if not rows:
            return "No exposures."
        top = rows[0]  # ranking sorted by total loss desc
        return (
            f"Worst multi-round cascade (stressed base): {top.get('entity')} — "
            f"{top.get('rounds')} rounds, {top.get('defaulted')} defaulted "
            f"({top.get('second_order')} second-order), loss {_money(top.get('total'))} "
            f"(fire-sale haircut {top.get('firesale')})."
        )
    if intent == "contagion":
        if not rows:
            return "No exposures."
        top = rows[0]  # ranking is sorted by total loss desc
        return (
            f"Most systemic (stressed base): {top.get('entity')} — direct "
            f"{_money(top.get('direct'))}, total {_money(top.get('total'))} "
            f"(×{top.get('amplification')} via guarantee contagion)."
        )
    return f"{len(rows)} row(s)."


def answer(
    question: str,
    runner: Runner,
    *,
    label_index: dict[str, str] | None = None,
    visible_groups: set[str] | None = None,
    member_to_head: dict[str, str] | None = None,
    allow_ollama: bool = True,
) -> AnswerResult:
    """Answer a natural-language question, read-only and role-scoped."""
    nlq = None
    if allow_ollama and ollama.is_available():
        sparql = ollama.generate(question)
        if sparql and is_safe(sparql).safe:
            nlq = nl2sparql.NLQuery(question, "ollama", "ollama", sparql)
    if nlq is None:
        nlq = nl2sparql.generate(question, label_index)
    if nlq is None:
        return AnswerResult(
            question,
            False,
            "none",
            "unsupported",
            "",
            "I can answer questions about: exposure to a group · top counterparties · names "
            "near their limit · guarantee chains · sector / country / rating concentration · "
            "wrong-way risk · net (post-collateral) exposure · expected loss · regulatory "
            "capital · IFRS-9 ECL & staging · PFE / CVA / total xVA · stress & macro scenarios "
            "· systemic contagion (incl. multi-round fire-sale cascade). "
            "Try: 'what is our total expected loss?' or 'what happens in a property crash?'",
        )

    safety = is_safe(nlq.sparql)
    if not safety.safe:
        return AnswerResult(
            question,
            False,
            nlq.engine,
            nlq.intent,
            nlq.sparql,
            f"Generated query rejected by the safety check: {safety.reason}.",
            safe=False,
        )

    if nlq.intent == "general_wwr":
        raw = _general_wwr_rows()
    elif nlq.intent == "reverse_stress":
        raw = _reverse_stress_rows(nlq.params.get("preset", "double_el"))
    elif nlq.intent == "macro":
        raw = _macro_rows(nlq.params.get("scenario", "recession"))
    elif nlq.intent == "stress":
        raw = _stress_rows(nlq.params.get("scenario", "broad_downgrade"))
    elif nlq.intent == "xva":
        raw = _xva_rows()
    elif nlq.intent == "xva_full":
        raw = _xva_full_rows()
    elif nlq.intent == "ifrs9":
        raw = _ifrs9_rows()
    elif nlq.intent == "contagion":
        raw = _contagion_rows()
    elif nlq.intent == "contagion_multiround":
        raw = _contagion_multiround_rows()
    elif nlq.intent in ("expected_loss", "capital"):
        # Computed intents: PD / risk-weight are parametric (not pure SPARQL).
        raw = _credit_risk_rows(runner, nlq.sparql)
    else:
        raw = runner.select(nlq.sparql)
    rows = _scope_rows(raw, visible_groups, member_to_head)
    return AnswerResult(
        question,
        True,
        nlq.engine,
        nlq.intent,
        nlq.sparql,
        _summarise(nlq.intent, rows, nlq.params),
        rows=rows,
    )
