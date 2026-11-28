"""Visit the prologue-unlocked wreck, photograph two subjects, and inspect the departure log."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, without_render, ws_base
from _campaign_drive import unlock_again
from browser_prologue_smoke import flight_keys
from _menu import open_main, soft_click, wait_screen


def run(page):
    page.on("pageerror", lambda error: print("page error:", error, flush=True))
    page.goto(f"{http_base(8092)}/?ws={ws_base(8792)}&quality=performance")
    open_main(page)
    soft_click(page, "#entry-freeDive")
    wait_screen(page, "sites")
    assert page.locator('[data-site="korean_castle"]').count() == 0
    page.keyboard.press("Escape")
    page.evaluate("localStorage.setItem('rov.campaign.v1', JSON.stringify({completed:['prologue']}))")
    soft_click(page, "#entry-freeDive")
    soft_click(page, '[data-site="korean_castle"]')
    page.wait_for_selector(".free-dive-list", timeout=timeout(90000))
    page.wait_for_function("window.__viewer.worldG.getObjectByName('Forecastle_deck') && window.__modelLoaded")
    shots = Path(__file__).resolve().parents[1] / "output/free-dive"
    shots.mkdir(parents=True, exist_ok=True)
    assert page.evaluate("window.__viewer.S.mission.mode") == "free_explore"
    first = page.evaluate("window.__viewer.takePhoto()")
    print("first", first, flush=True)
    assert first and first["observation"]
    assert not page.evaluate("window.__viewer.S.tether.broken")
    keys = flight_keys(page)
    with without_render(page):
        if page.evaluate("window.__viewer.S.locked"):
            unlock_again(page, keys["lock"])
        page.wait_for_function("window.__viewer.S.locked === false")
        start = page.evaluate("window.__viewer.S.pos.slice()")
        page.keyboard.down(keys["surge"][0])
        try:
            moved = page.wait_for_function("""p => {
                const s = window.__viewer.S;
                const distance = Math.hypot(s.pos[0] - p[0], s.pos[1] - p[1]);
                return !s.locked && s.thrust.some(v => Math.abs(v) > 0.01) && distance > 0.1 && distance;
            }""", arg=start, timeout=timeout(20000))
            print(f"Unlocked horizontal displacement: {moved.json_value():.3f} m", flush=True)
        finally:
            page.keyboard.up(keys["surge"][0])
    second = page.evaluate("window.__viewer.takePhoto()")
    print("second", second, flush=True)
    assert second and second["observation"]
    assert second["observation"]["category"] != first["observation"]["category"]
    page.screenshot(path=str(shots / "free_dive_wreck-discovery.jpg"))
    page.keyboard.press("Escape")
    soft_click(page, "#pauseHome")
    log = page.locator("dialog.free-dive-log")
    log.wait_for()
    assert log.locator("small").count() == 2
    log.locator("button").click()
    page.wait_for_function("window.__menu?.ready", timeout=timeout(60000))


if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        run(browser.new_page(viewport={"width": 960, "height": 540}))
        browser.close()
