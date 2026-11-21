"""Playwright fixed-step capture of a baked trailer clip (1920×1080 @ 60 fps PNG sequence)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from _browser import http_base, launch, timeout, ws_base  # noqa: E402


def _hud_flag(hud) -> bool:
    if hud in (False, 'off'):
        return False
    return True


def capture_clip(
    clip_path: Path,
    frames_dir: Path | None,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    http_port: int | None = None,
    ws_port: int | None = None,
    hero_at: float | None = None,
    hero_path: Path | None = None,
    hero_only: bool = False,
) -> dict:
    """Render every frame of a baked replay into PNG files under frames_dir.

    The page runs with ?capture&trailer so the realtime clock is paused and each call to
    window.__advance(1/fps) draws exactly one frame. Camera path and HUD come from the clip's
    trailer metadata (written by bake.py). With hero_only=True only the representative frame
    is written (for docs/design/trailer review stills).
    """
    clip = json.loads(clip_path.read_text(encoding='utf-8'))
    trailer_meta = (clip.get('clips') or [{}])[0].get('trailer') or {}
    camera = trailer_meta.get('camera') or {'mode': 'onboard'}
    hud = trailer_meta.get('hud', True)
    duration = float(trailer_meta.get('duration') or 0)
    if duration <= 0:
        frames = (clip.get('clips') or [{}])[0].get('frames') or []
        duration = float(frames[-1]['t'] - frames[0]['t']) if len(frames) > 1 else 0.0
    if hero_at is None:
        hero_at = float(trailer_meta.get('hero_at', duration * 0.45))

    if frames_dir is not None and not hero_only:
        frames_dir.mkdir(parents=True, exist_ok=True)
    # Serve the clip from the simulator HTTP root so ?replay=… can fetch it.
    # bake writes under simulator/output/trailer/…; the server mounts viewer/ and also may serve
    # from the simulator root depending on config. Copy into viewer/_trailer_clips for a stable URL.
    viewer_clips = TOOLS.parent / 'viewer' / '_trailer_clips'
    viewer_clips.mkdir(parents=True, exist_ok=True)
    served = viewer_clips / clip_path.name
    served.write_bytes(clip_path.read_bytes())
    replay_url = f'_trailer_clips/{served.name}'

    base = http_base(http_port or 8092)
    ws = ws_base(ws_port or 8792)
    query = (
        f'?ws={ws}&replay={replay_url}&capture&trailer=1&nointro&nopip&quality=ultra'
        f'&movie=0'
    )
    url = f'{base}/{query}'

    frame_count = int(round(duration * fps))
    hero_index = int(round(hero_at * fps))
    hero_index = max(0, min(frame_count - 1, hero_index))

    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        context = browser.new_context(viewport={'width': width, 'height': height},
                                      device_scale_factor=1)
        context.set_default_timeout(timeout(120000))
        page = context.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=timeout(120000))
        page.wait_for_function(
            'window.__advance && window.__trailer && window.__viewer && window.__replay',
            timeout=timeout(180000),
        )
        page.wait_for_function(
            '() => { const r = window.__replay(); return r && r.dur > 0; }',
            timeout=timeout(180000),
        )
        page.evaluate(
            """([camera, hud]) => {
              window.__trailer.setPath(camera);
              window.__trailer.setHud(hud);
              window.__trailer.setTime(0);
              if (window.__viewer?.setCam && camera.mode === 'onboard') {
                window.__viewer.setCam('onboard');
              }
            }""",
            [camera, _hud_flag(hud)],
        )
        # Warm a couple of frames so materials and the first state settle.
        for _ in range(3):
            page.evaluate('(dt) => window.__advance(dt)', 1 / fps)

        page.evaluate('() => { window.__trailer.setTime(0); if (window.__viewer?.rep) window.__viewer.rep.t = 0; }')
        # Reset replay time properly through the public API when available.
        page.evaluate(
            """() => {
              const rep = window.__viewer?.rep;
              if (rep) { rep.t = 0; rep.endHold = 0; rep.playing = true; }
              window.__trailer.setTime(0);
            }"""
        )

        written = []
        if hero_only:
            # Fast-forward without drawing until the hero frame (viewer honours __skipRender).
            if hero_index > 0:
                page.evaluate(
                    """([n, dt]) => {
                      window.__skipRender = true;
                      for (let i = 0; i < n; i++) window.__advance(dt);
                      window.__skipRender = false;
                      window.__advance(dt);
                    }""",
                    [hero_index, 1 / fps],
                )
            else:
                page.evaluate('(dt) => window.__advance(dt)', 1 / fps)
            if hero_path is not None:
                hero_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(hero_path), type='png', timeout=timeout(120000))
            print(f'  hero-only at frame {hero_index}/{frame_count}', flush=True)
        else:
            for index in range(frame_count):
                page.evaluate('(dt) => window.__advance(dt)', 1 / fps)
                path = frames_dir / f'frame_{index:06d}.png'
                page.screenshot(path=str(path), type='png', timeout=timeout(120000))
                written.append(path)
                if hero_path is not None and index == hero_index:
                    hero_path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(hero_path), type='png', timeout=timeout(120000))
                if index % max(1, fps) == 0:
                    print(f'  frame {index}/{frame_count}', flush=True)

        browser.close()

    return {
        'frames': len(written),
        'duration': duration,
        'fps': fps,
        'hero': str(hero_path) if hero_path else None,
        'frames_dir': str(frames_dir) if frames_dir else None,
        'hero_only': hero_only,
    }
