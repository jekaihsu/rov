"""Simulated vehicle communications link (tether modem between topside and ROV).

This is a *simulated* fault model, separate from the simulator's own browser-server
network watchdog in ``room.py`` (0.6 s input timeout), which it never replaces.
The link has three states:

* ``healthy``  - no effect. This is the default; nothing degrades on its own.
* ``degraded`` - video presentation lag grows towards a cap, video freezes in periodic
  episodes, compression artefacts rise and telemetry updates more slowly. Commands
  still reach the vehicle (field reports: video frozen while helm and lights respond).
* ``lost``     - no commands reach the vehicle: it keeps the last command it received.
  After ``failsafe_delay_s`` the vehicle applies its failsafe action. Video freezes on the
  last frame and telemetry stops. After the link is restored the modem takes
  ``reconnect_s`` to re-establish, and the vehicle stays locked until the pilot re-arms.

Only scenarios (``Scenario.link``) and instructor injections change the link.
Every number below is provisional; the sources are in
``research_notes/感測器_揚沙_通訊/comms_and_power.md``. X1 loss-of-comms behaviour,
timeouts and reconnect time are not published.
"""
from __future__ import annotations

import math

from .rc import RCState

# Provisional parameters with their sources. None of them is an X1 measurement.
LINK_PARAMETERS = {
    "failsafe_action": {
        "value": "disarm",
        "source": "Open-source sub autopilot failsafe option 'disarm' (comms_and_power.md); X1 unpublished"},
    "failsafe_delay_s": {
        "value": 3.0,
        "source": "Open-source sub autopilot pilot-input timeout upper bound 3.0 s (GCS 5 s); X1 unpublished"},
    "reconnect_s": {
        "value": 30.0,
        "source": "Earlier same-family vehicle vendor FAQ: ~30 s reconnect after a cable unplug; X1 unmeasured"},
    "max_video_lag_s": {
        "value": 5.0,
        "source": "Field report: video lag up to ~4-5 s with controls responsive (topside modem fault)"},
    "freeze_period_s": {
        "value": 20.0,
        "source": "Field report snippet: video freezes ~5 s roughly every 20 s"},
    "freeze_s": {
        "value": 5.0,
        "source": "Field report snippet: video freezes ~5 s roughly every 20 s"},
    "healthy_telemetry_hz": {
        "value": 30.0,
        "source": "Simulator state publication rate; not a vehicle telemetry measurement"},
    "degraded_telemetry_hz": {
        "value": 4.0,
        "source": "Assumption: telemetry survives at a reduced rate when video capacity collapses"},
}
FAILSAFE_ACTIONS = ("disarm", "depth_hold", "surface")
STATES = ("healthy", "degraded", "lost")
# Below this severity the queue never fills enough to freeze whole seconds of video (assumption).
FREEZE_SEVERITY = 0.3
# Surface failsafe: ascend through the existing depth-hold loop, then hold at the surface.
SURFACE_DEPTH_M = 0.3


def default_config() -> dict:
    return {key: item["value"] for key, item in LINK_PARAMETERS.items()}


class CommsLink:
    """Per-vehicle link state machine. Driven by simulation time only (deterministic)."""

    def __init__(self, config: dict | None = None):
        self.config = default_config()
        initial = dict(config or {})
        state = initial.pop("state", "healthy")
        severity = float(initial.pop("severity", 0.5))
        self.configure(initial)
        self.severity = 0.0
        self.fixed_lag_s = 0.0
        self.forced_freeze = False
        self.lag_s = 0.0
        self.degraded_at = None
        self.phase = "connected"        # connected | lost | reconnecting
        self.cause = None               # comms | power
        self.lost_at = None
        self.reconnect_at = None
        self.frozen_rc = None
        self.failsafe = None            # applied action, latched until re-arm
        self.failsafe_target = None
        self.rearm_required = False
        self.rearm_seen_lock = False
        self.immediate = False
        self.clock = 0.0
        if state == "degraded":
            self.degrade(severity)
        elif state == "lost":
            self.lose()

    # ── configuration and commands ───────────────────────────────────────
    def configure(self, values: dict) -> None:
        for key, value in values.items():
            if key not in self.config:
                raise ValueError(f"unknown link parameter: {key}")
            if key == "failsafe_action":
                if value not in FAILSAFE_ACTIONS:
                    raise ValueError("failsafe_action must be disarm, depth_hold or surface")
                self.config[key] = value
                continue
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"{key} must be a finite non-negative number")
            self.config[key] = number

    def degrade(self, severity: float) -> None:
        severity = max(0.0, min(1.0, float(severity)))
        if self.degraded_at is None:
            self.degraded_at = self.clock
        self.severity = severity

    def clear_degrade(self) -> None:
        self.severity = 0.0
        self.degraded_at = None
        self.lag_s = 0.0                # the buffer drops and the picture jumps to live

    def lose(self, cause: str = "comms", immediate: bool = False, rc: RCState | None = None) -> None:
        """Idempotent: calling it every tick while the loss lasts keeps the original timers.
        ``rc`` is the command the vehicle last received; it keeps executing it until the failsafe."""
        if self.phase == "lost":
            return
        if self.phase == "connected" and self.failsafe is None:
            self.frozen_rc = None if rc is None else RCState(**rc.as_dict())
        self.phase = "lost"
        self.cause = cause
        self.lost_at = self.clock
        self.reconnect_at = None
        self.immediate = immediate

    def restore(self) -> None:
        if self.phase != "lost":
            return
        self.phase = "reconnecting"
        self.reconnect_at = self.clock + self.config["reconnect_s"]

    # ── derived values ───────────────────────────────────────────────────
    @property
    def connected(self) -> bool:
        return self.phase == "connected"

    @property
    def state_name(self) -> str:
        if not self.connected:
            return "lost"
        if self.severity > 0 or self.fixed_lag_s > 0 or self.forced_freeze:
            return "degraded"
        return "healthy"

    def _freeze_episode(self) -> bool:
        if self.severity < FREEZE_SEVERITY or self.degraded_at is None:
            return False
        period = self.config["freeze_period_s"]
        if period <= 0:
            return False
        length = min(period, self.config["freeze_s"] * self.severity)
        phase = (self.clock - self.degraded_at) % period
        return phase >= period - length

    @property
    def video_frozen(self) -> bool:
        return not self.connected or self.forced_freeze or self._freeze_episode()

    @property
    def video_lag_s(self) -> float:
        return min(self.config["max_video_lag_s"], self.lag_s + self.fixed_lag_s)

    @property
    def telemetry_hz(self) -> float | None:
        if not self.connected:
            return 0.0
        if self.severity <= 0:
            return None
        healthy = self.config["healthy_telemetry_hz"]
        degraded = self.config["degraded_telemetry_hz"]
        return round(healthy + (degraded - healthy) * self.severity, 2)

    # ── per-step behaviour ───────────────────────────────────────────────
    def step(self, sim, dt: float) -> None:
        self.clock += dt
        self._grow_lag(dt)
        if self.phase == "lost":
            self._lost_step(sim)
        elif self.phase == "reconnecting" and self.clock >= self.reconnect_at:
            self._reconnected(sim)
        elif self.phase == "connected" and self.rearm_required:
            self._watch_rearm(sim)

    def _grow_lag(self, dt: float) -> None:
        if self.severity <= 0:
            self.lag_s = 0.0
            return
        # Capacity C against stream bitrate B: the queue grows at (B - C) / C seconds per second.
        capacity = 1.0 - 0.8 * self.severity
        growth = (1.0 - capacity) / capacity
        cap = self.config["max_video_lag_s"] * self.severity
        self.lag_s = min(cap, self.lag_s + growth * dt)

    def _lost_step(self, sim) -> None:
        if self.frozen_rc is None and self.failsafe is None:
            # The vehicle keeps executing the last command it received.
            self.frozen_rc = RCState(**sim.rc.as_dict())
        elapsed = self.clock - self.lost_at
        if self.failsafe is None and (self.immediate or elapsed >= self.config["failsafe_delay_s"]):
            action = "disarm" if self.cause == "power" else self.config["failsafe_action"]
            self._apply_failsafe(sim, action)

    def _apply_failsafe(self, sim, action: str) -> None:
        self.failsafe = action
        self.frozen_rc = None
        self.rearm_required = True
        self.rearm_seen_lock = False
        self.failsafe_target = float(sim.vehicle.s.pos[2])
        lock_vehicle(sim)
        names = {"disarm": "解除武裝", "depth_hold": "定深", "surface": "上浮"}
        sim._log("link", f"通訊中斷保護：{names[action]}")

    def _reconnected(self, sim) -> None:
        self.phase = "connected"
        self.cause = None
        self.reconnect_at = None
        self.lost_at = None
        self.frozen_rc = None
        if self.failsafe is not None:
            # Pilot input sent while the link was down never reached the vehicle: latch again.
            lock_vehicle(sim)
            self.rearm_seen_lock = False
        sim._log("link", "通訊恢復" + ("，需重新解鎖" if self.rearm_required else ""))

    def _watch_rearm(self, sim) -> None:
        rc = sim.rc
        if rc.rc_lock == 1:
            self.rearm_seen_lock = True
        elif self.rearm_seen_lock:
            self.rearm_required = False
            self.failsafe = None
            self.failsafe_target = None
            sim._log("link", "已重新解鎖")

    def command_rc(self, live: RCState) -> RCState:
        """RC as received by the vehicle. While lost it is the last command before the loss.
        The simulator's own network watchdog still wins: a live lock always applies."""
        if not self.connected and self.failsafe is not None:
            # Packets that arrive while the link is down never reach the vehicle.
            locked = RCState(**live.as_dict())
            locked.centre_sticks()
            locked.rc_lock = 1
            locked.photo = 0
            locked.record = 0
            return locked
        if self.frozen_rc is None:
            return live
        if live.rc_lock == 1:
            return live
        return self.frozen_rc

    def failsafe_command(self, sim):
        """Autonomous command while a depth-hold or surface failsafe is latched, else None."""
        if self.failsafe not in ("depth_hold", "surface"):
            return None
        if sim.tether.broken:
            return None
        if self.failsafe == "surface":
            target = max(0.0, (self.failsafe_target or 0.0))
            if sim.depth > SURFACE_DEPTH_M:
                return {"heave": 1.0, "depth": None}
            return {"heave": 0.0, "depth": min(target, SURFACE_DEPTH_M)}
        return {"heave": 0.0, "depth": self.failsafe_target}

    def state(self) -> dict:
        reconnect_in = None
        if self.phase == "reconnecting":
            reconnect_in = round(max(0.0, self.reconnect_at - self.clock), 1)
        failsafe_in = None
        if self.phase == "lost" and self.failsafe is None and not self.immediate:
            failsafe_in = round(max(0.0, self.lost_at + self.config["failsafe_delay_s"] - self.clock), 1)
        quality = 0.0 if not self.connected else round(1.0 - self.severity, 2)
        return {
            "state": self.state_name,
            "phase": self.phase,
            "cause": self.cause,
            "quality": quality,
            "video_lag_s": round(self.video_lag_s, 2),
            "video_frozen": self.video_frozen,
            "artefact": round(self.severity if self.connected else 0.0, 2),
            "telemetry_hz": self.telemetry_hz,
            "failsafe_action": self.config["failsafe_action"],
            "failsafe": self.failsafe,
            "failsafe_in": failsafe_in,
            "reconnect_in": reconnect_in,
            "rearm_required": self.rearm_required,
        }


def lock_vehicle(sim) -> None:
    """Latch the same disarm used by the network failsafe; the pilot must lock then unlock."""
    from .room import Room
    Room.lock(sim)
