"""Capture harbor_inspection and wreck_survey screenshots for G3: snag objects and the pilot log.

Usage (from simulator/, with a server on ROV_HTTP_PORT / ROV_WS_PORT):
  ROV_CHROMIUM=/opt/google/chrome/chrome python3 tools/capture_g3_tether_visibility.py

Writes output/g3-tether-visibility/*-{snags,log}-{before,after}.png. Evidence copies live under
docs/tasks/evidence/G3/.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'g3-tether-visibility'
SCENES = (
    ('harbor_inspection', 'Harbor rubble', [36.0, -2.0, 18.0]),
    ('wreck_survey', 'Wreck boulder 3', [31.1, 17.2, 30.0]),
)


def log_lines(snag_name):
    return [
        {'t': 12.0, 'kind': 'tether', 'text': f'勾纏：{snag_name}'},
        {'t': 18.0, 'kind': 'tether', 'text': f'勾纏收緊：{snag_name}'},
        {'t': 22.0, 'kind': 'tether', 'text': f'勾纏脫開：{snag_name}'},
        {'t': 25.0, 'kind': 'tether', 'text': '絞車失速'},
        {'t': 30.0, 'kind': 'tether', 'text': '扭轉警示（+2.3 圈）'},
        {'t': 35.0, 'kind': 'tether', 'text': '斷纜（gland）'},
        {'t': 40.0, 'kind': 'silt', 'text': '揚沙全白'},
        {'t': 45.0, 'kind': 'power', 'text': '電源跳脫'},
    ]


def open_engineering(page):
    page.evaluate("""() => {
      const panel = document.getElementById('engineering');
      if (panel) panel.hidden = false;
      document.body.classList.remove('hud-hidden');
    }""")
    page.wait_for_function(
        'document.getElementById("engineering") && !document.getElementById("engineering").hidden',
        timeout=timeout(10000))


def aim_at_snag(page, point, *, hide_snags=False):
    page.evaluate("""({point, hideSnags}) => {
      const v = window.__viewer;
      const THREE = v.THREE;
      window.__skipRender = true;
      document.body.classList.add('hud-hidden');
      document.querySelectorAll('.banner, .flight, [class*="banner"]').forEach((el) => {
        el.style.display = 'none';
        el.hidden = true;
      });
      const eng = document.getElementById('engineering');
      if (eng) eng.hidden = true;
      const structures = [...(v.worldG?.children || [])].find((c) => c.name === 'structures');
      if (hideSnags) {
        structures?.traverse((o) => {
          if (!o.isMesh) return;
          const names = o.userData?.colliders || [];
          if (names.length && names.every((n) => (v.W.obstacles || []).some((ob) => ob.name === n && ob.type === 'snag')))
            o.visible = false;
        });
      }
      const at = new THREE.Vector3(-point[1], -point[2], point[0]);
      v.camera.position.copy(at).add(new THREE.Vector3(1.0, 2.0, 2.4));
      v.camera.lookAt(at.x, at.y + 0.3, at.z);
      v.camera.near = 0.05;
      v.camera.far = 40;
      v.camera.updateProjectionMatrix();
      v.scene.fog = null;
      v.scene.background = new THREE.Color(0x246070);
      if (!window.__g3Light) {
        window.__g3Light = new THREE.PointLight(0xfff2d8, 4.5, 18, 1.4);
        v.scene.add(window.__g3Light);
        v.scene.add(new THREE.HemisphereLight(0x8ec8d8, 0x2a2418, 0.85));
      }
      window.__g3Light.position.copy(v.camera.position);
      structures?.traverse((o) => {
        if (o.isMesh && o.material?.emissive?.setHex) {
          o.material.emissive.setHex(0x222018);
          o.material.needsUpdate = true;
        }
      });
      v.renderer.toneMapping = THREE.NoToneMapping;
      v.renderer.setClearColor(0x246070, 1);
      v.renderer.render(v.scene, v.camera);
    }""", {'point': point, 'hideSnags': hide_snags})


def paint_log(page, snag_name):
    page.evaluate("""(lines) => {
      const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ').replace(/-/g, '/');
      const rows = lines.map((l) => ({...l, stamp}));
      window.__g3Log = rows;
      const paint = () => {
        const el = document.getElementById('log');
        if (!el || !window.__g3Log) return;
        el.innerHTML = window.__g3Log.slice().reverse().map((l) =>
          '<li><span class="t">' + l.stamp + '</span><span class="x">' + l.text + '</span></li>').join('');
      };
      paint();
      if (!window.__g3LogHook) window.__g3LogHook = setInterval(paint, 100);
    }""", log_lines(snag_name))


def capture(page, scenario, snag_name, point, label, *, before=False):
    suffix = 'before' if before else 'after'
    page.goto(
        f'{http_base()}/?play=1&nointro&scenario={scenario}&room=g3{suffix}{label}&ws={ws_base()}'
        f'&fidelity=real&thirdPerson=1&cam=orbit&quality=medium',
        wait_until='domcontentloaded')
    page.wait_for_function(
        'window.__viewer?.W?.obstacles?.some((o) => o.type === "snag") && window.__modelLoaded',
        timeout=timeout(90000))
    page.wait_for_timeout(1200)
    aim_at_snag(page, point, hide_snags=before)
    page.wait_for_timeout(150)
    (OUT / f'{label}-snags-{suffix}.png').write_bytes(page.screenshot(type='png'))
    if before:
        print(f'wrote {label}-snags-{suffix}.png')
        return
    open_engineering(page)
    paint_log(page, snag_name)
    page.wait_for_timeout(400)
    page.evaluate('document.getElementById("log")?.scrollIntoView({block:"center"})')
    page.wait_for_timeout(300)
    box = page.locator('#engineering .rack.right').bounding_box()
    (OUT / f'{label}-log-{suffix}.png').write_bytes(
        page.screenshot(type='png', clip=box if box else None))
    print(f'wrote {label}-snags-{suffix}.png and {label}-log-{suffix}.png')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        for scenario, snag, point in SCENES:
            label = scenario.replace('_', '-')
            capture(page, scenario, snag, point, label, before=True)
            capture(page, scenario, snag, point, label, before=False)
        browser.close()
    if errors:
        print('page errors:', errors, file=sys.stderr)
        return 1
    print('G3 captures saved under', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
