#!/usr/bin/env python3
"""Generate Valve-Compliant Steam Store & Library Graphical Assets (8 Capsules)
+ 5 Official 1920x1080 Pure Gameplay Screenshots for ROV-01 (#80),
and verify the /arena 3-Candidate HUD Theme Engine in headless Chromium.
"""
from __future__ import annotations

import json
import math
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path("/workspace/rov_sim")
BOX_RUN = ROOT / "box_run"
P260_DIR = ROOT / "p260"
THREE_DIR = ROOT / "e2e_deps" / "node_modules" / "three"
OUT_DIR = ROOT / "steam_assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FORBIDDEN_RE = re.compile(
    r"qysea|fifish|(?<![0-9a-z_])x1(?![0-9a-z_])|鰭源|(?<![a-z0-9])qy|q-?irc|(?<![0-9a-z_])qic(?![0-9a-z_])"
    r"|v6p|ego_self_test|bluerov|blue robotics|saab|seaeye|falcon",
    re.IGNORECASE,
)

FONT_TITLE_PATH = "/usr/share/fonts/truetype/sand-box/google/Barlow/Barlow-Black.ttf"
FONT_SUB_PATH = "/usr/share/fonts/truetype/sand-box/google/Fira Sans/FiraSans-Black.ttf"
FONT_MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_SANS_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(FONT_SANS_PATH, size)


def get_free_ports(n: int = 4) -> list[int]:
    socks, ports = [], []
    for _ in range(n):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        socks.append(s)
        ports.append(s.getsockname()[1])
    for s in socks:
        s.close()
    return ports


class P260Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        p = path.split("?", 1)[0]
        if p.startswith("/vendor/three/"):
            return str(THREE_DIR / p[len("/vendor/three/"):])
        return super().translate_path(path)

    def log_message(self, *args) -> None:
        pass


def start_p260_server() -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(P260Handler, directory=str(P260_DIR)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def wait_http(url: str, proc=None, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            out, _ = proc.communicate()
            raise RuntimeError(f"Server exited early ({proc.returncode}): {out.decode('utf-8', 'ignore')}")
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}")


def capture_5_screenshots_and_hero_render() -> dict:
    http_port, ws_port, rpc_port = get_free_ports(3)
    sim_proc = subprocess.Popen(
        [
            sys.executable, "-u", "-m", "rov01sim.server",
            "--http-port", str(http_port),
            "--ws-port", str(ws_port),
            "--rpc-port", str(rpc_port),
            "--scenario", "mission_1_pool",
            "--seed", "42",
            "--release-mode",
        ],
        cwd=str(BOX_RUN),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    p260_srv, p260_url = start_p260_server()
    arena_verification = {}

    try:
        wait_http(f"http://127.0.0.1:{http_port}/index.html", sim_proc)
        wait_http(f"{p260_url}/index.html")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )
            page = context.new_page()
            console_errors: list[str] = []
            asset_urls: list[str] = []
            page.on("console", lambda m: console_errors.append(m.text) if (m.type == "error" and "404" not in m.text) else None)
            page.on("pageerror", lambda e: console_errors.append(str(e)))
            page.on("request", lambda r: asset_urls.append(r.url))

            page.goto(
                f"http://127.0.0.1:{http_port}/index.html?play=1&model=rov01&ws=ws://127.0.0.1:{ws_port}&nointro=1&cam=orbit",
                wait_until="networkidle",
            )
            deadline = time.time() + 30.0
            while time.time() < deadline:
                ready = page.evaluate("() => !!(window.__modelLoaded && window.__viewer?.S?.wave1 && window.__arenaHud)")
                if ready:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError(f"Simulator viewer did not become ready. Console errors: {console_errors}")

            # Verify /arena 3-Candidate HUD switching via F2, pill click, and API
            initial_theme = page.evaluate("() => window.__wave1.getHudTheme()")
            page.keyboard.press("F2")
            after_f2_theme = page.evaluate("() => window.__wave1.getHudTheme()")
            page.click("#w1ArenaPresetPill")
            after_pill_theme = page.evaluate("() => window.__wave1.getHudTheme()")
            page.keyboard.press("F2")
            cycled_back_theme = page.evaluate("() => window.__wave1.getHudTheme()")

            widgets_present = page.evaluate("""() => ({
                hasHexRadar: !!document.getElementById('arenaHexRadar'),
                hasUtAScan: !!document.getElementById('arenaUtAScan'),
                hasTetherBar: !!document.getElementById('arenaTetherBarFill'),
                hasRpmSpectrum: !!document.getElementById('arenaRpmSpectrum'),
                hasSplitTimer: !!document.getElementById('arenaSplitTimer'),
                hasDiegeticFrame: !!document.getElementById('arenaDiegeticFrame'),
                presetOrder: window.__arenaHud.ORDER,
            })""")
            arena_verification = {
                "initial_theme": initial_theme,
                "after_f2_theme": after_f2_theme,
                "after_pill_theme": after_pill_theme,
                "cycled_back_theme": cycled_back_theme,
                "widgets_present": widgets_present,
            }
            assert initial_theme == "TACTICAL_SONAR", f"Expected TACTICAL_SONAR initial, got {initial_theme}"
            assert after_f2_theme == "INDUSTRIAL_P260", f"Expected INDUSTRIAL_P260 after F2, got {after_f2_theme}"
            assert after_pill_theme == "STEAM_DIEGETIC", f"Expected STEAM_DIEGETIC after pill click, got {after_pill_theme}"
            assert cycled_back_theme == "TACTICAL_SONAR", f"Expected TACTICAL_SONAR after cycle, got {cycled_back_theme}"
            assert all(widgets_present.values()), f"Missing grafted widgets: {widgets_present}"

            def switch_mission(mid: str) -> None:
                page.evaluate(f"() => window.__wave1.selectMission('{mid}')")
                dl = time.time() + 15.0
                while time.time() < dl:
                    if page.evaluate("() => window.__viewer?.S?.wave1?.mission_id") == mid:
                        break
                    time.sleep(0.15)

            def frame_rov01_hero(dist_z: float = 0.78, side_x: float = 0.68, up_y: float = 0.34) -> None:
                page.evaluate(f"""() => {{
                    const v = window.__viewer;
                    v.setCam('orbit');
                    const p = v.rovG.position;
                    if (v.controls) {{
                        v.controls.target.copy(p);
                        v.camera.position.set(p.x + {side_x}, p.y + {up_y}, p.z + {dist_z});
                        v.controls.update();
                    }} else {{
                        v.camera.position.set(p.x + {side_x}, p.y + {up_y}, p.z + {dist_z});
                        v.camera.lookAt(p.x, p.y, p.z);
                    }}
                }}""")

            def assert_brand_clean(label: str, pg) -> None:
                dom_text = pg.evaluate("() => document.body.innerText")
                m = FORBIDDEN_RE.search(dom_text)
                if m:
                    raise AssertionError(f"[CORR-ROV-01] Forbidden brand token {m.group(0)!r} in {label}")

            # 1. Screenshot 1: M1 Pool 6DoF + Candidate A (TACTICAL_SONAR)
            switch_mission("mission_1_pool")
            page.evaluate("() => window.__wave1.setHudTheme('TACTICAL_SONAR')")
            page.evaluate("""() => {
                window.__wave1.setDepthHold(true, 2.5);
                window.__wave1.setHeadingHold(true, 45.0);
                window.__wave1.inject6Dof({ surge: 0.74, sway: -0.32, heave: 0.28, roll: 0.15, pitch: -0.22, yaw: 0.46 }, 0.08, 0.35);
            }""")
            time.sleep(0.45)
            frame_rov01_hero(dist_z=0.76, side_x=0.66, up_y=0.33)
            time.sleep(0.25)
            assert_brand_clean("M1", page)
            page.screenshot(path=str(OUT_DIR / "steam_ss_01_m1_pool_6dof.png"))

            # Also capture a clean 3D ROV-01 crop with HUD temporarily hidden for capsule compositing
            page.evaluate("""() => {
                document.querySelectorAll('header.topbar, aside.rack, .hud, #w1HudBanner, #sticks, #labels, #arenaDiegeticFrame').forEach(el => {
                    el.dataset.prevVis = el.style.visibility || '';
                    el.style.visibility = 'hidden';
                });
            }""")
            frame_rov01_hero(dist_z=0.64, side_x=0.58, up_y=0.26)
            time.sleep(0.2)
            raw_hero_path = OUT_DIR / "_tmp_raw_rov01_webgl.png"
            page.screenshot(path=str(raw_hero_path))
            page.evaluate("""() => {
                document.querySelectorAll('header.topbar, aside.rack, .hud, #w1HudBanner, #sticks, #labels, #arenaDiegeticFrame').forEach(el => {
                    el.style.visibility = el.dataset.prevVis || '';
                });
            }""")

            # 2. Screenshot 2: M2 Hull UT Gauging + Candidate B (INDUSTRIAL_P260)
            page.evaluate("() => { window.__wave1.setDepthHold(false); window.__wave1.setHeadingHold(false); }")
            switch_mission("mission_2_hull_ut")
            time.sleep(0.5)
            page.evaluate("() => window.__wave1.setHudTheme('INDUSTRIAL_P260')")
            page.evaluate("() => { const b = document.getElementById('banner'); if (b) b.hidden = true; }")
            for cp_id in ["UT-01", "UT-02", "UT-03", "UT-04"]:
                page.evaluate(f"() => window.__wave1.sampleUt('{cp_id}')")
                time.sleep(0.12)
            page.evaluate("""() => {
                window.__wave1.inject6Dof({ surge: 0.58, sway: 0.18, heave: -0.20, roll: 0.0, pitch: 0.12, yaw: -0.25 }, 0.08, 0.35);
            }""")
            time.sleep(0.45)
            frame_rov01_hero(dist_z=0.74, side_x=-0.62, up_y=0.30)
            time.sleep(0.25)
            assert_brand_clean("M2", page)
            page.screenshot(path=str(OUT_DIR / "steam_ss_02_m2_hull_ut_gauging.png"))

            # 3. Screenshot 3: M3 Deep SAR T3 Fault + Candidate A (TACTICAL_SONAR)
            switch_mission("mission_3_sar_fault")
            time.sleep(0.55)
            page.evaluate("() => window.__wave1.setHudTheme('TACTICAL_SONAR')")
            page.evaluate("() => { const b = document.getElementById('banner'); if (b) b.hidden = true; }")
            page.evaluate("() => window.__wave1.injectThrusterFault(2, true)")
            page.evaluate("() => window.__wave1.injectCollision(0.95, 'front-stbd')")
            page.evaluate("() => window.__wave1.triggerEmergencyReturn(true)")
            page.evaluate("""() => {
                window.__wave1.inject6Dof({ surge: 0.82, sway: 0.35, heave: -0.45, roll: 0.0, pitch: 0.15, yaw: 0.38 }, 0.08, 0.35);
            }""")
            time.sleep(0.65)
            frame_rov01_hero(dist_z=-0.74, side_x=0.66, up_y=0.35)
            time.sleep(0.25)
            assert_brand_clean("M3", page)
            page.screenshot(path=str(OUT_DIR / "steam_ss_03_m3_deep_sar_t3_fault.png"))

            # 4. Screenshot 4: M4 Pipeline Time-Trial + Candidate C (STEAM_DIEGETIC)
            switch_mission("mission_4_pipeline")
            time.sleep(0.55)
            page.evaluate("() => { const b = document.getElementById('banner'); if (b) b.hidden = true; }")
            page.evaluate("() => window.__wave1.clearFaults()")
            page.evaluate("() => window.__wave1.triggerEmergencyReturn(false)")
            page.evaluate("() => window.__wave1.setHudTheme('STEAM_DIEGETIC')")
            page.evaluate("""() => {
                window.__wave1.inject6Dof({ surge: 0.92, sway: -0.24, heave: 0.16, roll: 0.08, pitch: -0.10, yaw: 0.28 }, 0.08, 0.35);
            }""")
            time.sleep(0.5)
            frame_rov01_hero(dist_z=0.78, side_x=0.70, up_y=0.34)
            time.sleep(0.25)
            assert_brand_clean("M4", page)
            page.screenshot(path=str(OUT_DIR / "steam_ss_04_m4_pipeline_time_trial.png"))

            assert len(console_errors) == 0, f"Unexpected console errors: {console_errors}"

            # 5. Screenshot 5: P260 Dual-Viewport ROV-01 + Multibeam / OBS CAM
            p260_page = context.new_page()
            p260_errs: list[str] = []
            p260_page.on("pageerror", lambda e: p260_errs.append(str(e)))
            p260_page.goto(f"{p260_url}/index.html", wait_until="networkidle")
            time.sleep(2.2)
            assert_brand_clean("P260", p260_page)
            assert len(p260_errs) == 0, f"P260 page errors: {p260_errs}"
            p260_page.screenshot(path=str(OUT_DIR / "steam_ss_05_p260_dual_viewport.png"))

            browser.close()
    finally:
        p260_srv.shutdown()
        sim_proc.terminate()
        try:
            sim_proc.wait(timeout=4)
        except Exception:
            sim_proc.kill()

    return arena_verification


# ==============================================================================
# Procedural Subsea & ROV-01 Illustration + WebGL Composite for 8 Steam Capsules
# ==============================================================================

def build_underwater_scene_canvas(width: int, height: int, rov_crop: Image.Image | None, hero_layout: str = "center_right") -> Image.Image:
    """Create a rich deep-sea engineering key art canvas (100% text-free) featuring:
    - Deep-ocean bathymetric gradient (#020813 -> #072235 -> #0e4459)
    - Volumetric surface caustics & dual LED floodlight cones (#BAE6FD / #22D3EE)
    - Subsea jacket truss structure & pipeline silhouette in background
    - Acoustic multibeam sonar sweep rings (#22D3EE & #10B981)
    - High-contrast 3-Layer Sandwich ROV-01 render + procedural rim enhancements
    """
    base = Image.new("RGBA", (width, height), (3, 12, 24, 255))
    draw = ImageDraw.Draw(base, "RGBA")

    # 1. Vertical deep-water gradient bands
    steps = 120
    for i in range(steps):
        t = i / max(1, steps - 1)
        y0 = int(i * height / steps)
        y1 = int((i + 1) * height / steps) + 1
        r = int(14 * (1 - t) ** 1.6 + 2 * t)
        g = int(76 * (1 - t) ** 1.4 + 11 * t)
        b = int(104 * (1 - t) ** 1.2 + 22 * t)
        draw.rectangle([0, y0, width, y1], fill=(r, g, b, 255))

    # 2. Subsea jacket structure & pipeline silhouettes in background
    truss_col = (10, 38, 56, 150)
    pipe_y = int(height * 0.78)
    pipe_h = max(18, int(height * 0.065))
    draw.rectangle([0, pipe_y, width, pipe_y + pipe_h], fill=(12, 34, 48, 210), outline=(34, 211, 238, 65), width=2)
    # Anode bands on subsea pipeline
    for px in range(int(width * 0.08), width, max(80, int(width * 0.14))):
        draw.rectangle([px, pipe_y - 2, px + max(12, int(width * 0.015)), pipe_y + pipe_h + 2], fill=(56, 189, 248, 165))

    # Offshore jacket diagonal bracing lines
    for k in range(6):
        x_base = int(width * (0.12 + k * 0.16))
        draw.line([(x_base, 0), (x_base - int(height * 0.22), height)], fill=truss_col, width=max(3, int(width * 0.004)))
        draw.line([(x_base - int(height * 0.18), 0), (x_base + int(height * 0.12), height)], fill=(14, 48, 68, 110), width=max(2, int(width * 0.0025)))

    # 3. Sonar bathymetry & polar sweep arcs (pure geometry, ZERO text)
    if hero_layout == "center_right":
        rov_cx, rov_cy = int(width * 0.64), int(height * 0.52)
    elif hero_layout == "center":
        rov_cx, rov_cy = int(width * 0.50), int(height * 0.48)
    elif hero_layout == "right":
        rov_cx, rov_cy = int(width * 0.72), int(height * 0.52)
    else:  # hero_wide for 3840x1240
        rov_cx, rov_cy = int(width * 0.54), int(height * 0.52)

    sonar_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sonar_layer, "RGBA")
    max_r = int(min(width, height) * 0.58)
    for idx, frac in enumerate([0.28, 0.46, 0.66, 0.86, 1.05]):
        rad = int(max_r * frac)
        alpha = max(18, 72 - idx * 12)
        col = (34, 211, 238, alpha) if idx % 2 == 0 else (16, 185, 129, alpha)
        sdraw.ellipse([rov_cx - rad, rov_cy - rad, rov_cx + rad, rov_cy + rad], outline=col, width=max(1, int(height * 0.0022)))

    # Volumetric dual LED floodlight cones & UT green laser beam projecting from ROV bow
    beam_len = int(width * 0.42)
    beam_spread = int(height * 0.34)
    sdraw.polygon(
        [
            (rov_cx + int(height * 0.06), rov_cy - int(height * 0.03)),
            (rov_cx + beam_len, rov_cy - beam_spread),
            (rov_cx + beam_len, rov_cy + int(beam_spread * 0.65)),
        ],
        fill=(186, 230, 253, 38),
    )
    sdraw.polygon(
        [
            (rov_cx + int(height * 0.08), rov_cy + int(height * 0.04)),
            (rov_cx + int(beam_len * 0.85), rov_cy - int(beam_spread * 0.25)),
            (rov_cx + int(beam_len * 0.85), rov_cy + beam_spread),
        ],
        fill=(34, 211, 238, 44),
    )
    sonar_layer = sonar_layer.filter(ImageFilter.GaussianBlur(radius=max(2, int(height * 0.008))))
    base = Image.alpha_composite(base, sonar_layer)

    # 4. Composite WebGL ROV-01 3D render crop + crisp technical vector overlay of ROV-01 3-layer sandwich
    if rov_crop is not None:
        target_h = int(height * (0.64 if hero_layout != "small" else 0.82))
        aspect = rov_crop.width / max(1, rov_crop.height)
        target_w = int(target_h * aspect)
        resized_rov = rov_crop.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Circular soft alpha mask around the WebGL ROV-01 render
        mask = Image.new("L", (target_w, target_h), 0)
        mdraw = ImageDraw.Draw(mask)
        for r_step in range(100, 0, -2):
            f = r_step / 100.0
            rx = int(target_w * 0.46 * f)
            ry = int(target_h * 0.46 * f)
            a_val = int(255 * (1.0 - f ** 2.4))
            mdraw.ellipse([target_w // 2 - rx, target_h // 2 - ry, target_w // 2 + rx, target_h // 2 + ry], fill=a_val)

        enh = ImageEnhance.Contrast(resized_rov).enhance(1.22)
        enh = ImageEnhance.Brightness(enh).enhance(1.12)
        paste_x = rov_cx - target_w // 2
        paste_y = rov_cy - target_h // 2
        base.paste(enh, (paste_x, paste_y), mask)

    # 5. Crisp high-resolution vector overlay of ROV-01's signature 3-Layer Sandwich silhouette
    #    so the ROV is razor-sharp even at 3840x1240 and 462x174!
    v_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vd = ImageDraw.Draw(v_layer, "RGBA")
    sc = height * (0.00105 if hero_layout != "small" else 0.00145)
    if width < height:  # vertical capsules
        sc = width * 0.00125

    def pt(dx: float, dy: float) -> tuple[int, int]:
        return (int(rov_cx + dx * sc), int(rov_cy + dy * sc))

    # Subsea Cyber-Cyan Tether catenary curve trailing from stern (-dx) (#38BDF8 / #22D3EE)
    tether_pts = [
        pt(-420 - i * 45, -30 - int(85 * math.sin(i * 0.25) + i * 18))
        for i in range(14)
    ]
    if len(tether_pts) >= 2:
        vd.line([pt(-170, -18)] + tether_pts, fill=(56, 189, 248, 235), width=max(3, int(6 * sc)))

    # Bottom Layer: CNC Titanium Skids (#1E293B) + Anodized Trim (#38BDF8) + Bronze DVL Sonar Windows (#B45309)
    vd.rounded_rectangle([pt(-175, 76), pt(185, 98)], radius=max(3, int(6 * sc)), fill=(30, 41, 59, 248), outline=(56, 189, 248, 210), width=max(1, int(2 * sc)))
    vd.rounded_rectangle([pt(-65, 62), pt(35, 86)], radius=max(3, int(5 * sc)), fill=(15, 23, 42, 250), outline=(56, 189, 248, 220), width=max(1, int(2 * sc)))
    for bx in (-42, -16, 10):
        vd.ellipse([pt(bx - 8, 69), pt(bx + 8, 82)], fill=(34, 211, 238, 255))

    # Middle Layer: Matte Carbon Black Pressure Hull (#0F172A) + Optical Dome + Anodized Aluminum Kort Nozzles (#38BDF8)
    vd.rounded_rectangle([pt(-145, -34), pt(145, 52)], radius=max(6, int(18 * sc)), fill=(15, 23, 42, 252), outline=(56, 189, 248, 215), width=max(1, int(2.5 * sc)))
    # Acrylic bow camera dome
    vd.pieslice([pt(105, -36), pt(195, 50)], start=-90, end=90, fill=(14, 116, 144, 195), outline=(56, 189, 248, 255), width=max(2, int(3 * sc)))
    # Anodized Subsea Aluminum Trim (#38BDF8) Kort Thruster Shrouds (Fore & Aft) + Cyan Thrust Plume
    for tx in (-130, 85):
        vd.rounded_rectangle([pt(tx, -22), pt(tx + 58, 44)], radius=max(4, int(8 * sc)), fill=(56, 189, 248, 255), outline=(224, 242, 254, 235), width=max(1, int(2 * sc)))
        vd.line([pt(tx + 29, -16), pt(tx + 29, 38)], fill=(51, 65, 85, 255), width=max(2, int(4 * sc)))
    # Hydrodynamic cyan thruster plume behind shrouds
    vd.polygon([pt(-135, -10), pt(-320, -52), pt(-320, 68), pt(-135, 30)], fill=(34, 211, 238, 95))

    # Open Tubular Carbon-Titanium Crash Frame Stanchions (#1E293B) + Reflective Engineering Tape Bands (#F8FAFC)
    for sx in (-165, -55, 55, 165):
        vd.rectangle([pt(sx - 5, -52), pt(sx + 5, 78)], fill=(30, 41, 59, 255))
        if abs(sx) > 100:
            vd.rectangle([pt(sx - 6, -18), pt(sx + 6, -4)], fill=(248, 250, 252, 255))
            vd.rectangle([pt(sx - 6, 36), pt(sx + 6, 50)], fill=(248, 250, 252, 255))

    # Top Layer: 45-degree Chamfered High-Visibility Marine Cyber Cyan Syntactic Buoyancy Block (#06B6D4 / #22D3EE)
    buoy_poly = [
        pt(-172, -48),
        pt(172, -48),
        pt(172, -88),
        pt(142, -114),
        pt(-142, -114),
        pt(-172, -88),
    ]
    vd.polygon(buoy_poly, fill=(6, 182, 212, 255), outline=(34, 211, 238, 255))
    # Reflective engineering strip on buoyancy block (#F8FAFC) + Anodized Trim (#38BDF8)
    vd.rectangle([pt(-95, -88), pt(95, -73)], fill=(248, 250, 252, 248))
    vd.rectangle([pt(-145, -56), pt(145, -48)], fill=(56, 189, 248, 255))

    # Forward 316L Stainless UT Probe + Coupled Emerald Glow Ring (#10B981)
    vd.rectangle([pt(165, 52), pt(255, 60)], fill=(203, 213, 225, 255))
    vd.rectangle([pt(250, 44), pt(272, 68)], fill=(148, 163, 184, 255))
    vd.ellipse([pt(268, 40), pt(286, 72)], fill=(16, 185, 129, 255), outline=(167, 243, 208, 255), width=max(1, int(2 * sc)))

    # Dual Subsea LED Floodlight Hotspots at Bow
    vd.ellipse([pt(158, -56), pt(186, -28)], fill=(224, 242, 254, 255), outline=(56, 189, 248, 255), width=max(1, int(2 * sc)))

    base = Image.alpha_composite(base, v_layer)

    # 6. Underwater particulate scatter (marine snow / acoustic backscatter dots — pure visual, zero text)
    p_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(p_layer, "RGBA")
    for i in range(95):
        px = (i * 197 + 43) % width
        py = (i * 131 + 29) % height
        pr = 1 + (i % 3)
        pcol = (34, 211, 238, 95) if i % 3 == 0 else (226, 232, 240, 65)
        pdraw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=pcol)
    base = Image.alpha_composite(base, p_layer)
    return base


def draw_brand_lockup(
    img: Image.Image,
    title_xy: tuple[int, int],
    title_size: int,
    sub_size: int,
    tag_size: int = 0,
    align: str = "left",
    show_tags: bool = True,
) -> None:
    """Draw Valve-compliant ROV-01 brand title lockup (no review scores, no awards, no discount tags)."""
    draw = ImageDraw.Draw(img, "RGBA")
    f_title = load_font(FONT_TITLE_PATH, title_size)
    f_sub = load_font(FONT_SUB_PATH, sub_size)
    f_tag = load_font(FONT_MONO_PATH, max(10, tag_size)) if tag_size > 0 else None

    tx, ty = title_xy

    # Dark backing glow for legibility
    if align == "center":
        bbox_t = draw.textbbox((0, 0), "ROV-01", font=f_title)
        tw = bbox_t[2] - bbox_t[0]
        tx_draw = tx - tw // 2
    else:
        tx_draw = tx

    # Technical eyebrow badge
    if show_tags and f_tag:
        badge_text = "6DoF SUBSEA INSPECTION & FAULT REALLOCATION SIMULATOR"
        bb = draw.textbbox((0, 0), badge_text, font=f_tag)
        bw, bh = bb[2] - bb[0] + 18, bb[3] - bb[1] + 10
        bx = (tx - bw // 2) if align == "center" else tx_draw
        by = ty - bh - int(title_size * 0.14)
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=5, fill=(9, 22, 36, 225), outline=(34, 211, 238, 220), width=2)
        draw.text((bx + 9, by + 4), badge_text, font=f_tag, fill=(34, 211, 238, 255))

    # Main Title: "ROV-01" with Safety Amber accent bar
    draw.text((tx_draw + 3, ty + 4), "ROV-01", font=f_title, fill=(2, 6, 23, 230))
    draw.text((tx_draw, ty), "ROV-01", font=f_title, fill=(248, 250, 252, 255))

    sub_text = "SUBSEA ENGINEERING & SAR SIMULATOR"
    sub_y = ty + int(title_size * 1.02)
    if align == "center":
        sb = draw.textbbox((0, 0), sub_text, font=f_sub)
        sx_draw = tx - (sb[2] - sb[0]) // 2
    else:
        sx_draw = tx_draw
    draw.text((sx_draw + 2, sub_y + 2), sub_text, font=f_sub, fill=(2, 6, 23, 230))
    draw.text((sx_draw, sub_y), sub_text, font=f_sub, fill=(56, 189, 248, 255))


def generate_8_steam_capsules() -> list[dict]:
    raw_hero_path = OUT_DIR / "_tmp_raw_rov01_webgl.png"
    rov_crop = None
    if raw_hero_path.exists():
        raw_img = Image.open(raw_hero_path).convert("RGBA")
        # Crop central 3D ROV-01 area from the 1920x1080 HUD-free render
        rov_crop = raw_img.crop((420, 120, 1500, 960))

    capsules_spec = [
        ("main_capsule_1232x706.png", 1232, 706),
        ("header_capsule_920x430.png", 920, 430),
        ("small_capsule_462x174.png", 462, 174),
        ("vertical_capsule_748x896.png", 748, 896),
        ("library_capsule_600x900.png", 600, 900),
        ("library_header_920x430.png", 920, 430),
        ("library_hero_3840x1240.png", 3840, 1240),
        ("library_logo_1280x720.png", 1280, 720),
    ]

    # 1. main_capsule_1232x706.png (1232 x 706)
    img_main = build_underwater_scene_canvas(1232, 706, rov_crop, hero_layout="center_right")
    draw_brand_lockup(img_main, (58, 235), title_size=118, sub_size=28, tag_size=15, align="left", show_tags=True)
    img_main.convert("RGB").save(OUT_DIR / "main_capsule_1232x706.png", "PNG", optimize=True)

    # 2. header_capsule_920x430.png (920 x 430)
    img_hdr = build_underwater_scene_canvas(920, 430, rov_crop, hero_layout="right")
    draw_brand_lockup(img_hdr, (42, 138), title_size=86, sub_size=21, tag_size=12, align="left", show_tags=True)
    img_hdr.convert("RGB").save(OUT_DIR / "header_capsule_920x430.png", "PNG", optimize=True)

    # 3. small_capsule_462x174.png (462 x 174)
    img_sm = build_underwater_scene_canvas(462, 174, rov_crop, hero_layout="small")
    draw_brand_lockup(img_sm, (18, 36), title_size=52, sub_size=13, tag_size=0, align="left", show_tags=False)
    img_sm.convert("RGB").save(OUT_DIR / "small_capsule_462x174.png", "PNG", optimize=True)

    # 4. vertical_capsule_748x896.png (748 x 896)
    img_vert = build_underwater_scene_canvas(748, 896, rov_crop, hero_layout="center")
    draw_brand_lockup(img_vert, (374, 650), title_size=96, sub_size=22, tag_size=13, align="center", show_tags=True)
    img_vert.convert("RGB").save(OUT_DIR / "vertical_capsule_748x896.png", "PNG", optimize=True)

    # 5. library_capsule_600x900.png (600 x 900)
    img_lib_cap = build_underwater_scene_canvas(600, 900, rov_crop, hero_layout="center")
    draw_brand_lockup(img_lib_cap, (300, 665), title_size=82, sub_size=18, tag_size=11, align="center", show_tags=True)
    img_lib_cap.convert("RGB").save(OUT_DIR / "library_capsule_600x900.png", "PNG", optimize=True)

    # 6. library_header_920x430.png (920 x 430)
    img_lib_hdr = build_underwater_scene_canvas(920, 430, rov_crop, hero_layout="right")
    draw_brand_lockup(img_lib_hdr, (42, 142), title_size=84, sub_size=20, tag_size=12, align="left", show_tags=True)
    img_lib_hdr.convert("RGB").save(OUT_DIR / "library_header_920x430.png", "PNG", optimize=True)

    # 7. library_hero_3840x1240.png (3840 x 1240 — Valve rule: PURE ARTWORK, ZERO TEXT / ZERO LOGO)
    img_lib_hero = build_underwater_scene_canvas(3840, 1240, rov_crop, hero_layout="hero_wide")
    img_lib_hero.convert("RGB").save(OUT_DIR / "library_hero_3840x1240.png", "PNG", optimize=True)

    # 8. library_logo_1280x720.png (1280 x 720 — TRANSPARENT RGBA PNG logo: ROV-01: SUBSEA ENGINEERING & SAR SIMULATOR)
    img_logo = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(img_logo, "RGBA")
    # Draw crisp ROV-01 hex sonar emblem + bold typography on transparent background
    cx, cy = 640, 320
    # Top hexagonal sonar badge on transparent canvas
    hex_r = 54
    hex_pts = [
        (cx + int(hex_r * math.cos(-math.pi / 2 + i * math.pi / 3)),
         150 + int(hex_r * math.sin(-math.pi / 2 + i * math.pi / 3)))
        for i in range(6)
    ]
    ldraw.polygon(hex_pts, fill=(9, 22, 36, 235), outline=(34, 211, 238, 255))
    ldraw.ellipse([cx - 22, 150 - 22, cx + 22, 150 + 22], outline=(56, 189, 248, 255), width=4)
    ldraw.ellipse([cx - 6, 150 - 6, cx + 6, 150 + 6], fill=(16, 185, 129, 255))

    f_logo_main = load_font(FONT_TITLE_PATH, 168)
    f_logo_sub = load_font(FONT_SUB_PATH, 36)
    main_txt = "ROV-01"
    sub_txt = "ROV-01: SUBSEA ENGINEERING & SAR SIMULATOR"

    mb = ldraw.textbbox((0, 0), main_txt, font=f_logo_main)
    mx = cx - (mb[2] - mb[0]) // 2
    my = 225
    ldraw.text((mx + 4, my + 5), main_txt, font=f_logo_main, fill=(2, 6, 23, 220))
    ldraw.text((mx, my), main_txt, font=f_logo_main, fill=(248, 250, 252, 255))

    # Accent divider bar
    ldraw.rounded_rectangle([cx - 290, 422, cx + 290, 430], radius=4, fill=(34, 211, 238, 255))

    sb = ldraw.textbbox((0, 0), sub_txt, font=f_logo_sub)
    sx = cx - (sb[2] - sb[0]) // 2
    sy = 450
    ldraw.text((sx + 2, sy + 3), sub_txt, font=f_logo_sub, fill=(2, 6, 23, 220))
    ldraw.text((sx, sy), sub_txt, font=f_logo_sub, fill=(56, 189, 248, 255))

    img_logo.save(OUT_DIR / "library_logo_1280x720.png", "PNG", optimize=True)

    if raw_hero_path.exists():
        raw_hero_path.unlink()

    results = []
    for fname, exp_w, exp_h in capsules_spec:
        fpath = OUT_DIR / fname
        with Image.open(fpath) as im:
            w, h = im.size
            mode = im.mode
            assert (w, h) == (exp_w, exp_h), f"Dimension mismatch for {fname}: got {w}x{h}, expected {exp_w}x{exp_h}"
            if fname == "library_logo_1280x720.png":
                assert mode == "RGBA", f"Logo must be RGBA, got {mode}"
                assert im.getpixel((0, 0))[3] == 0, "Logo top-left corner must be transparent (alpha=0)"
        results.append({
            "file": fname,
            "width": w,
            "height": h,
            "mode": mode,
            "bytes": fpath.stat().st_size,
        })
    return results


def verify_all_outputs(arena_info: dict, capsule_results: list[dict]) -> dict:
    expected_screenshots = [
        ("steam_ss_01_m1_pool_6dof.png", 1920, 1080),
        ("steam_ss_02_m2_hull_ut_gauging.png", 1920, 1080),
        ("steam_ss_03_m3_deep_sar_t3_fault.png", 1920, 1080),
        ("steam_ss_04_m4_pipeline_time_trial.png", 1920, 1080),
        ("steam_ss_05_p260_dual_viewport.png", 1920, 1080),
    ]
    ss_results = []
    for fname, exp_w, exp_h in expected_screenshots:
        fpath = OUT_DIR / fname
        assert fpath.exists(), f"Missing screenshot {fpath}"
        with Image.open(fpath) as im:
            w, h = im.size
            mode = im.mode
        assert (w, h) == (exp_w, exp_h), f"Screenshot {fname} expected {exp_w}x{exp_h}, got {w}x{h}"
        ss_results.append({
            "file": fname,
            "width": w,
            "height": h,
            "mode": mode,
            "bytes": fpath.stat().st_size,
        })

    summary = {
        "arena_hud_verification": arena_info,
        "screenshots_1920x1080": ss_results,
        "steam_capsules": capsule_results,
    }
    (OUT_DIR / "steam_assets_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    arena_info = capture_5_screenshots_and_hero_render()
    capsule_results = generate_8_steam_capsules()
    summary = verify_all_outputs(arena_info, capsule_results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("STEAM_ASSETS_AND_ARENA_HUD_COMPLETE=PASS")
