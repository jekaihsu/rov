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
    def __init__(self, sim: Simulator, rate_hz: float = 100.0, view_hz: float = 30.0):
        self.sim = sim
        self.rate_hz = rate_hz
        self.view_hz = view_hz
        self.lock = asyncio.Lock()
        self.viewers: set = set()
        self.world_version = 0

    # ── physics loop ──────────────────────────────────────────────────────
    async def physics_loop(self):
        dt = 1.0 / self.rate_hz
        nxt = time.perf_counter()
        while True:
            async with self.lock:
                try:
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
            return self.sim.viewer_state()
        if kind == "ping":
            return "pong"
        raise ValueError(f"unknown request type {kind!r}")

    # ── viewer WebSocket ─────────────────────────────────────────────────
    async def viewer_handler(self, ws):
        self.viewers.add(ws)
        try:
            await ws.send(dumps({"type": "world", **self.sim.world_description()}))
            sender = asyncio.create_task(self._viewer_sender(ws))
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                async with self.lock:
                    reply = self.handle_viewer(msg)
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
                payload = dumps({"type": "state", **self.sim.viewer_state()})
            if world:
                await ws.send(world)
            await ws.send(payload)
            await asyncio.sleep(1.0 / self.view_hz)

    def handle_viewer(self, msg: dict):
        t = msg.get("type")
        sim = self.sim
        if t == "rc":
            sim.apply_viewer_rc(msg.get("rc", {}))
        elif t == "scenario":
            seed = msg.get("seed")
            sim.load_scenario(msg.get("key", "open_water"), int(seed) if seed not in (None, "") else None)
            self.world_version += 1
        elif t == "reset":
            sim.load_scenario(sim.scenario.key, sim.scenario.seed)
            self.world_version += 1
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
    host = SimHost(sim)
    rpc = await asyncio.start_server(host.rpc_client, args.host, args.rpc_port)
    ws = await websockets.serve(host.viewer_handler, args.host, args.ws_port, max_size=2 ** 22)
    if not args.no_http:
        start_static(args.http_port, args.host)
    print(f"[qysim] scenario={sim.scenario.name}  SDK rpc tcp://{args.host}:{args.rpc_port}  "
          f"viewer ws://{args.host}:{args.ws_port}  http://{args.host}:{args.http_port}/", flush=True)
    async with rpc:
        await asyncio.gather(host.physics_loop(), rpc.serve_forever(), ws.wait_closed())


def main(argv=None):
    ap = argparse.ArgumentParser(description="X1 ROV simulator host")
    ap.add_argument("--scenario", default="open_water")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--rpc-port", type=int, default=int(os.environ.get("QYSIM_RPC_PORT", 9760)))
    ap.add_argument("--ws-port", type=int, default=8765)
    ap.add_argument("--http-port", type=int, default=8080)
    ap.add_argument("--no-http", action="store_true")
    args = ap.parse_args(argv)
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
