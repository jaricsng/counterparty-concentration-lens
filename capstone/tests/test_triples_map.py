"""The Spark job's row->triples transform produces output IDENTICAL to M1.

Runs the pure mapping (no Spark) over the generated CSVs and proves the
resulting RDF graph equals the M1 loader's (``lens_m1.rdfize``) — so the Spark
job, which applies the same transform per partition, emits the same triples.
The live Spark run is verified separately via capstone/run_spark.sh.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from lens_capstone.triples_map import TABLE_MAP
from lens_m1 import csv_tables, rdfize
from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "m1-ingestion" / "data"


def _mapped_graph(dataset_dir: Path) -> Graph:
    lines: list[str] = []
    for _table, (filename, fn) in TABLE_MAP.items():
        with (dataset_dir / filename).open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                lines.extend(fn(row))
    g = Graph()
    g.parse(data="\n".join(lines), format="nt")
    return g


@pytest.mark.parametrize("variant", ["calm", "stressed"])
def test_spark_transform_matches_m1(variant: str) -> None:
    dataset_dir = DATA / variant
    mapped = _mapped_graph(dataset_dir)
    spec = csv_tables.read_dataset(dataset_dir, variant)
    canonical = rdfize.build_graph(spec)
    assert set(mapped) == set(canonical)


def test_shared_collateral_triples_dedupe(stressed_dir: Path = DATA / "stressed") -> None:
    # COL-3001 secures two loans (two CSV rows); collateral-level triples must
    # not duplicate in the RDF set.
    g = _mapped_graph(stressed_dir)
    from rdflib import Namespace, URIRef

    lens = Namespace("https://lens.example/ontology/")
    col = URIRef("https://lens.example/id/COL-3001")
    secures = list(g.objects(col, lens.securesLoan))
    assert len(secures) == 2  # both loans
    assert len(list(g.objects(col, lens.pledgedBy))) == 1  # not duplicated
