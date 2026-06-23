"""Run the money-shot concentration query against Fuseki and print the result.

Usage:
    python -m scripts.run_money_shot [GROUP_HEAD_IRI]

Defaults to the Acme group head. Prints the headline (direct vs connected,
limit breach) and the breakdown of contributing multi-hop paths.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lens_m0.concentration import Headline, breakdown, headline  # noqa: E402
from lens_m0.config import DEFAULT_GROUP_HEAD, load_settings  # noqa: E402
from lens_m0.fuseki import FusekiRunner  # noqa: E402


def _money(amount: Decimal) -> str:
    return f"SGD {amount:,.0f}"


def _print_headline(h: Headline) -> None:
    print("=" * 72)
    print(f"  COUNTERPARTY CONCENTRATION — group head: {h.group_head}")
    print("=" * 72)
    print(f"  Single-source view (loans booked to the named entity): {_money(h.direct_head_only)}")
    print(f"  Direct loans across the whole ownership group:         {_money(h.direct_group)}")
    print("  TRUE CONNECTED EXPOSURE (direct + guaranties + shared")
    print(f"     collateral, multi-hop):                             {_money(h.connected_total)}")
    print(f"  Hidden exposure the connected view reveals:            {_money(h.hidden_exposure)}")
    print("-" * 72)
    print(f"  Group credit limit:                                    {_money(h.group_limit)}")
    verdict = "** BREACH **" if h.limit_breached else "within limit"
    print(f"  Limit status on connected exposure:                    {verdict}")
    print("=" * 72)


def _print_breakdown(contribs: list) -> None:
    print("\n  Contributing paths (what no single source system sees on its own):\n")
    header = f"  {'Type':<26}{'Counterparty':<28}{'Amount':>15}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for c in contribs:
        name = c.counterparty_name or c.counterparty
        print(f"  {c.contribution_type:<26}{name:<28}{_money(c.amount):>15}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    group_head = args[0] if args else DEFAULT_GROUP_HEAD

    settings = load_settings()
    runner = FusekiRunner(query_url=settings.query_url, gsp_url=settings.gsp_url)

    ping = f"{settings.fuseki_base_url.rstrip('/')}/$/ping"
    if not runner.is_up(ping):
        print(f"Fuseki not reachable at {settings.fuseki_base_url}. Start it and load data first.")
        return 2

    h = headline(runner, settings.queries_dir, group_head)
    _print_headline(h)
    _print_breakdown(breakdown(runner, settings.queries_dir, group_head))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
