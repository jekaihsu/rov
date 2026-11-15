"""Shared helpers for sdk_mock sandbox examples.

Live bridge talks to a running qysim server over TCP (and optional viewer WebSocket).
Local bridge drives ``qysim.engine.Simulator`` in-process for fast headless tests:
one control tick advances simulation time without waiting on the wall clock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Allow ``python examples/xxx.py`` from simulator/sdk_mock without an external PYTHONPATH.
_SDK_ROOT = Path(__file__).resolve().parents[1]
_SIM_ROOT = _SDK_ROOT.parent
for _path in (str(_SDK_ROOT), str(_SIM_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

STRINGS = {
    "remote_on": "遠端控制已取得",
    "remote_off": "遠端控制已釋放",
    "dvl_offline": "DVL 失鎖，改為只定深",
    "dvl_online": "DVL 恢復，恢復巡航",
    "no_echo": "前向測距無回波（最大量程）",
    "blind": "前向測距落在盲區",
}


def configure_rpc(host: str, port: int) -> None:
    """Point the mock SDK client at a host/port (process-wide env used by ``_client``)."""
    os.environ["QYSIM_HOST"] = host
    os.environ["QYSIM_RPC_PORT"] = str(port)
    from qysea.sdk import _client
    with _client._clients_lock:
        for key, client in list(_client._clients.items()):
            client.close()
            _client._clients.pop(key, None)


class LocalBridge:
    """In-process SDK surface for tests: ``sdk_call`` + deterministic ``step``."""

    def __init__(self, scenario: str = "open_water", seed: int = 1, sensor_ideal: bool = False):
        from qysim.engine import Simulator
        from qysim.sensors import SensorConfig
        self.sim = Simulator(scenario, seed=seed, sensor_config=SensorConfig(ideal=sensor_ideal))
        self.vision = {"available": False, "detections": [], "age_s": 0.0}
        self._vision_t = None

    def sdk(self, cls: str, method: str, *args, **kwargs):
        return self.sim.sdk_call(cls, method, list(args), dict(kwargs))

    def advance(self, seconds: float) -> None:
        steps = max(1, int(round(seconds / self.sim.dt)))
        for _ in range(steps):
            self.sim.step()

    def sleep_or_advance(self, seconds: float) -> None:
        self.advance(seconds)

    def sim_time(self) -> float:
        return self.sim.t

    def post_vision(self, detections: list) -> None:
        self.vision = {"available": True, "detections": list(detections), "age_s": 0.0}
        self._vision_t = self.sim.t

    def get_vision(self) -> dict:
        if self._vision_t is None:
            return {"available": False, "detections": []}
        age = self.sim.t - self._vision_t
        if age > 1.0:
            return {"available": False, "detections": [], "age_s": age}
        return {"available": True, "detections": self.vision["detections"], "age_s": age}

    def get_frame_bgr(self, width: int = 320, height: int = 180):
        from qysea.sdk._render import render
        s = self.sim.vehicle.s
        view = {
            "pos": s.pos.tolist(),
            "q": s.q.tolist(),
            "visibility_m": self.sim.scenario.visibility_m,
            "seabed_depth": self.sim.world.seabed_depth,
            "obstacles": [o.as_dict() for o in self.sim.world.obstacles],
            "led": self.sim.rc.right_switch,
            "silt": self.sim.world.silt_at(s.pos),
            "tether": self.sim.tether.x.tolist(),
        }
        return render(view, width, height, osd=False, t_now=1.0 + self.sim.t)


class LiveBridge:
    """TCP mock-SDK + optional viewer WebSocket for ``vision_results``."""

    def __init__(self, host: str, rpc_port: int, ws_port: int | None = None):
        configure_rpc(host, rpc_port)
        self.host = host
        self.rpc_port = rpc_port
        self.ws_port = ws_port
        self._ws = None
        self._t0 = time.monotonic()
        from qysea.sdk.manage.QY_Rov_Manage import QYRovRealTimeStatusManage
        from qysea.sdk.manage.QY_RovController_Manage import QYRovControllerManage
        from qysea.sdk.manage.QY_Camera_Manage import QYCameraMediaStreamManage
        self.status_api = QYRovRealTimeStatusManage()
        self.controller = QYRovControllerManage()
        self.camera = QYCameraMediaStreamManage()
        self.status_api.connect_to_rov()

    def sdk(self, cls: str, method: str, *args, **kwargs):
        from qysea.sdk._client import call
        return call(cls, method, args, kwargs)

    def advance(self, seconds: float) -> None:
        time.sleep(seconds)

    def sleep_or_advance(self, seconds: float) -> None:
        time.sleep(seconds)

    def sim_time(self) -> float:
        return time.monotonic() - self._t0

    def _ensure_ws(self):
        if self._ws is not None:
            return
        if self.ws_port is None:
            raise RuntimeError("vision WebSocket requires --ws-port")
        from websockets.sync.client import connect
        self._ws = connect(f"ws://{self.host}:{self.ws_port}")
        self._ws.send(json.dumps({"type": "join", "name": "sdk_sandbox_vision"}))
        while True:
            reply = json.loads(self._ws.recv())
            if reply.get("type") == "session":
                break

    def post_vision(self, detections: list) -> None:
        self._ensure_ws()
        self._ws.send(json.dumps({"type": "vision_results", "detections": detections}))

    def get_vision(self) -> dict:
        return self.camera.get_sim_detections()

    def get_frame_bgr(self, width: int = 320, height: int = 180):
        # Live path uses the camera manage stream (size fixed by stream flag).
        got = self.camera.capture_video("MAIN_CAMERA", "SUB_STREAM")
        if got is not True:
            raise RuntimeError(got)
        ok, frame = self.camera.get_frame()
        if not ok or frame is None:
            raise RuntimeError("get_frame failed")
        return frame

    def close(self) -> None:
        try:
            self.camera.close_video()
        except Exception:
            pass
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None


def take_remote(bridge) -> None:
    bridge.sdk("QYRovControllerManage", "set_remote_control_status", "ON")
    bridge.sdk("QYRovControllerManage", "set_rc_lock_button", 0)
    bridge.sdk("QYRovControllerManage", "set_keep_depth_button", 1)
    bridge.sdk("QYRovControllerManage", "set_left_switch", 0)  # A mode
    for channel in (
        "set_left_joystick_up_down",
        "set_left_joystick_left_right",
        "set_right_joystick_up_down",
        "set_right_joystick_left_right",
        "set_left_wave_left_right",
        "set_right_wave_left_right",
    ):
        bridge.sdk("QYRovControllerManage", channel, 1500)


def release_remote(bridge) -> None:
    for channel in (
        "set_left_joystick_up_down",
        "set_left_joystick_left_right",
        "set_right_joystick_up_down",
        "set_right_joystick_left_right",
        "set_left_wave_left_right",
        "set_right_wave_left_right",
    ):
        bridge.sdk("QYRovControllerManage", channel, 1500)
    bridge.sdk("QYRovControllerManage", "set_keep_depth_button", 0)
    bridge.sdk("QYRovControllerManage", "set_rc_lock_button", 1)
    bridge.sdk("QYRovControllerManage", "set_remote_control_status", "OFF")


def get_status(bridge) -> dict:
    if isinstance(bridge, LocalBridge):
        return bridge.sim.sdk_status()
    status = bridge.status_api.get_rov_status()
    if not isinstance(status, dict) or status.get("status") != "ok":
        raise RuntimeError(f"get_rov_status failed: {status!r}")
    return status


def angle_error_deg(target: float, current: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


def clamp_pwm(value: float, low: int = 1100, high: int = 1900) -> int:
    return int(max(low, min(high, round(value))))


def add_host_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="127.0.0.1", help="simulator host")
    parser.add_argument("--port", type=int, default=9760, help="SDK RPC port")
    parser.add_argument("--ws-port", type=int, default=8765, help="viewer WebSocket port")
    parser.add_argument("--seconds", type=float, default=30.0, help="run duration (sim or wall)")
    parser.add_argument("--local", action="store_true", help="in-process simulator (tests)")
    parser.add_argument("--scenario", default="open_water")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--ideal-sensors", action="store_true", help="local only: QYSIM ideal sensors")


def make_bridge(args) -> LocalBridge | LiveBridge:
    if args.local:
        return LocalBridge(scenario=args.scenario, seed=args.seed, sensor_ideal=args.ideal_sensors)
    return LiveBridge(args.host, args.port, ws_port=getattr(args, "ws_port", None))


def print_result(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
