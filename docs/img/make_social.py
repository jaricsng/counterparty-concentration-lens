"""Render the social-preview card for the repo (GitHub social image + LinkedIn post).

Reproducible provenance for docs/img/social-preview.png. Pure Pillow — no app or network.
Draws at 2x and downscales with LANCZOS for crisp text. Figures are the verified
synthetic-demo numbers (stressed dataset).

    python docs/img/make_social.py     # writes docs/img/social-preview.png (1280x640)
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "social-preview.png"
S = 2  # supersample factor
W, H = 1280 * S, 640 * S

# palette
BG_TOP = (10, 16, 32)
BG_BOT = (14, 26, 51)
WHITE = (245, 247, 250)
MUTED = (154, 167, 189)
AMBER = (242, 169, 59)
RED = (228, 68, 59)
CHIP_TX = (199, 210, 228)
NODE_FILL = (22, 35, 63)
NODE_EDGE = (58, 82, 128)
LINE = (74, 96, 140)

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ARIAL_BLK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size * S)


def w_of(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont) -> int:
    b = draw.textbbox((0, 0), text, font=f)
    return b[2] - b[0]


def tracked(draw, xy, text, f, fill, spacing):
    """Draw letter-spaced text (for the small uppercase kicker)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += w_of(draw, ch, f) + spacing * S


def gradient() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def main() -> None:
    img = gradient().convert("RGBA")

    # --- translucent graph card + faint lens rings (on an alpha overlay) ---
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    card = (735 * S, 150 * S, 1216 * S, 560 * S)
    od.rounded_rectangle(
        card, radius=22 * S, fill=(255, 255, 255, 12), outline=(255, 255, 255, 28), width=1 * S
    )
    cx, cy = 975 * S, 352 * S
    for rad in (95, 140, 188):
        od.ellipse(
            (cx - rad * S, cy - rad * S, cx + rad * S, cy + rad * S),
            outline=(96, 132, 196, 46),
            width=2 * S,
        )
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img)

    # --- concentration graph: central group + satellites ---
    sats = [
        (-90, "Borrower", "loan"),
        (-18, "Guarantor", "guarantee"),
        (54, "Collateral", "shared"),
        (126, "Parent Co", "owns"),
        (198, "NBFI fund", "exposure"),
    ]
    ring = 150 * S
    pts = []
    for ang, label, edge in sats:
        a = math.radians(ang)
        sx, sy = cx + ring * math.cos(a), cy + ring * math.sin(a)
        pts.append((sx, sy, label, edge))
    # edges first
    fedge = font(ARIAL, 12)
    for sx, sy, _label, edge in pts:
        d.line((cx, cy, sx, sy), fill=LINE, width=2 * S)
        mx, my = (cx + sx) / 2, (cy + sy) / 2
        ew = w_of(d, edge, fedge)
        d.text((mx - ew / 2, my - 8 * S), edge, font=fedge, fill=MUTED)
    # satellite nodes
    fsat = font(ARIAL_B, 13)
    rs = 30 * S
    for sx, sy, label, _edge in pts:
        d.ellipse(
            (sx - rs, sy - rs, sx + rs, sy + rs), fill=NODE_FILL, outline=NODE_EDGE, width=2 * S
        )
        lw = w_of(d, label, fsat)
        d.text((sx - lw / 2, sy + rs + 6 * S), label, font=fsat, fill=CHIP_TX)
    # central group node (red)
    rc = 46 * S
    d.ellipse((cx - rc, cy - rc, cx + rc, cy + rc), fill=(58, 26, 30), outline=RED, width=3 * S)
    fg = font(ARIAL_BLK, 15)
    gw = w_of(d, "GROUP X", fg)
    d.text((cx - gw / 2, cy - 15 * S), "GROUP X", font=fg, fill=(255, 214, 210))
    fgs = font(ARIAL, 11)
    sw = w_of(d, "connected view", fgs)
    d.text((cx - sw / 2, cy + 6 * S), "connected view", font=fgs, fill=MUTED)

    # --- left column ---
    x = 64 * S
    tracked(d, (x, 60 * S), "LEARNING PROTOTYPE  ·  SYNTHETIC DATA", font(ARIAL_B, 15), AMBER, 3)

    ftitle = font(ARIAL_BLK, 58)
    d.text((x, 96 * S), "Counterparty", font=ftitle, fill=WHITE)
    d.text((x, 168 * S), "Concentration Lens", font=ftitle, fill=WHITE)

    # accent bar
    d.rounded_rectangle((x, 250 * S, x + 176 * S, 258 * S), radius=4 * S, fill=RED)

    fsub = font(ARIAL, 20)
    sub = [
        "One real-time, relationship-aware view of counterparty",
        "exposure — built on the FIBO financial ontology.",
    ]
    for i, ln in enumerate(sub):
        d.text((x, (280 + i * 30) * S), ln, font=fsub, fill=MUTED)

    # money-shot pill
    py0 = 356 * S
    fpill = font(ARIAL_B, 19)
    seg1, seg2, seg3 = "Direct 2.2M", "Connected 21.2M", "×9.4"
    pad = 16 * S
    pill_w = (
        pad
        + w_of(d, seg1, fpill)
        + 34 * S
        + w_of(d, seg2, fpill)
        + 20 * S
        + w_of(d, seg3, fpill)
        + pad
    )
    d.rounded_rectangle(
        (x, py0, x + pill_w, py0 + 46 * S),
        radius=23 * S,
        fill=(30, 22, 20),
        outline=(120, 70, 40),
        width=1 * S,
    )
    tx = x + pad
    ty = py0 + 12 * S
    d.text((tx, ty), seg1, font=fpill, fill=CHIP_TX)
    tx += w_of(d, seg1, fpill) + 10 * S
    # arrow
    ay = py0 + 23 * S
    d.line((tx, ay, tx + 20 * S, ay), fill=AMBER, width=3 * S)
    d.polygon([(tx + 20 * S, ay - 5 * S), (tx + 28 * S, ay), (tx + 20 * S, ay + 5 * S)], fill=AMBER)
    tx += 34 * S
    d.text((tx, ty), seg2, font=fpill, fill=(255, 176, 120))
    tx += w_of(d, seg2, fpill) + 12 * S
    d.text((tx, ty), seg3, font=fpill, fill=RED)

    # metrics line
    fmet = font(ARIAL, 16)
    d.text(
        (x, 424 * S),
        "HHI 0.187  ·  CR10 91%  ·  multi-hop via guarantees + collateral + ownership",
        font=fmet,
        fill=MUTED,
    )

    # stack chips (two rows)
    chips = [
        "FIBO",
        "Fuseki / SPARQL",
        "SHACL",
        "OPA / Rego",
        "FastAPI",
        "Streamlit",
        "Ollama",
        "Argo CD / k3d",
        "Trivy · SBOM",
    ]
    fchip = font(ARIAL_B, 15)
    cx0, cyrow = x, 466 * S
    row_h = 34 * S
    gap = 8 * S
    maxx = 700 * S
    for c in chips:
        cw = w_of(d, c, fchip) + 24 * S
        if cx0 + cw > maxx:
            cx0 = x
            cyrow += row_h + gap
        d.rounded_rectangle(
            (cx0, cyrow, cx0 + cw, cyrow + row_h),
            radius=row_h // 2,
            fill=(255, 255, 255, 16),
            outline=(255, 255, 255, 36),
            width=1 * S,
        )
        d.text((cx0 + 12 * S, cyrow + 8 * S), c, font=fchip, fill=CHIP_TX)
        cx0 += cw + gap

    # footer
    ffoot = font(ARIAL, 13)
    d.text(
        (x, 596 * S),
        "M0 ontology → M6 GitOps  ·  DevSecOps CI: ruff · mypy · bandit · "
        "gitleaks · trivy · SBOM  ·  production-shaped, not production-hardened",
        font=ffoot,
        fill=(120, 133, 156),
    )

    final = img.convert("RGB").resize((1280, 640), Image.LANCZOS)
    final.save(OUT, optimize=True)
    print("wrote", OUT, final.size)


if __name__ == "__main__":
    main()
