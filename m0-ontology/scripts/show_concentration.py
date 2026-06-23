"""Print all concentration metrics for the dataset currently loaded in Fuseki.

Run the M1 loader first to choose the dataset, e.g.:
    (cd ../m1-ingestion && python -m scripts.load_data --dataset stressed)
    python -m scripts.show_concentration
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lens_m0 import metrics_queries as Q  # noqa: E402
from lens_m0.config import load_settings  # noqa: E402
from lens_m0.fuseki import FusekiRunner  # noqa: E402


def _pct(x: Decimal) -> str:
    return f"{float(x) * 100:5.1f}%"


def _m(x: Decimal) -> str:
    return f"SGD {float(x) / 1e6:4.0f}M"


def main() -> int:
    s = load_settings()
    runner = FusekiRunner(query_url=s.query_url, gsp_url=s.gsp_url)
    ping = f"{s.fuseki_base_url.rstrip('/')}/$/ping"
    if not runner.is_up(ping):
        print(f"Fuseki not reachable at {s.fuseki_base_url}. Load a dataset first.")
        return 2

    hhi = Q.hhi(runner, s.queries_dir)
    cr10 = Q.cr10(runner, s.queries_dir)
    print("=" * 68)
    print("  PORTFOLIO CONCENTRATION (direct vs connected)")
    print("=" * 68)
    print(
        f"  HHI    direct={float(hhi.direct):.3f}   "
        f"connected={float(hhi.connected):.3f}   (>0.18 high)"
    )
    print(f"  CR10   direct={_pct(cr10.direct)}  connected={_pct(cr10.connected)}  (>60% high)")

    print("\n  Sector concentration (risk-owner attribution, >30% flagged):")
    for sector, share in sorted(
        Q.sector_shares(runner, s.queries_dir).items(), key=lambda kv: kv[1], reverse=True
    ):
        flag = "  <== concentrated" if share > Decimal("0.30") else ""
        print(f"    {sector:28} {_pct(share)}{flag}")

    print("\n  Single-name watchlist (connected exposure vs limit):")
    for r in Q.watchlist(runner, s.queries_dir):
        if r.band != "green":
            name = r.entity_name or r.entity
            print(
                f"    [{r.band.upper():5}] {name[:30]:30} "
                f"{_m(r.connected)} / {_m(r.limit)} = {_pct(r.utilisation)}"
            )

    print("\n  UBO aggregation (from a subsidiary -> ultimate parent):")
    for r in Q.ubo_aggregation(runner, s.queries_dir):
        tag = "UBO" if r.is_ubo else "sub"
        name = r.member_name or r.member
        print(f"    [{tag}] {name[:30]:30} {_m(r.connected)} / {_m(r.limit)} [{r.band}]")

    print("\n  NBFI cascade (second-order exposure if the NBFI fails):")
    cascade = Q.nbfi_cascade(runner, s.queries_dir)
    total = sum((c.amount for c in cascade), Decimal(0))
    for c in cascade:
        name = c.counterparty_name or c.counterparty
        print(f"    {c.contribution_type:22} {name[:26]:26} {_m(c.amount)}")
    print(f"    {'TOTAL cascade-connected':22} {'':26} {_m(total)}")

    print("\n  Structural wrong-way risk (same-issuer collateral):")
    flags = Q.wrong_way_risk(runner, s.queries_dir)
    if not flags:
        print("    (none)")
    for f in flags:
        print(
            f"    loan {f.loan}: collateral {f.collateral} issued by "
            f"{f.issuer_name or f.issuer} (same group {f.group} as borrower)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
