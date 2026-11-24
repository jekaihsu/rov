"""Simulator host process.

    python -m rov01sim.server [--scenario jacket_inspection] [--seed 42]

Services (all on localhost by default):
    SDK RPC    tcp  :9760   JSON lines, used by the SDK-compat client shim
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
import re
import secrets
import socketserver
import threading
import time
import traceback
import weakref
from pathlib import Path

import numpy as np

from .engine import Simulator
from .rc import CHANNELS
from .usb_rc import UsbRcControls
from .room import Room
from .simready_usd import get_simready_usda_payload, load_simready_catalog_dict

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
    return json.dumps(obj, default=_json_default, ensure_ascii=False, separators=(",", ":"))


class SimHost:
    def __init__(self, sim: Simulator, rate_hz: float = 100.0, view_hz: float = 30.0, usb_rc: bool = False):
        self.sim = sim
        self.room = Room(sim)
        self.rooms = {self.room.id: self.room}
        self._wire_snapshots = weakref.WeakKeyDictionary()
        self.sessions = {}
        self.bridges = {}
        self.rpc_connections = 0
        self.rate_hz = rate_hz
        self.view_hz = view_hz
        self.lock = asyncio.Lock()
        self.viewers: set = set()
        self.world_version = 0
        self.usb_rc_enabled = usb_rc
        self.controller_connected = False
        self.controller_generation = 0
        self.controller_last_sample = 0.0
        self.controller_samples = 0
        self.controller_reason = "等待 USB 遙控器"
        self.controller_raw = ()
        self.controller_controls = UsbRcControls()
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
        if self.usb_rc_enabled and self.controller_connected:
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
            self.controller_reason = "USB 控制器已連接"
            values = axes
            if len(raw) >= 23:
                values = self.controller_controls.update(raw, self.sim.rc_physical)
                for key in ("photo", "record"):
                    self.controller_buttons[key] = values[key]
                    values[key] = int(bool(values[key] or self.viewer_buttons[key]))
            if any(key in values and values[key] != getattr(self.sim.rc_physical, key)
                   for key in ("rc_lock", "keep_depth", "left_switch", "right_switch")):
                self.controller_revision += 1
            if self.sim.input_latched:
                if values.get("rc_lock") == 1:
                    self.sim.input_latched = False
                else:
                    values["rc_lock"] = 1
            self.sim.apply_viewer_rc(values)
            if not self.sim.remote_control:
                # Preserve short press/release pairs coalesced in one USB read.
                self.sim._buttons(self.sim.rc_physical)

    async def controller_status(self, reason):
        async with self.lock:
            self.controller_offline(reason)
        print(f"[usb-rc] {reason}", flush=True)

    def viewer_state(self, room=None, player=None):
        room = room or self.room
        state = room.state(player)
        bridge = self.bridges.get((room.id, player.id)) if player else None
        if bridge is not None:
            sim = room.vehicles[player.vehicle_id]
            state["controller"] = {"name": "USB 網路橋接", "bridge": True,
                "connected": time.monotonic() - bridge["last_input"] < .6,
                "reason": "USB 遙控器已配對至此座席",
                "generation": player.generation, "revision": player.bridge_seq,
                "axes": {key: getattr(sim.rc_physical, key) for key in CHANNELS}}
        if self.usb_rc_enabled and room is self.room and (player is None or player.vehicle_id == "v1"):
            state["controller"] = {
                "name": "ROV-01 USB Controller", "connected": self.controller_connected,
                "generation": self.controller_generation, "samples": self.controller_samples,
                "revision": self.controller_revision,
                "reason": self.controller_reason,
                "raw_channels": self.controller_raw,
                "axes": {key: getattr(self.sim.rc_physical, key) for key in CHANNELS},
            }
        return state

    def world_description(self, room=None, player=None):
        room = room or self.room
        sim = room.vehicles[player.vehicle_id] if player else room.primary
        return {**sim.world_description(), "room": {"id": room.id, "host_id": room.host_id,
                "capacity": room.capacity,
                "players": [{"id": p.id, "vehicle_id": p.vehicle_id, "name": p.name,
                             "connected": p.connected} for p in room.players.values()]},
                "is_host": player is not None and player.id == room.host_id}

    def viewer_payload(self, room=None, player=None):
        """Encode a fleet snapshot once while retaining the complete v2 wire state.

        Each viewer still receives its own top-level telemetry and every fleet
        member. Only immutable serialized fragments are shared between senders;
        room membership and USB controller metadata are read on every call.
        Call while holding the host lock, like viewer_state().
        """
        room = room or self.room
        state = self.viewer_state(room, player)
        fleet = state.pop("vehicles")
        cached = self._wire_snapshots.get(room)
        if cached is None or cached[0] is not fleet:
            entries = {item["vehicle_id"]: (item, dumps(item)) for item in fleet}
            fleet_json = "[" + ",".join(encoded for _, encoded in entries.values()) + "]"
            cached = (fleet, entries, fleet_json)
            self._wire_snapshots[room] = cached
        base, encoded = cached[1][state["vehicle_id"]]
        # Normal state is a shallow copy of this vehicle plus recipient metadata.
        # Fall back if a future controller adapter replaces any existing field.
        if all(key in state and state[key] is value for key, value in base.items()):
            extras = {key: value for key, value in state.items() if key not in base}
            body = encoded[1:-1]
            if extras:
                body += "," + dumps(extras)[1:-1]
        else:
            body = dumps(state)[1:-1]
        return '{"type":"state",' + body + ',"vehicles":' + cached[2] + "}"

    def should_step_room(self, room):
        """Retain the local SDK room without spending CPU on an unused simulator."""
        if room is not self.room:
            return True
        sim = room.primary
        return bool(room.players or self.usb_rc_enabled or self.rpc_connections or
                    sim.remote_control or sim.nav.mode != "IDLE" or sim.nav.hold is not None or
                    sim.camera.recording_since is not None or
                    getattr(getattr(sim, "wave1", None), "emergency_return_active", False) or
                    getattr(getattr(sim, "wave1", None), "direct_6dof_active", False))

    # ── physics loop ──────────────────────────────────────────────────────
    async def physics_loop(self):
        dt = 1.0 / self.rate_hz
        nxt = time.perf_counter()
        while True:
            async with self.lock:
                try:
                    self.check_controller()
                    for room_id, room in list(self.rooms.items()):
                        room.check_timeouts(usb_vehicle="v1" if self.usb_rc_enabled and room is self.room else None)
                        for player in room.players.values():
                            bridge = self.bridges.get((room.id, player.id))
                            if bridge and time.monotonic() - bridge["last_input"] >= .6:
                                room.lock(room.vehicles[player.vehicle_id])
                        if room is not self.room and not room.players:
                            del self.rooms[room_id]
                            continue
                        if self.should_step_room(room):
                            room.step(dt)
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
        self.rpc_connections += 1
        try:
            while True:
                req = None
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
            self.rpc_connections -= 1
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
                    "visibility_m": self.sim.scenario.visibility_m, "silt": self.sim.world.silt_at(s.pos),
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
        sender = None
        try:
            await ws.send(dumps({"type": "world", **self.world_description()}))
            sender = asyncio.create_task(self._viewer_sender(ws))
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    if not isinstance(msg, dict):
                        raise ValueError("message must be an object")
                except ValueError:
                    continue
                async with self.lock:
                    try:
                        if msg.get("type") == "attach_controller":
                            reply = self.attach_controller(ws, msg)
                            room, player, _ = self.sessions[ws]
                        elif msg.get("type") == "leave":
                            session = self.sessions.pop(ws, None)
                            if session:
                                room, player, generation = session
                                bridge = self.bridges.get((room.id, player.id))
                                if bridge and bridge["ws"] is ws:
                                    self.bridges.pop((room.id, player.id), None)
                                    room.lock(room.vehicles[player.vehicle_id])
                                else:
                                    room.disconnect(player, generation)
                            reply = {"type": "command_result", "action": "leave", "ok": True}
                        elif msg.get("type") == "join":
                            reply = self.join_viewer(ws, msg)
                            room, player, _ = self.sessions[ws]
                            button_values = room.vehicles[player.vehicle_id].rc_physical.as_dict()
                        elif msg.get("type") == "wave1":
                            session = self.sessions.get(ws)
                            room, player = (session[0], session[1]) if session else (self.room, None)
                            reply = self.handle_viewer(msg, button_values, room=room, player=player)
                            if msg.get("action") == "select_mission":
                                await ws.send(dumps({"type": "world", **self.world_description(room, player)}))
                        else:
                            session = self.sessions.get(ws)
                            if session is None:
                                reply = {"type": "error", "code": "join_required", "message": "請先加入房間"}
                            else:
                                room, player, generation = session
                                if generation != player.generation or not player.connected:
                                    reply = {"type": "error", "code": "session_replaced", "message": "此控制席已重新連線"}
                                else:
                                    bridge = self.bridges.get((room.id, player.id))
                                    is_bridge = bridge is not None and bridge["ws"] is ws
                                    if is_bridge and msg.get("type") != "rc":
                                        reply = {"type": "error", "code": "controller_only", "message": "橋接僅可傳送遙控輸入"}
                                    else:
                                        reply = self.handle_viewer(msg, button_values, room=room, player=player,
                                                                   controller_bridge=is_bridge)
                                        if is_bridge and reply is None:
                                            bridge["last_input"] = time.monotonic()
                    except (ValueError, TypeError, KeyError, OverflowError) as exc:
                        reply = {"type": "error", "code": "invalid_command", "message": str(exc)}
                if reply:
                    await ws.send(dumps(reply))
                    if reply.get("type") == "session":
                        await ws.send(dumps({"type": "world", **self.world_description(room, player)}))
        except Exception:
            pass
        finally:
            if sender is not None:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
            async with self.lock:
                session = self.sessions.pop(ws, None)
                if session:
                    room, player, generation = session
                    bridge = self.bridges.get((room.id, player.id))
                    if bridge and bridge["ws"] is ws:
                        self.bridges.pop((room.id, player.id), None)
                        room.lock(room.vehicles[player.vehicle_id])
                    else:
                        room.disconnect(player, generation)
            self.viewers.discard(ws)

    def attach_controller(self, ws, msg):
        if ws in self.sessions:
            raise ValueError("A controller bridge needs a fresh connection")
        room = self.rooms.get(str(msg.get("room_id", "training")))
        token = str(msg.get("resume_token", ""))
        player = next((p for p in room.players.values() if p.connected and secrets.compare_digest(p.token, token)), None) if room else None
        if player is None:
            raise ValueError("controller_pairing_invalid")
        key = (room.id, player.id)
        if key in self.bridges:
            raise ValueError("controller_already_attached")
        if room is self.room and player.vehicle_id == "v1" and self.usb_rc_enabled:
            raise ValueError("local_controller_already_attached")
        player.bridge_seq = -1
        room.lock(room.vehicles[player.vehicle_id])
        self.bridges[key] = {"ws": ws, "last_input": time.monotonic()}
        self.sessions[ws] = (room, player, player.generation)
        return {"type": "controller_session", "vehicle_id": player.vehicle_id, "generation": player.generation}

    def join_viewer(self, ws, msg):
        from .vehicles import get_vehicle_definition
        from .tooling import validate_loadout
        room_id = str(msg.get("room_id", "training"))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", room_id):
            raise ValueError("房間代碼須為 1–32 個英數字、底線或連字號")
        model_id = str(msg.get("model_id", "rov01"))
        get_vehicle_definition(model_id)
        requested_loadout=validate_loadout(model_id,msg['loadout']) if 'loadout' in msg else None
        if ws in self.sessions:
            old_room, old_player, old_generation = self.sessions[ws]
            if old_room.id == room_id:
                return old_room.session(old_player)
        if room_id not in self.rooms:
            if len(self.rooms) >= 8:
                raise ValueError("server_rooms_full")
            self.rooms[room_id] = Room(Simulator(self.sim.scenario.key, self.sim.scenario.seed), room_id)
        room = self.rooms[room_id]
        player = room.join(msg.get("name", "Pilot"), msg.get("resume_token"), model_id)
        if requested_loadout is not None and player.generation==1:
            room.vehicles[player.vehicle_id].tools.install(requested_loadout)
        if ws in self.sessions:
            old_room.disconnect(old_player, old_generation)
        self.sessions[ws] = (room, player, player.generation)
        self.world_version += 1
        return room.session(player)

    async def _viewer_sender(self, ws):
        seen_version = self.world_version
        while True:
            world = None
            async with self.lock:                 # snapshot under the lock, send outside it
                session = self.sessions.get(ws)
                room, player = (session[0], session[1]) if session else (self.room, None)
                if seen_version != self.world_version:
                    seen_version = self.world_version
                    sim = room.vehicles[player.vehicle_id] if player else room.primary
                    world = dumps({"type": "world", **self.world_description(room, player)})
                payload = self.viewer_payload(room, player)
            if world:
                await ws.send(world)
            await ws.send(payload)
            await asyncio.sleep(1.0 / self.view_hz)

    def handle_viewer(self, msg: dict, button_values: dict | None = None, *, room=None, player=None, controller_bridge=False):
        t = msg.get("type")
        if t == "latency_probe":
            return {"type":"latency_reply", "sent":msg.get("sent")}
        room = room or self.room
        sim = room.vehicles[player.vehicle_id] if player else room.primary
        if player is not None and t in ("scenario", "reset", "pause", "current") and player.id != room.host_id:
            return {"type": "error", "code": "host_only", "message": "只有房主可以變更共同場景"}
        if t == "operation" and msg.get("action") in ("mission_mode", "expedition_start", "expedition_cancel") and (player is None or player.id != room.host_id):
            return {"type": "error", "code": "host_only", "message": "只有房主可以變更共同任務"}
        if t == "rc":
            if player is not None and not room.input(player, msg.get("seq"), bridge=controller_bridge):
                return {"type": "error", "code": "stale_input", "message": "控制封包序號已過期"}
            values = msg.get("rc", {})
            if not isinstance(values, dict):
                raise ValueError("rc must be an object")
            if any(not isinstance(v, (int, float)) or not np.isfinite(v) for v in values.values()):
                raise ValueError("RC values must be finite numbers")
            bridge = self.bridges.get((room.id, player.id)) if player else None
            if bridge and not controller_bridge:
                # The browser may deliberately change buttons, but cannot overwrite USB axes.
                values = {k: v for k, v in values.items() if k not in CHANNELS}
                if button_values is not None:
                    changed = {k: v for k, v in values.items() if button_values.get(k) != v}
                    button_values.update(values)
                    values = changed
                if time.monotonic() - bridge["last_input"] >= .6:
                    values["rc_lock"] = 1
            if self.usb_rc_enabled and room is self.room and sim is self.sim:
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
            if sim.input_latched:
                # A delayed unlocked heartbeat must never undo a failsafe lock.
                # Synchronize a locked command first, then require a later unlock.
                if values.get("rc_lock") == 1:
                    sim.input_latched = False
                else:
                    values["rc_lock"] = 1
            sim.apply_viewer_rc(values)
            if not sim.remote_control:
                # Preserve short camera button edges when several network packets
                # arrive between physics ticks, just as the local USB reader does.
                sim._buttons(sim.rc_physical)
        elif t == "scenario":
            seed = msg.get("seed")
            room.reset(msg.get("key", "open_water"), int(seed) if seed not in (None, "") else None)
            self.world_version += 1
            if room is self.room:
                self.controller_controls.reset()
                self.controller_generation += 1
        elif t == "reset":
            room.reset()
            self.world_version += 1
            if room is self.room:
                self.controller_controls.reset()
                self.controller_generation += 1
        elif t == "pause":
            paused = bool(msg.get("value", not sim.paused))
            for vehicle in room.vehicles.values():
                vehicle.paused = paused
        elif t == "model":
            room.select_model(sim.vehicle_id, str(msg.get("model_id", "rov01")))
            self.world_version += 1
        elif t == "operation":
            return {"type": "operation_result", **sim.operations.command(msg)}
        elif t == "payout":
            metres = float(msg.get("metres", 0.0))
            if not np.isfinite(metres):
                raise ValueError("Payout must be finite")
            sim.tether.payout(max(-100.0, min(100.0, metres)))
        elif t == "auto_payout":
            sim.tether.auto_payout = bool(msg.get("value", True))
        elif t == "operation_mode":
            sim.sdk_call("RovParameterManage", "set_rov_controller_operation", [msg.get("value", "ROV_USA")], {})
        elif t == "current":
            cur = sim.world.current
            changes = {}
            for k in ("surface_kn", "surface_dir", "mid_kn", "mid_dir", "bottom_kn", "bottom_dir", "turbulence"):
                if k in msg:
                    value = float(msg[k])
                    if not np.isfinite(value):
                        raise ValueError("Current must be finite")
                    limit = 360.0 if k.endswith("dir") else 3.0 if k == "turbulence" else 10.0
                    changes[k] = max(0.0, min(limit, value))
            for key, value in changes.items():
                setattr(cur, key, value)
            self.world_version += 1
        elif t == "shaping":
            for k in ("throttle_curvature", "throttle_limit", "rotate_curvature", "rotate_limit"):
                if k in msg:
                    setattr(sim.shaping, k, max(0, min(100, int(msg[k]))))
            sim.shaping.custom = True
        elif t == "remote_release":
            sim.sdk_call("RovControllerManage", "set_remote_control_status", ["OFF"], {})
        elif t == "wave1":
            action = msg.get("action")
            w1 = sim.wave1
            if action == "gamepad_6dof":
                w1.apply_gamepad_6dof(msg.get("axes", {}), msg.get("deadzone"), msg.get("expo"))
            elif action == "inject_fault":
                w1.inject_thruster_fault(msg.get("thruster_index", 2), bool(msg.get("jammed", True)))
            elif action == "clear_faults":
                w1.inject_thruster_fault(None, False)
            elif action == "emergency_return":
                w1.trigger_emergency_return(bool(msg.get("enable", True)))
            elif action == "collision_impulse":
                w1.inject_collision_impulse(float(msg.get("speed_mps", 0.85)), str(msg.get("zone", "front-stbd")))
            elif action == "hazard_params":
                w1.set_hazard_params(
                    current_kn=msg.get("current_kn"),
                    current_dir=msg.get("current_dir"),
                    turbidity_ntu=msg.get("turbidity_ntu"),
                )
            elif action == "sample_ut":
                w1.sample_ut_checkpoint(msg.get("checkpoint_id"))
            elif action == "start_ut_coupling":
                w1.start_ut_coupling(
                    msg.get("checkpoint_id"),
                    tilt_deg=float(msg.get("tilt_deg", 1.4)),
                    distance_m=float(msg.get("distance_m", 0.42)),
                )
            elif action == "depth_hold":
                w1.set_depth_hold(bool(msg.get("enable", True)), msg.get("target_depth_m"))
            elif action == "heading_hold":
                w1.set_heading_hold(bool(msg.get("enable", True)), msg.get("target_heading_deg"))
            elif action == "emergency_surface":
                w1.trigger_emergency_surface(bool(msg.get("enable", True)))
            elif action == "inject_tether_snag":
                w1.inject_tether_snag()
            elif action == "resolve_tether_snag":
                w1.resolve_tether_snag()
            elif action == "select_mission":
                mission_id = str(msg.get("mission_id", "mission_1_pool"))
                room.reset(mission_id, msg.get("seed"))
                for v_sim in room.vehicles.values():
                    v_sim.wave1.mission_id = mission_id
                    v_sim.wave1.ut_state = "ut_searching"
                    v_sim.wave1.ut_hold_elapsed_s = 0.0
                    v_sim.rc_physical.rc_lock = 0
                self.world_version += 1
            elif action in ("campaign_action", "cable_campaign"):
                sub_action = str(msg.get("sub_action") or msg.get("campaign_action") or "status")
                res = w1.handle_campaign_action(sub_action, msg)
                room._snapshot = None
                return {"type": "wave1_result", "action": action, **res}
            elif action == "simready_collide":
                res = w1.collide_simready_asset(
                    str(msg.get("asset_id") or "SR-IND-01"),
                    msg.get("impact_speed_mps"),
                )
                room._snapshot = None
                return {"type": "wave1_result", "action": action, **res}
            elif action == "simready_teleport":
                res = w1.teleport_to_simready_asset(str(msg.get("asset_id") or "SR-IND-01"))
                room._snapshot = None
                return {"type": "wave1_result", "action": action, **res}
            elif action in ("b2b_roster", "get_b2b_roster"):
                return {"type": "b2b_roster_result", "action": action, **sim.wave1.get_b2b_roster()}
            elif action in ("b2b_record_run", "record_b2b_run"):
                cert = sim.wave1.record_b2b_run(
                    trainee_id=str(msg.get("trainee_id", "YX-PILOT-NEW")),
                    trainee_name=str(msg.get("trainee_name", msg.get("name", "Pilot Trainee"))),
                    department=str(msg.get("department", msg.get("cohort", "永祥水下工程部 (Subsea Ops)"))),
                    timestamp=msg.get("timestamp"),
                )
                return {"type": "b2b_record_result", "action": action, **cert}
            room._snapshot = None
            return {"type": "wave1_result", "action": action, "ok": True, "wave1": sim.wave1.state()}
        if t in ("scenario", "reset", "pause", "current", "model"):
            return {"type": "command_result", "action": t, "ok": True}
        return None


_ACTIVE_SIM_HOST: SimHost | None = None


def _get_or_create_sim_host() -> SimHost:
    global _ACTIVE_SIM_HOST
    if _ACTIVE_SIM_HOST is None:
        _ACTIVE_SIM_HOST = SimHost(Simulator("mission_2_hull_ut", seed=42))
    return _ACTIVE_SIM_HOST


def handle_b2b_api_request(
    method: str,
    path: str,
    body: dict | bytes | str | None = None,
    sim_host: SimHost | None = None,
) -> tuple[int, dict]:
    """Handle B2B REST API requests (/api/b2b/roster and /api/b2b/record_run)."""
    clean_path = path.split("?")[0].rstrip("/")
    host = sim_host or _get_or_create_sim_host()
    w1 = host.sim.wave1

    if method.upper() == "GET" and clean_path == "/api/b2b/roster":
        return 200, w1.get_b2b_roster()

    if method.upper() == "POST" and clean_path == "/api/b2b/record_run":
        if isinstance(body, (bytes, bytearray)):
            raw_text = body.decode("utf-8", errors="replace").strip()
            payload = json.loads(raw_text) if raw_text else {}
        elif isinstance(body, str):
            raw_text = body.strip()
            payload = json.loads(raw_text) if raw_text else {}
        elif isinstance(body, dict):
            payload = dict(body)
        else:
            payload = {}

        trainee_id = str(payload.get("trainee_id", "")).strip() or "YX-PILOT-NEW"
        trainee_name = str(payload.get("trainee_name", payload.get("name", payload.get("handle", "")))).strip() or "Pilot Trainee"
        department = str(payload.get("department", payload.get("cohort", "永祥水下工程部 (Subsea Ops)"))).strip()
        timestamp = payload.get("timestamp")
        cert = w1.record_b2b_run(
            trainee_id=trainee_id,
            trainee_name=trainee_name,
            department=department,
            timestamp=timestamp,
        )
        return 200, cert

    return 404, {"ok": False, "error": f"Unknown B2B endpoint: {method} {clean_path}"}


def handle_simready_api_request(
    method: str,
    path: str,
    body: dict | bytes | str | None = None,
    sim_host: SimHost | None = None,
) -> tuple[int, dict]:
    """Handle SimReady OpenUSD REST API requests (/api/simready/catalog, /api/simready/usd/<id>, /api/simready/collide)."""
    clean_path = path.split("?")[0].rstrip("/")
    host = sim_host or _get_or_create_sim_host()
    w1 = host.sim.wave1

    if method.upper() == "GET" and clean_path == "/api/campaign/state":
        return 200, {"ok": True, "campaign": w1.cable_campaign.to_dict(host.sim.vehicle.s.pos)}

    if method.upper() == "POST" and clean_path == "/api/campaign/action":
        if isinstance(body, (bytes, bytearray)):
            raw_text = body.decode("utf-8", errors="replace").strip()
            payload = json.loads(raw_text) if raw_text else {}
        elif isinstance(body, str):
            raw_text = body.strip()
            payload = json.loads(raw_text) if raw_text else {}
        elif isinstance(body, dict):
            payload = dict(body)
        else:
            payload = {}
        sub_action = str(payload.get("sub_action") or payload.get("action") or "status")
        return 200, w1.handle_campaign_action(sub_action, payload)

    if method.upper() == "GET" and clean_path == "/api/simready/catalog":
        cat = load_simready_catalog_dict()
        return 200, {"ok": True, **cat}

    if method.upper() == "GET" and clean_path.startswith("/api/simready/usd/"):
        asset_id = clean_path.split("/api/simready/usd/", 1)[1].strip()
        data = get_simready_usda_payload(asset_id)
        if data is None:
            return 404, {"ok": False, "error": f"Unknown SimReady OpenUSD asset: {asset_id}"}
        return 200, {"ok": True, **data}

    if method.upper() == "POST" and clean_path in ("/api/simready/collide", "/api/simready/teleport"):
        if isinstance(body, (bytes, bytearray)):
            raw_text = body.decode("utf-8", errors="replace").strip()
            payload = json.loads(raw_text) if raw_text else {}
        elif isinstance(body, str):
            raw_text = body.strip()
            payload = json.loads(raw_text) if raw_text else {}
        elif isinstance(body, dict):
            payload = dict(body)
        else:
            payload = {}
        asset_id = str(payload.get("asset_id") or "SR-IND-01").strip()
        if clean_path.endswith("/collide"):
            res = w1.collide_simready_asset(asset_id, payload.get("impact_speed_mps"))
        else:
            res = w1.teleport_to_simready_asset(asset_id)
        return (200 if res.get("ok") else 404), res

    return 404, {"ok": False, "error": f"Unknown SimReady endpoint: {method} {clean_path}"}


class _Static(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".usda": "text/plain; charset=utf-8",
        ".usd": "application/octet-stream",
        ".wasm": "application/wasm",
    }
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(VIEWER_DIR), **k)

    def _send_json(self, status_code: int, payload: dict) -> None:
        raw = dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "/api/b2b/roster":
            sim_host = getattr(self.server, "sim_host", None) or _get_or_create_sim_host()
            code, payload = handle_b2b_api_request("GET", clean_path, None, sim_host=sim_host)
            self._send_json(code, payload)
            return
        if clean_path in ("/api/simready/catalog", "/api/campaign/state") or clean_path.startswith("/api/simready/usd/"):
            sim_host = getattr(self.server, "sim_host", None) or _get_or_create_sim_host()
            code, payload = handle_simready_api_request("GET", clean_path, None, sim_host=sim_host)
            self._send_json(code, payload)
            return
        super().do_GET()

    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "/api/b2b/record_run":
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            sim_host = getattr(self.server, "sim_host", None) or _get_or_create_sim_host()
            try:
                code, payload = handle_b2b_api_request("POST", clean_path, raw_body, sim_host=sim_host)
            except Exception as exc:
                code, payload = 400, {"ok": False, "error": str(exc)}
            self._send_json(code, payload)
            return
        if clean_path in ("/api/simready/collide", "/api/simready/teleport", "/api/campaign/action"):
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            sim_host = getattr(self.server, "sim_host", None) or _get_or_create_sim_host()
            try:
                code, payload = handle_simready_api_request("POST", clean_path, raw_body, sim_host=sim_host)
            except Exception as exc:
                code, payload = 400, {"ok": False, "error": str(exc)}
            self._send_json(code, payload)
            return
        self._send_json(404, {"ok": False, "error": f"Unknown POST endpoint: {clean_path}"})

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


def start_static(port: int, host: str, sim_host: SimHost | None = None) -> socketserver.ThreadingTCPServer:
    global _ACTIVE_SIM_HOST
    if sim_host is not None:
        _ACTIVE_SIM_HOST = sim_host
    socketserver.TCPServer.allow_reuse_address = True
    # A module graph opens several connections per browser. Windows rejects
    # bursts at the default five-connection listen backlog.
    socketserver.ThreadingTCPServer.request_queue_size = 64
    httpd = socketserver.ThreadingTCPServer((host, port), _Static)
    httpd.sim_host = sim_host or _ACTIVE_SIM_HOST
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


async def main_async(args):
    import websockets
    if getattr(args, "release_mode", False):
        os.environ["ROV01SIM_RELEASE_MODE"] = "1"
    sim = Simulator(args.scenario, args.seed, release_mode=getattr(args, "release_mode", False))
    host = SimHost(sim, usb_rc=args.usb_rc)
    rpc = await asyncio.start_server(host.rpc_client, "127.0.0.1", args.rpc_port)
    ws = await websockets.serve(host.viewer_handler, args.host, args.ws_port, max_size=2 ** 16)
    if not args.no_http:
        start_static(args.http_port, args.host, sim_host=host)
    print(f"[rov01sim] scenario={sim.scenario.name}  SDK rpc tcp://127.0.0.1:{args.rpc_port}  "
          f"viewer ws://{args.host}:{args.ws_port}  http://{args.host}:{args.http_port}/", flush=True)
    async with rpc:
        tasks = [host.physics_loop(), rpc.serve_forever(), ws.wait_closed()]
        if args.usb_rc:
            from .usb_rc import UsbRcReader
            reader = UsbRcReader(adb=args.adb, serial=args.usb_rc_serial)
            tasks.append(reader.run(host.controller_sample, host.controller_status))
        await asyncio.gather(*tasks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="ROV-01 simulator host")
    ap.add_argument("--scenario", default="open_water")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--rpc-port", type=int, default=int(os.environ.get("ROV01SIM_RPC_PORT", 9760)))
    ap.add_argument("--ws-port", type=int, default=8765)
    ap.add_argument("--http-port", type=int, default=8080)
    ap.add_argument("--no-http", action="store_true")
    ap.add_argument("--release-mode", dest="release_mode", action="store_true", help="Disable legacy vendor SDK adapters and legacy RC aliases")
    ap.add_argument("--usb-rc", dest="usb_rc", action="store_true", help="Read USB controller through authorized ADB")
    ap.add_argument("--adb", default=None, help="Path to Android Platform Tools adb")
    ap.add_argument("--usb-rc-serial", dest="usb_rc_serial", default=None, help="Select one USB controller when several are connected")
    args = ap.parse_args(argv)
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
