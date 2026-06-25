"""The engineered synthetic datasets: ``calm`` and ``stressed``.

Same 30-entity roster in both; only the exposures (loans / guarantees /
collateral) differ. The STRESSED variant is deliberately engineered to breach
the concentration thresholds in docs/concentration-metrics.md §4 / §9; the CALM
variant rebalances the same names so every metric sits in a normal band. Limits
express risk appetite and are identical in both variants — only exposure moves.
Synthetic, fictional names only.

Engineered cases (stressed):
  1. Hidden single-name breach  — Acme group (LE-0001): direct ~20% of capital,
     connected ~34% (guarantee + shared collateral) -> breaches the 25% limit.
  2. Skewed HHI / CR10          — connected (risk-owner) concentration breaches
     while direct-only stays acceptable.
  3. Sector concentration       — financial services > 30% (the NBFI cluster).
  4. NBFI cascade               — Nimbus (LE-0030): direct 5M, connected ~47M.
  5. Structural wrong-way risk  — Helios Power loan vs a Helios Holdings bond.
  6. UBO aggregation breach     — Vortex group (LE-0020): 3 subs, none breaching
     its own limit, but the UBO total breaches the group limit.
  7. Amber watchlist            — Helios + the three Vortex subs sit at 75-100%.
"""

from __future__ import annotations

from .spec import Collateral, DatasetSpec, Entity, Guarantee, Limit, Loan

BANK = "LE-0099"
BANK_CAPITAL = 100_000_000  # single-name limit basis: 25% = SGD 25M

CRE = "commercial real estate"
ENERGY = "energy"
TECH = "technology"
FIN = "financial services"
GOV = "government"
HEALTH = "healthcare"
INDUS = "industrials"
TRANSPORT = "transport & logistics"
CONSUMER = "consumer"

# --------------------------------------------------------------------------- #
#  Shared entity roster (identical across variants)
# --------------------------------------------------------------------------- #

ENTITIES: list[Entity] = [
    Entity(BANK, "Lender Bank Pte Ltd", "bank", FIN, eligible_capital=BANK_CAPITAL),
    # Acme group — CRE — hidden single-name breach + 3-level UBO chain
    Entity("LE-0001", "Acme Holdings Pte Ltd", "corporate", CRE, annual_revenue=80_000_000),
    Entity("LE-0002", "Acme Trading Pte Ltd", "corporate", CRE, parent_id="LE-0001"),
    Entity("LE-0003", "Acme Capital SPV Ltd", "corporate", CRE, parent_id="LE-0001"),
    Entity("LE-0004", "Acme Logistics Sdn Bhd", "corporate", TRANSPORT, parent_id="LE-0002"),
    # Helios group — energy — structural wrong-way risk
    Entity("LE-0010", "Helios Holdings Ltd", "corporate", ENERGY, annual_revenue=60_000_000),
    Entity("LE-0011", "Helios Power Pte Ltd", "corporate", ENERGY, parent_id="LE-0010"),
    Entity("LE-0012", "Helios Retail Energy Ltd", "corporate", ENERGY, parent_id="LE-0010"),
    # Vortex group — NBFI — UBO aggregation breach (Archegos-shaped)
    Entity("LE-0020", "Vortex Global Holdings Ltd", "nbfi", FIN),
    Entity("LE-0021", "Vortex Alpha Fund Ltd", "nbfi", FIN, parent_id="LE-0020"),
    Entity("LE-0022", "Vortex Beta Fund Ltd", "nbfi", FIN, parent_id="LE-0020"),
    Entity("LE-0023", "Vortex Gamma Fund Ltd", "nbfi", FIN, parent_id="LE-0020"),
    # Nimbus — NBFI cascade (small direct, large via guarantees)
    Entity("LE-0030", "Nimbus Capital Partners Ltd", "nbfi", FIN),
    Entity("LE-0031", "Pinnacle Developments Ltd", "corporate", CRE, annual_revenue=40_000_000),
    Entity("LE-0032", "Summit Resources Ltd", "corporate", ENERGY, annual_revenue=35_000_000),
    Entity("LE-0033", "Crest Manufacturing Ltd", "corporate", INDUS, annual_revenue=30_000_000),
    # Standalone names (sector spread + CR10 tail + government)
    Entity("LE-0040", "Orion Estates Ltd", "corporate", CRE, annual_revenue=25_000_000),
    Entity("LE-0041", "Zenith Tech Pte Ltd", "corporate", TECH, annual_revenue=20_000_000),
    Entity("LE-0042", "Sirius Public Authority", "government", GOV),
    Entity("LE-0043", "Castor Health Ltd", "corporate", HEALTH, annual_revenue=15_000_000),
    Entity("LE-0044", "Pollux Logistics Ltd", "corporate", TRANSPORT, annual_revenue=12_000_000),
    Entity("LE-0045", "Borealis Foods Ltd", "corporate", CONSUMER, annual_revenue=18_000_000),
    Entity("LE-0046", "Lyra Capital Ltd", "nbfi", FIN),
    Entity("LE-0047", "Draco Industrial Ltd", "corporate", INDUS, annual_revenue=14_000_000),
    Entity("LE-0048", "Vega Retail Ltd", "corporate", CONSUMER, annual_revenue=10_000_000),
    Entity("LE-0049", "Altair Energy Ltd", "corporate", ENERGY, annual_revenue=16_000_000),
    # Further small standalone names (book breadth so CR10 is meaningful)
    Entity("LE-0050", "Mistral Foods Ltd", "corporate", CONSUMER, annual_revenue=11_000_000),
    Entity("LE-0051", "Cobalt Materials Ltd", "corporate", INDUS, annual_revenue=13_000_000),
    Entity("LE-0052", "Delphi Health Ltd", "corporate", HEALTH, annual_revenue=9_000_000),
    Entity("LE-0053", "Aster Retail Pte Ltd", "corporate", CONSUMER, annual_revenue=8_000_000),
]

_SOURCES = {
    "entities": "entities.csv — counterparty master (as if from KYC/onboarding)",
    "loans": "loans.csv — loan book (as if from the lending/core-banking system)",
    "guarantees": "guarantees.csv — credit support (as if from collateral management)",
    "collateral": "collateral.csv — pledged collateral (as if from collateral management)",
    "limits": "limits.csv — credit limits (as if from the risk/limits system)",
}

_M = 1_000_000


def _loan(loan_id: str, borrower: str, principal_m: int) -> Loan:
    return Loan(loan_id, BANK, borrower, principal_m * _M)


# --------------------------------------------------------------------------- #
#  STRESSED variant
# --------------------------------------------------------------------------- #


def build_stressed() -> DatasetSpec:
    loans = [
        # Acme group direct (roll-up 20M; under its 25M limit on its own)
        _loan("LN-1001", "LE-0002", 5),
        _loan("LN-1002", "LE-0004", 5),
        _loan("LN-1003", "LE-0001", 5),
        _loan("LN-1004", "LE-0003", 5),
        # Borealis loan (guaranteed by Acme) + Vega loan (shares Acme collateral)
        _loan("LN-1005", "LE-0045", 7),
        _loan("LN-1006", "LE-0048", 7),
        # Nimbus cascade: small direct, guarantees six larger loans
        _loan("LN-1010", "LE-0030", 5),
        _loan("LN-1011", "LE-0031", 7),
        _loan("LN-1012", "LE-0032", 7),
        _loan("LN-1013", "LE-0033", 7),
        _loan("LN-1014", "LE-0047", 7),
        _loan("LN-1015", "LE-0049", 7),
        _loan("LN-1016", "LE-0043", 7),
        # Small unguaranteed second facilities (so those names survive in CR10)
        _loan("LN-1017", "LE-0031", 1),
        _loan("LN-1018", "LE-0032", 1),
        _loan("LN-1019", "LE-0033", 1),
        _loan("LN-1023", "LE-0047", 1),
        # Vortex subsidiaries (each at 80% of its 10M sub-limit; UBO breaches)
        _loan("LN-1020", "LE-0021", 8),
        _loan("LN-1021", "LE-0022", 8),
        _loan("LN-1022", "LE-0023", 8),
        # Helios — WWR loan + a small second loan (group total 10M vs 12M limit)
        _loan("LN-1030", "LE-0011", 7),
        _loan("LN-1031", "LE-0012", 3),
        # Standalone tail
        _loan("LN-1040", "LE-0040", 3),
        _loan("LN-1041", "LE-0041", 2),
        _loan("LN-1042", "LE-0042", 3),
        _loan("LN-1044", "LE-0044", 2),
        _loan("LN-1048", "LE-0046", 2),
        _loan("LN-1050", "LE-0050", 3),
        _loan("LN-1051", "LE-0051", 3),
        _loan("LN-1052", "LE-0052", 2),
        _loan("LN-1053", "LE-0053", 2),
    ]
    guarantees = [
        Guarantee("GTY-2001", "LE-0001", "LN-1005", 7 * _M),  # Acme -> Borealis
        Guarantee("GTY-2002", "LE-0030", "LN-1011", 7 * _M),  # Nimbus -> Pinnacle
        Guarantee("GTY-2003", "LE-0030", "LN-1012", 7 * _M),  # Nimbus -> Summit
        Guarantee("GTY-2004", "LE-0030", "LN-1013", 7 * _M),  # Nimbus -> Crest
        Guarantee("GTY-2005", "LE-0030", "LN-1014", 7 * _M),  # Nimbus -> Draco
        Guarantee("GTY-2006", "LE-0030", "LN-1015", 7 * _M),  # Nimbus -> Altair
        Guarantee("GTY-2007", "LE-0030", "LN-1016", 7 * _M),  # Nimbus -> Castor
    ]
    collateral = [
        # Shared collateral linking Vega's loan to an Acme loan. Because it secures
        # two DIFFERENT borrowers' loans it is not dedicated to one netting set, so
        # it is excluded from netting (its value still present in the data).
        Collateral(
            "COL-3001",
            "Marina warehouse",
            "LE-0002",
            ("LN-1001", "LN-1006"),
            collateral_value=6 * _M,
            haircut_pct=20,
        ),
        # WWR: Helios Power pledges a bond ISSUED BY its own parent Helios Holdings.
        # Wrong-way collateral is weak protection -> a heavy 50% haircut.
        Collateral(
            "COL-3002",
            "Helios Holdings 5% bond",
            "LE-0011",
            ("LN-1030",),
            issuer_id="LE-0010",
            collateral_value=4 * _M,
            haircut_pct=50,
        ),
        Collateral(
            "COL-3003",
            "Plant & equipment",
            "LE-0021",
            ("LN-1020",),
            collateral_value=5 * _M,
            haircut_pct=20,
        ),
        # Spread of collateralised names across sectors (for the net-exposure view
        # + sector filtering). Haircuts reflect collateral quality.
        Collateral(  # government bond — low haircut
            "COL-3004",
            "Sovereign 5% bond",
            "LE-0042",
            ("LN-1042",),
            collateral_value=2 * _M,
            haircut_pct=5,
        ),
        Collateral(  # commercial real estate
            "COL-3005",
            "Office tower",
            "LE-0040",
            ("LN-1040",),
            collateral_value=2 * _M,
            haircut_pct=25,
        ),
        Collateral(  # trade receivables — high haircut
            "COL-3006",
            "Trade receivables",
            "LE-0043",
            ("LN-1016",),
            collateral_value=4 * _M,
            haircut_pct=40,
        ),
        Collateral(  # listed equities pledged by an NBFI
            "COL-3007",
            "Listed equities",
            "LE-0030",
            ("LN-1010",),
            collateral_value=3 * _M,
            haircut_pct=30,
        ),
    ]
    return DatasetSpec(
        "stressed",
        ENTITIES,
        loans,
        guarantees,
        collateral,
        _limits_common(),
        description="Deliberately engineered to breach concentration thresholds (§4/§9).",
        sources=_SOURCES,
    )


# --------------------------------------------------------------------------- #
#  CALM variant — same names, exposures rebalanced into normal bands
# --------------------------------------------------------------------------- #


def build_calm() -> DatasetSpec:
    loans = [
        # Acme group direct (modest; no shared-collateral pull)
        _loan("LN-1001", "LE-0002", 3),
        _loan("LN-1002", "LE-0004", 2),
        _loan("LN-1003", "LE-0001", 2),
        _loan("LN-1004", "LE-0003", 2),
        _loan("LN-1005", "LE-0045", 4),
        _loan("LN-1006", "LE-0048", 4),
        # Nimbus — small book, one modest guarantee
        _loan("LN-1010", "LE-0030", 4),
        _loan("LN-1011", "LE-0031", 5),
        _loan("LN-1012", "LE-0032", 4),
        _loan("LN-1013", "LE-0033", 4),
        _loan("LN-1014", "LE-0047", 4),
        _loan("LN-1015", "LE-0049", 4),
        _loan("LN-1016", "LE-0043", 4),
        # Vortex subsidiaries (well under sub + UBO limits)
        _loan("LN-1020", "LE-0021", 4),
        _loan("LN-1021", "LE-0022", 4),
        _loan("LN-1022", "LE-0023", 3),
        # Helios — collateral is a THIRD-PARTY bond (no WWR in calm)
        _loan("LN-1030", "LE-0011", 5),
        _loan("LN-1031", "LE-0012", 3),
        # Standalone tail
        _loan("LN-1040", "LE-0040", 5),
        _loan("LN-1041", "LE-0041", 4),
        _loan("LN-1042", "LE-0042", 5),
        _loan("LN-1044", "LE-0044", 4),
        _loan("LN-1048", "LE-0046", 4),
        _loan("LN-1050", "LE-0050", 4),
        _loan("LN-1051", "LE-0051", 4),
        _loan("LN-1052", "LE-0052", 3),
        _loan("LN-1053", "LE-0053", 3),
    ]
    guarantees = [
        # Calm: one small guarantee (mechanism present, well within limits)
        Guarantee("GTY-2002", "LE-0030", "LN-1011", 5 * _M),  # Nimbus -> Pinnacle
    ]
    collateral = [
        Collateral(
            "COL-3001",
            "Marina warehouse",
            "LE-0002",
            ("LN-1001",),  # not shared
            collateral_value=3 * _M,
            haircut_pct=20,
        ),
        # Calm: bond issued by an unrelated third party -> no WWR -> light haircut
        Collateral(
            "COL-3002",
            "Government 3% bond",
            "LE-0011",
            ("LN-1030",),
            issuer_id="LE-0042",
            collateral_value=4 * _M,
            haircut_pct=10,
        ),
        Collateral(
            "COL-3003",
            "Plant & equipment",
            "LE-0021",
            ("LN-1020",),
            collateral_value=3 * _M,
            haircut_pct=20,
        ),
        Collateral(  # government bond — low haircut
            "COL-3004",
            "Sovereign 5% bond",
            "LE-0042",
            ("LN-1042",),
            collateral_value=3 * _M,
            haircut_pct=5,
        ),
        Collateral(  # commercial real estate
            "COL-3005",
            "Office tower",
            "LE-0040",
            ("LN-1040",),
            collateral_value=2 * _M,
            haircut_pct=25,
        ),
    ]
    return DatasetSpec(
        "calm",
        ENTITIES,
        loans,
        guarantees,
        collateral,
        _limits_common(),
        description="Same names rebalanced so all metrics sit within normal bands.",
        sources=_SOURCES,
    )


def _limits_common() -> list[Limit]:
    """Limits express risk appetite, not the scenario — identical in both sets.

    Default single-name limit = 25M (25% of the bank's eligible capital). Helios
    carries a tighter 12M limit (so it sits amber under stress). Vortex
    subsidiaries get individual 10M limits and the Vortex UBO a 20M group limit,
    so the UBO can breach while no subsidiary does.
    """
    default = 25_000_000
    default_names = [
        "LE-0001",
        "LE-0030",
        "LE-0031",
        "LE-0032",
        "LE-0033",
        "LE-0040",
        "LE-0041",
        "LE-0042",
        "LE-0043",
        "LE-0044",
        "LE-0045",
        "LE-0046",
        "LE-0047",
        "LE-0048",
        "LE-0049",
        "LE-0050",
        "LE-0051",
        "LE-0052",
        "LE-0053",
    ]
    limits = [Limit(f"LIM-{n}", n, default) for n in default_names]
    limits.append(Limit("LIM-LE-0010", "LE-0010", 12_000_000))  # Helios (tight)
    limits.append(Limit("LIM-LE-0020", "LE-0020", 20_000_000))  # Vortex UBO group limit
    for sub in ("LE-0021", "LE-0022", "LE-0023"):
        limits.append(Limit(f"LIM-{sub}", sub, 10_000_000))  # Vortex subsidiary limits
    return limits


DATASETS = {"calm": build_calm, "stressed": build_stressed}


def get_dataset(name: str) -> DatasetSpec:
    if name not in DATASETS:
        raise ValueError(f"unknown dataset {name!r}; choose from {sorted(DATASETS)}")
    return DATASETS[name]()
