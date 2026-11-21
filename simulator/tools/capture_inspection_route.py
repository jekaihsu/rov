"""Sample fixed five-second waypoints along the first 30 seconds of each inspection approach."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout
from browser_scene_looks import REAL, build_replay

# (eye, aim) NED metres. Replay poses keep both versions on the same path.
ROUTES = {
    "hull_inspection": [
        ((0, 0, 3), (7, 0, 4)), ((3, 0, 3.5), (10, 0, 5)),
        ((6, -.5, 4), (13, 0, 5)), ((9, -1.5, 5), (14, 0, 5.6)),
        ((12, -2.8, 6.6), (15, 0, 5.8)), ((15, -2.8, 8.5), (19, 0, 7)),
        ((18, -1, 9.5), (21, 0, 7.8))],
    "aquaculture_pen": [
        ((3, 0, 7), (6, 1, 7)), ((3, 2.5, 7), (6.5, 1, 7)),
        ((3.5, 5, 6.5), (7, 4, 6)), ((4.5, 7.5, 6), (8, 6.8, 5.5)),
        ((5.7, 10, 5), (9, 8.5, 5)), ((7.2, 12, 4), (10, 10.5, 4)),
        ((9, 14, 3), (11.5, 12, 3))],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        for site, poses in ROUTES.items():
            snapshots = []
            for i, (eye, aim) in enumerate(poses):
                recording, _ = build_replay(site, (site, 1), eye, aim, 2)
                frame = recording["clips"][0]["frames"][0]
                snapshots.append({**frame, "t": i * 5})
            recording["clips"][0]["frames"] = snapshots + [{**snapshots[-1], "t": 31}]
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            page.route("**/__route.json", lambda route: route.fulfill(
                body=json.dumps(recording), content_type="application/json"))
            page.goto(f"{http_base(8092)}/?replay=__route.json&nointro&capture&{REAL}")
            page.wait_for_function("Boolean(window.__viewer?.S && window.__advance)", timeout=timeout(90000))
            page.wait_for_load_state("networkidle", timeout=timeout(90000))
            page.add_style_tag(content="#replayBar,#rpSub{display:none!important}")
            page.evaluate("document.querySelector('#rpPlay').click()")
            for i in range(len(poses)):
                # Advance the replay clock through intermediate poses. Render the sampled frame at full resolution.
                page.evaluate("""i => {
                    const replay = window.__viewer.rep;
                    window.__skipRender = true;
                    const steps = i ? 100 : 16;
                    for (let n = 1; n <= steps; n++) {
                      replay.t = i ? (i - 1) * 5 + n / 20 : 0;
                      window.__advance(.05);
                    }
                    window.__skipRender = false;
                    window.__advance(.001);
                }""", i)
                path = args.out / f"{site}-{i * 5:02}s.jpg"
                page.screenshot(path=str(path), type="jpeg", quality=82, timeout=timeout(240000))
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
