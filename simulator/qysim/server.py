"""Simulator host process.

    python -m qysim.server [--scenario jacket_inspection] [--seed 42]

Services (all on localhost by default):
    SDK RPC    tcp  :9760   JSON lines, used by the mock ``qysea`` package
    Viewer WS  ws   :8765   state stream to the 3D viewer, RC/commands back
    Static     http :8080   serves viewer/ (and the ROV model)

See PROTOCOL.md for message formats.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import json
import os
import socketserver
import threading
import time
import traceback
from pathlib import Path

import numpy as np

from .engine import Simulator
from .rc import CHANNELS
from .qirc import QircControls

ROOT = Path(__file__).resolve().parents[1]
VIEWER_DIR = ROOT / "viewer"
MODEL_FALLBACK = ROOT.parent / "sim"          # repo sim/rov.glb


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def dumps(obj) -> str:
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


class SimHost:
    def __init__(self, sim: Simulator, rate_hz: float = 100.0, view_hz: float = 30.0, qirc: bool = False):
        self.sim = sim
        self.rate_hz = rate_hz
        self.view_hz = view_hz
        self.lock = asyncio.Lock()
        self.viewers: set = set()
        self.world_version = 0
        self.qirc_enabled = qirc
        self.controller_connected = False
        self.controller_generation = 0
        self.controller_last_sample = 0.0
        self.controller_samples = 0
        self.controller_reason = "等待 USB 遙控器"
        self.controller_raw = ()
        self.controller_controls = QircControls()
        self.controller_revision = 0
        self.controller_buttons = {"photo": 0, "record": 0}
        self.viewer_buttons = {"photo": 0, "record": 0}

    def controller_offline(self, reason):
        if self.controller_connected:
            self.controller_generation += 1
        self.controller_connected = False
        self.controller_reason = reason
        self.sim.rc_physical.centre_sticks()
        self.sim.rc_physical.rc_lock = 1
        self.sim.rc_physical.photo = self.sim.rc_physical.record = 0
        self.controller_controls.reset()
        self.controller_buttons = {"photo": 0, "record": 0}
        self.viewer_buttons = {"photo": 0, "record": 0}

    def check_controller(self, now=None):
        if self.qirc_enabled and self.controller_connected:
            if (time.monotonic() if now is None else now) - self.controller_last_sample > 0.6:
                self.controller_offline("USB 搖桿資料逾時，已回中並上鎖")

    async def controller_sample(self, axes, raw):
        async with self.lock:
            if not self.controller_connected:
                self.controller_generation += 1
                self.sim.rc_physical.rc_lock = 1
            self.controller_connected = True
            self.controller_last_sample = time.monotonic()
            self.controller_samples += 1
            self.controller_raw = tuple(raw)
            self.controller_reason = "Q-iRC USB 已連接"
            values = axes
            if len(raw) >= 23:
                values = self.controller_controls.update(raw, self.sim.rc_physical)
                for key in ("photo", "record"):
                    self.controller_buttons[key] = values[key]
                    values[key] = int(bool(values[key] or self.viewer_buttons[key]))
            if any(key in values and values[key] != getattr(self.sim.rc_physical, key)
                   for key in ("rc_lock", "keep_depth", "left_switch", "right_switch")):
                self.controller_revision += 1
            self.sim.apply_viewer_rc(values)
            if not self.sim.remote_control:
                # Preserve short press/release pairs coalesced in one USB read.
                self.sim._buttons(self.sim.rc_physical)

    async def controller_status(self, reason):
        async with self.lock:
            self.controller_offline(reason)
        print(f"[qirc] {reason}", flush=True)

    def viewer_state(self):
        state = self.sim.viewer_state()
        if self.qirc_enabled:
            state["controller"] = {
                "name": "Q-iRC USB", "connected": self.controller_connected,
                "generation": self.controller_generation, "samples": self.controller_samples,
                "revision": self.controller_revision,
                "reason": self.controller_reason,
                "raw_channels": self.controller_raw,
                "axes": {key: getattr(self.sim.rc_physical, key) for key in CHANNELS},
            }
        return state

    # ── physics loop ──────────────────────────────────────────────────────
    async def physics_loop(self):
        dt = 1.0 / self.rate_hz
        nxt = time.perf_counter()
        while True:
            async with self.lock:
                try:
                    self.check_controller()
                    self.sim.step(dt)
                except Exception:
                    traceback.print_exc()
            nxt += dt
            delay = nxt - time.perf_counter()
            if delay < -0.25:            # fell far behind: resync instead of spiralling
                nxt = time.perf_counter()
                delay = 0
            await asyncio.sleep(max(0.0, delay))

    # ── SDK RPC ───────────────────────────────────────────────────────────
    async def rpc_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    req = json.loads(line)
                    rid = req.get("id")
                    async with self.lock:
                        result = self.handle_rpc(req)
                    resp = {"id": rid, "ok": True, "result": result}
                except Exception as e:
                    resp = {"id": req.get("id") if isinstance(req, dict) else None, "ok": False,
                            "error": f"{type(e).__name__}: {e}"}
                writer.write((dumps(resp) + "\n").encode())
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    def handle_rpc(self, req: dict):
        kind = req.get("type", "sdk")
        if kind == "sdk":
            return self.sim.sdk_call(req["cls"], req["method"], req.get("args", []), req.get("kwargs", {}))
        if kind == "camera_view":
            # pose + scene for client-side frame rendering
            s = self.sim.vehicle.s
            pose = self.sim.file_pose(req["file_path"]) if req.get("file_path") else None
            return {"pos": s.pos.tolist(), "q": s.q.tolist(), "pose": pose,
                    "visibility_m": self.sim.scenario.visibility_m, "silt": self.sim.world.silt,
                    "led": self.sim.rc.right_switch, "seabed_depth": self.sim.world.seabed_depth,
                    "obstacles": [o.as_dict() for o in self.sim.world.obstacles],
                    "tether": self.sim.tether.x.tolist()}
        if kind == "state":
            return self.viewer_state()
        if kind == "ping":
            return "pong"
        raise ValueError(f"unknown request type {kind!r}")

    # ── viewer WebSocket ─────────────────────────────────────────────────
    async def viewer_handler(self, ws):
        self.viewers.add(ws)
        button_values = self.sim.rc_physical.as_dict()
        try:
            await ws.send(dumps({"type": "world", **self.sim.world_description()}))
            sender = asyncio.create_task(self._viewer_sender(ws))
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                async with self.lock:
                    reply = self.handle_viewer(msg, button_values)
                if reply:
                    await ws.send(dumps(reply))
            sender.cancel()
        except Exception:
            pass
        finally:
            self.viewers.discard(ws)

    async def _viewer_sender(self, ws):
        seen_version = self.world_version
        while True:
            world = None
            async with self.lock:                 # snapshot under the lock, send outside it
                if seen_version != self.world_version:
                    seen_version = self.world_version
                    world = dumps({"type": "world", **self.sim.world_description()})
                payload = dumps({"type": "state", **self.viewer_state()})
            if world:
                await ws.send(world)
            await ws.send(payload)
            await asyncio.sleep(1.0 / self.view_hz)

    def handle_viewer(self, msg: dict, button_values: dict | None = None):
        t = msg.get("type")
        sim = self.sim
        if t == "rc":
            values = msg.get("rc", {})
            if self.qirc_enabled:
                # Browser heartbeat may update buttons, never overwrite USB axes.
                values = {key: value for key, value in values.items() if key not in CHANNELS}
                if button_values is not None:
                    changed = {key: value for key, value in values.items() if button_values.get(key) != value}
                    button_values.update(values)
                    values = changed
                for key in ("photo", "record"):
                    if key in values:
                        self.viewer_buttons[key] = int(bool(values[key]))
                        values[key] = int(bool(values[key] or self.controller_buttons[key]))
                if (not self.controller_connected or
                        msg.get("controller_generation") != self.controller_generation):
                    values["rc_lock"] = 1
            sim.apply_viewer_rc(values)
        elif t == "scenario":
            seed = msg.get("seed")
            sim.load_scenario(msg.get("key", "open_water"), int(seed) if seed not in (None, "") else None)
            self.world_version += 1
            self.controller_controls.reset()
            self.controller_generation += 1
        elif t == "reset":
            sim.load_scenario(sim.scenario.key, sim.scenario.seed)
            self.world_version += 1
            self.controller_controls.reset()
            self.controller_generation += 1
        elif t == "pause":
            sim.paused = bool(msg.get("value", not sim.paused))
        elif t == "payout":
            sim.tether.payout(float(msg.get("metres", 0.0)))
        elif t == "auto_payout":
            sim.tether.auto_payout = bool(msg.get("value", True))
        elif t == "operation_mode":
            sim.sdk_call("QYRovParameterManage", "set_rov_controller_operation", [msg.get("value", "ROV_USA")], {})
        elif t == "current":
            cur = sim.world.current
            for k in ("surface_kn", "surface_dir", "mid_kn", "mid_dir", "bottom_kn", "bottom_dir", "turbulence"):
                if k in msg:
                    setattr(cur, k, float(msg[k]))
            self.world_version += 1
        elif t == "shaping":
            for k in ("throttle_curvature", "throttle_limit", "rotate_curvature", "rotate_limit"):
                if k in msg:
                    setattr(sim.shaping, k, int(msg[k]))
            sim.shaping.custom = True
        elif t == "remote_release":
            sim.sdk_call("QYRovControllerManage", "set_remote_control_status", ["OFF"], {})
        return None


class _Static(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(VIEWER_DIR), **k)

    def translate_path(self, path):
        p = super().translate_path(path)
        if not os.path.exists(p):
            alt = MODEL_FALLBACK / os.path.basename(path.split("?")[0])
            if alt.exists():
                return str(alt)
        return p

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


def start_static(port: int, host: str) -> None:
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer((host, port), _Static)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()


async def main_async(args):
    import websockets
    sim = Simulator(args.scenario, args.seed)
    host = SimHost(sim, qirc=args.qirc)
    rpc = await asyncio.start_server(host.rpc_client, args.host, args.rpc_port)
    ws = await websockets.serve(host.viewer_handler, args.host, args.ws_port, max_size=2 ** 22)
    if not args.no_http:
        start_static(args.http_port, args.host)
    print(f"[qysim] scenario={sim.scenario.name}  SDK rpc tcp://{args.host}:{args.rpc_port}  "
          f"viewer ws://{args.host}:{args.ws_port}  http://{args.host}:{args.http_port}/", flush=True)
    async with rpc:
        tasks = [host.physics_loop(), rpc.serve_forever(), ws.wait_closed()]
        if args.qirc:
            from .qirc import QircReader
            reader = QircReader(adb=args.adb, serial=args.qirc_serial)
            tasks.append(reader.run(host.controller_sample, host.controller_status))
        await asyncio.gather(*tasks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="X1 ROV simulator host")
    ap.add_argument("--scenario", default="open_water")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--rpc-port", type=int, default=int(os.environ.get("QYSIM_RPC_PORT", 9760)))
    ap.add_argument("--ws-port", type=int, default=8765)
    ap.add_argument("--http-port", type=int, default=8080)
    ap.add_argument("--no-http", action="store_true")
    ap.add_argument("--qirc", action="store_true", help="Read original Q-iRC through authorized USB ADB")
    ap.add_argument("--adb", default=None, help="Path to Android Platform Tools adb")
    ap.add_argument("--qirc-serial", default=None, help="Select one Q-iRC when several are connected")
    args = ap.parse_args(argv)
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
