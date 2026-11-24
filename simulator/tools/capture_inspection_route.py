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
        ((30.0, -13.2, 6.0), (30.0, -9.5, 6.0)), ((30.0, -12.2, 6.1), (30.0, -9.3, 6.0)),
        ((29.5, -11.4, 6.3), (29.5, -9.2, 6.2)), ((28.5, -10.8, 6.6), (28.5, -9.0, 6.4)),
        ((26.0, -10.4, 7.0), (26.0, -8.8, 6.8)), ((22.0, -9.8, 7.5), (20.0, -8.5, 7.0)),
        ((18.0, -8.8, 8.0), (16.0, -6.2, 7.5))],
    "aquaculture_pen": [
        ((1.8, 1.1, 1.25), (5.5, 1.8, 1.25)), ((2.5, 1.5, 2.0), (6.0, 1.8, 2.2)),
        ((3.2, 2.5, 3.5), (6.5, 2.2, 4.0)), ((3.8, 4.0, 5.0), (7.0, 3.5, 5.5)),
        ((4.2, 6.0, 6.5), (7.2, 5.0, 7.0)), ((5.0, 8.5, 6.0), (8.5, 7.5, 5.5)),
        ((6.5, 11.0, 4.5), (10.0, 10.0, 4.0))],
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
