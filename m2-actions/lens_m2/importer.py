"""Guarded bring-your-own-data import: validate -> per-row report -> load -> audit.

Imported records are routed through the SAME SHACL validation and audit machinery
as sandbox writes (docs/data-import.md §4). Every row is checked *before* anything
is written; the caller gets a per-row report of what was accepted or rejected and
why. Imported data replaces the active graph as a **named dataset** and never
touches the bundled calm/stressed CSVs — "reset to calm/stressed" restores them.

Default behaviour is **validate-all-then-load**: nothing is written unless every
record passes. ``allow_partial`` loads only the accepted records (exploratory).

> Synthetic / sample TEST data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# triples_map is the shared, tested row -> N-Triples transform (lenient: bad
# values become ill-typed literals that SHACL rejects, rather than crashing).
from lens_capstone.triples_map import LENSID, TABLE_MAP
from pyshacl import validate as shacl_validate
from rdflib import Graph
from rdflib.namespace import RDF, SH

from .audit import AuditLog, AuditRecord
from .store import Store
from .validation import _load_shapes

_ID_COL = {
    "entities": "entity_id",
    "loans": "loan_id",
    "guarantees": "guarantee_id",
    "collateral": "collateral_id",
    "limits": "limit_id",
}


@dataclass(frozen=True)
class ImportRecord:
    table: str
    record_id: str
    accepted: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImportReport:
    dataset_name: str
    loaded: bool
    accepted: int
    rejected: int
    triples: int
    records: list[ImportRecord]

    @property
    def total(self) -> int:
        return self.accepted + self.rejected

    def rejections(self) -> list[ImportRecord]:
        return [r for r in self.records if not r.accepted]


def _build_graph(
    rows_by_table: dict[str, list[dict[str, str]]],
) -> tuple[Graph, list[tuple[str, str]], list[ImportRecord]]:
    """Build the candidate graph; return (graph, record keys, pre-rejected rows)."""
    graph = Graph()
    keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    prerejected: list[ImportRecord] = []
    for table, rows in rows_by_table.items():
        _filename, fn = TABLE_MAP[table]
        for row in rows:
            rid = (row.get(_ID_COL[table]) or "").strip()
            if not rid:
                prerejected.append(ImportRecord(table, "(blank)", False, ["missing id"]))
                continue
            for line in fn(row):
                graph.parse(data=line, format="nt")
            key = (table, rid)
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return graph, keys, prerejected


def _violations_by_subject(graph: Graph, shapes_path: Path) -> dict[str, list[str]]:
    conforms, report, _ = shacl_validate(
        graph,
        shacl_graph=_load_shapes(str(shapes_path)),
        advanced=True,
        inference="none",
        meta_shacl=False,
    )
    out: dict[str, list[str]] = {}
    if conforms:
        return out
    for result in report.subjects(RDF.type, SH.ValidationResult):
        focus = report.value(result, SH.focusNode)
        message = report.value(result, SH.resultMessage)
        if focus is not None:
            out.setdefault(str(focus), []).append(str(message))
    return out


def import_dataset(
    rows_by_table: dict[str, list[dict[str, str]]],
    *,
    store: Store,
    audit: AuditLog,
    shapes_path: Path,
    dataset_name: str,
    actor: str = "importer",
    role: str = "group_risk",
    allow_partial: bool = False,
) -> ImportReport:
    """Validate, report, and (if permitted) load a user dataset."""
    graph, keys, prerejected = _build_graph(rows_by_table)
    violations = _violations_by_subject(graph, shapes_path)

    records: list[ImportRecord] = list(prerejected)
    accepted_subjects: set[str] = set()
    for table, rid in keys:
        iri = str(LENSID[rid])
        reasons = sorted(set(violations.get(iri, [])))
        if reasons:
            records.append(ImportRecord(table, rid, False, reasons))
        else:
            records.append(ImportRecord(table, rid, True))
            accepted_subjects.add(iri)

    accepted = sum(1 for r in records if r.accepted)
    rejected = sum(1 for r in records if not r.accepted)

    # Decide what (if anything) to load.
    if rejected == 0:
        to_load: Graph | None = graph
    elif allow_partial:
        to_load = Graph()
        for s, p, o in graph:
            if str(s) in accepted_subjects:
                to_load.add((s, p, o))
    else:
        to_load = None  # validate-all-then-load: abort the whole import

    loaded = to_load is not None
    triples = 0
    if to_load is not None:
        store.replace(to_load)
        triples = len(to_load)

    outcome = "accepted" if loaded else "rejected"
    reason = (
        f"imported '{dataset_name}': {accepted} accepted, {rejected} rejected, "
        f"{triples} triples loaded" + ("" if loaded else " (nothing written)")
    )
    audit.record(
        AuditRecord(
            "import",
            dataset_name,
            actor,
            role,
            outcome,
            reason,
            {"accepted": accepted, "rejected": rejected, "allow_partial": allow_partial},
        )
    )
    return ImportReport(dataset_name, loaded, accepted, rejected, triples, records)
