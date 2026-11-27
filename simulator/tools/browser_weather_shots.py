"""Capture six pairs at fixed review poses in one jacket replay, plus a contact sheet."""
import json
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout
from browser_daylight_shots import PLACE, grab
from browser_scene_looks import REAL, build_replay
from browser_underwater_look import school_view

OUT = Path(__file__).resolve().parents[2] / "docs/design/weather-u5"
SITE = "jacket_inspection"
CONDITIONS = {
    "Sunny morning": ("morning", 0.15, 1, 0),
    "Overcast": ("day", 1, 1, 0),
    "Dusk": ("dusk", 0.32, 1, 0),
    "Night": ("night", 0.3, 1, 0),
    "Rough sea": ("day", 0.62, 6, 0),
    "Rain": ("day", 0.91, 3, 0.9),
}


def capture(browser, replay, side):
    page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda msg: errors.append(msg.text) if "Shader Error" in msg.text else None)
    page.route("**/__weather.json", lambda route: route.fulfill(
        body=json.dumps(replay), content_type="application/json"))
    page.goto(f"{http_base()}/?replay=__weather.json&capture&nointro&nopip&{REAL}")
    page.wait_for_function("window.__viewer?.S && !!window.__advance", timeout=timeout(90000))
    page.wait_for_load_state("networkidle")
    page.evaluate("window.__advance(1/30)")
    if side == "surface":
        page.evaluate(PLACE, [[[-6, -9, -2.2], [20, 4, -9]], 0, 15])
    for label, values in CONDITIONS.items():
        weather = dict(zip(("time_of_day", "cloud_cover", "sea_state", "rain"), values))
        page.evaluate("(w) => {window.__viewer.W.scenario.weather = w}", weather)
        for _ in range(8):
            page.evaluate("window.__advance(1/15)")
            page.wait_for_timeout(100)
        path = OUT / f"{label.lower().replace(' ', '-')}-{side}.jpg"
        grab(page, path)
        print(path.name, flush=True)
        assert not errors, errors
    page.close()


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    eye, target = school_view(SITE, 42, 1.6, 0.1)
    replay, _ = build_replay("weather", (SITE, 42), eye, target, 2)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        for side in ("surface", "submerged"):
            capture(browser, replay, side)
        browser.close()
    sheet = Image.new("RGB", (800, 6 * 251), "#17212a")
    draw = ImageDraw.Draw(sheet)
    for row, label in enumerate(CONDITIONS):
        draw.text((10, row * 251 + 5), label, fill="white")
        for col, side in enumerate(("surface", "submerged")):
            with Image.open(OUT / f"{label.lower().replace(' ', '-')}-{side}.jpg") as frame:
                sheet.paste(frame.resize((400, 225), Image.Resampling.LANCZOS), (col * 400, row * 251 + 26))
    sheet.save(OUT / "contact-sheet.jpg", quality=88)


if __name__ == "__main__":
    main()
