"""Author, persist, reopen and fly a local course through the internal editor."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base, timeout

OUT = Path(__file__).resolve().parents[2] / "docs/design/mission-editor-x6"


def run():
    title = "水池巡檢與回報"
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: print("Page error:", error, flush=True))
        page.goto(f"{http_base(8080)}/mission-editor/?lang=zh-TW&quality=performance&ws={ws_base(8765)}")
        page.locator('[name="title"]').fill(title)
        page.locator('[name="visibility_m"]').fill("0")
        page.locator("[data-action=save]").click()
        page.wait_for_function("document.querySelector('output').textContent.includes('visibility_m')")
        page.locator('[name="visibility_m"]').fill("6")
        page.locator("details input").first.fill("確認出發點並回報。")
        page.locator("[data-action=add]").click()
        page.locator("section select").last.select_option("photo")
        page.locator('[name="limit"]').fill("3")
        page.locator("figure").first.locator("canvas").click(position={"x": 40, "y": 40})
        page.locator('[name="pass_score"]').fill("50")
        with page.expect_download() as info:
            page.locator("[data-action=exportFile]").click()
        saved = info.value.path()
        document = json.loads(saved.read_text(encoding="utf-8"))
        assert len(document["beats"]) == 2
        page.locator("[data-action=newCourse]").click()
        page.locator("[type=file]").set_input_files(saved)
        page.wait_for_function("document.querySelector('[name=title]').value === " + repr(title))
        page.locator("[data-action=save]").click()
        page.wait_for_function("document.querySelector('output').textContent === '已存檔'")
        page.reload()
        page.locator("nav select").select_option(label=title)
        assert page.locator('[name="visibility_m"]').input_value() == "6"
        assert page.locator("details input").first.input_value() == "確認出發點並回報。"
        OUT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=OUT / "editor.png")
        page.locator("[data-action=play]").click()
        page.wait_for_function(
            "window.__training?.scorecard?.lessonTitle === " + repr(title), timeout=timeout(90000)
        )
        card = page.evaluate("window.__training.scorecard")
        assert (
            card["score"] == 50 and card["objectivesDone"] == 1 and card["finished"] and card["passProvisional"]
        ), card
        page.wait_for_selector("#resultsScreen[data-success=true]")
        page.screenshot(path=OUT / "settlement.png")
        page.goto(f"{http_base(8080)}/?menu=training&tab=courses&lang=zh-TW&ws={ws_base(8765)}")
        local = page.locator(f'button[data-lesson="{card["lessonId"]}"]')
        local.wait_for(timeout=timeout(90000))
        assert local.inner_text() == title
        local.scroll_into_view_if_needed()
        page.screenshot(path=OUT / "course-map.png")
        local.click()
        page.wait_for_selector("#hangarNext")
        pad = browser.new_page()
        pad.add_init_script("""window.buttons = Array(17).fill(0);
            Object.defineProperty(navigator, 'getGamepads', {value: () => [{
              id:'Test controller', connected:true, index:0, mapping:'standard', axes:[0,0,0,0],
              buttons:window.buttons.map(value => ({value, pressed:!!value}))
            }]});""")
        pad.goto(f"{http_base(8080)}/mission-editor/?lang=ja")
        pad.wait_for_selector("h1:text-is('任務エディター')")
        pad.locator('[name="visibility_m"]').focus()
        pad.evaluate("window.buttons[15] = 1")
        pad.wait_for_function("document.activeElement.valueAsNumber > 20")
        pad.evaluate("window.buttons[15] = 0")
        steam = browser.new_page()
        steam.add_init_script("window.rovDesktop = {edition:'steam'}")
        steam.goto(f"{http_base(8080)}/mission-editor/", wait_until="commit")
        steam.wait_for_url(f"{http_base(8080)}/")
        assert not steam.locator("#editor").count()
        browser.close()
    print("Saved, reloaded and completed instructor mission:", card["lessonId"])


if __name__ == "__main__":
    run()
