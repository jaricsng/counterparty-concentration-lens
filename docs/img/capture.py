"""Capture demo screenshots + a scroll-tour GIF of the running Lens app.

Reproducible provenance for docs/img/*. Assumes the app is running with the stressed
dataset (see docs/running-the-lens.md); then:

    python docs/img/capture.py            # writes docs/img/*.png + demo-tour.gif

Uses Playwright (headless chromium) + Pillow. Not part of the app or CI.
"""

from __future__ import annotations

import io
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

URL = "http://localhost:8502/"
OUT = Path(__file__).parent
VIEW = {"width": 1440, "height": 900}

# subheader text -> screenshot filename (the section is scrolled into view)
SECTIONS = [
    ("HHI (connected)", "01-dashboard-top.png"),
    ("Country & rating concentration", "02-country-rating.png"),
    ("Net exposure (post-collateral / netting)", "03-net-exposure.png"),
    ("Expected loss & capital", "04-expected-loss-capital.png"),
    ("IFRS-9 ECL & staging", "05-ifrs9.png"),
    ("Stress / scenario (what-if)", "06-stress-scenario.png"),
    ("Reverse stress", "07-reverse-stress.png"),
    ("Forward-looking exposure & CVA", "08-xva.png"),
    ("Systemic contagion", "09-contagion.png"),
]


def _shot_section(page, needle: str, path: Path) -> None:
    el = page.get_by_text(needle, exact=False).first
    el.scroll_into_view_if_needed()
    page.mouse.wheel(0, -120)  # keep the header from being clipped at the very top
    page.wait_for_timeout(700)
    page.screenshot(path=str(path))
    print("  wrote", path.name)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEW, device_scale_factor=1)
        page.goto(URL, wait_until="networkidle", timeout=60_000)
        page.get_by_text("HHI (connected)", exact=False).first.wait_for(timeout=45_000)
        page.wait_for_timeout(1500)

        # --- static section screenshots (Dashboard) ---
        for needle, name in SECTIONS:
            try:
                _shot_section(page, needle, OUT / name)
            except Exception as exc:  # noqa: BLE001 — best-effort capture
                print("  skip", name, "->", repr(exc)[:120])

        # --- scroll-tour GIF of the dashboard ---
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(600)
        total = page.evaluate("document.body.scrollHeight") - VIEW["height"]
        frames: list[Image.Image] = []
        steps = 14
        for i in range(steps + 1):
            page.evaluate(f"window.scrollTo(0, {int(total * i / steps)})")
            page.wait_for_timeout(220)
            raw = page.screenshot()  # bytes, no temp file
            frames.append(Image.open(io.BytesIO(raw)).convert("RGB").resize((960, 600)))
        # hold the first/last frames a little
        seq = [frames[0]] * 3 + frames + [frames[-1]] * 4
        pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f in seq]
        pal[0].save(
            OUT / "demo-tour.gif",
            save_all=True,
            append_images=pal[1:],
            duration=350,
            loop=0,
            optimize=True,
        )
        print("  wrote demo-tour.gif")

        # --- NL chat screenshot ---
        try:
            page.get_by_role("tab", name="Ask (NL)").click()
            page.wait_for_timeout(800)
            box = page.get_by_placeholder("Ask about exposure", exact=False)
            box.click()
            box.fill("which counterparty is most systemically important?")
            box.press("Enter")
            page.wait_for_timeout(2500)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / "10-nl-chat.png"))
            print("  wrote 10-nl-chat.png")
        except Exception as exc:  # noqa: BLE001
            print("  skip nl-chat ->", repr(exc)[:120])

        browser.close()


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"done in {time.time() - t0:.0f}s")
