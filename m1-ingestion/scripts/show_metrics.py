"""Print the engineered calm-vs-stressed concentration numbers (design proof).

This is the plain-Python oracle view of the metrics — the same values M0's
SPARQL queries are validated against in the next step. It reads the in-memory
dataset specs, not Fuseki.

Usage:
    python -m scripts.show_metrics
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lens_m1 import metrics as M  # noqa: E402
from lens_m1.datasets import get_dataset  # noqa: E402


def _pct(x: Decimal) -> str:
    return f"{float(x) * 100:5.1f}%"


def _m(x: Decimal) -> str:
    return f"SGD {float(x) / 1e6:.1f}M"


def _show(name: str) -> None:
    spec = get_dataset(name)
    av = M.attributed_vector(spec)
    dv = M.direct_vector(spec)
    util = M.utilisations(spec)
    print("=" * 70)
    print(f"  {name.upper()} — {spec.description}")
    print("=" * 70)
    print(
        f"  Entities: {len(spec.entities)}   Loans: {len(spec.loans)}   "
        f"Guarantees: {len(spec.guarantees)}   Collateral: {len(spec.collateral)}"
    )
    print("  Portfolio concentration (risk-owner attribution):")
    print(
        f"    HHI   connected={float(M.hhi(av)):.3f}  direct={float(M.hhi(dv)):.3f}  (>0.18 high)"
    )
    print(f"    CR10  connected={_pct(M.cr10(av))} direct={_pct(M.cr10(dv))}  (>60% = high)")
    top = sorted(M.sector_shares(spec).items(), key=lambda kv: kv[1], reverse=True)[:3]
    print("    sectors: " + ", ".join(f"{s}={_pct(v)}" for s, v in top))
    print("  Single-name watchlist (connected exposure vs limit):")
    flagged = [u for u in util if u.band != "green"]
    if not flagged:
        print("    (all names green — within normal bands)")
    for u in flagged:
        print(
            f"    [{u.band.upper():5}] {spec.entity(u.name).name[:30]:30} "
            f"{_m(u.connected)} / {_m(u.limit)} = {_pct(u.ratio)}"
        )
    acme = M.connected_exposure(spec, "LE-0001")
    nim = M.connected_exposure(spec, "LE-0030")
    ubo = M.subsidiary_breach_check(spec, "LE-0020")
    wwr = M.wrong_way_risk_flags(spec)
    print("  Engineered cases:")
    print(f"    Hidden breach (Acme):   direct {_m(acme.direct)} -> connected {_m(acme.total)}")
    print(f"    NBFI cascade (Nimbus):  direct {_m(nim.direct)} -> connected {_m(nim.total)}")
    print(
        f"    UBO breach (Vortex):    connected {_m(Decimal(str(ubo['ubo_connected'])))} "
        f"vs limit {_m(Decimal(str(ubo['ubo_limit'])))}  breach={ubo['ubo_breaches']}  "
        f"sub-breaches={ubo['subsidiary_breaches']}"
    )
    print(
        f"    Structural WWR flags:   {len(wwr)} "
        + (
            f"({wwr[0]['loan']}: {wwr[0]['collateral']} issued by {wwr[0]['issuer']})"
            if wwr
            else ""
        )
    )
    print()


def main() -> int:
    for name in ("calm", "stressed"):
        _show(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
