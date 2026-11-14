"""Topside tether reel: drum inertia, brake, tender commands and the optional constant-tension controller.

Real small-ROV practice (research_notes/臍帶纜物理與收放文獻/shipboard_handling.md §1, §3, §5):
    * payout is passive: the vehicle drags tether off a disengaged or braked drum (Deep Trekker
      ``reelForward`` "not forcibly spooled out"); a tender may also hand-feed tether
    * haul-in is powered at roughly 0.4-0.6 m/s (QYSEA electric spool, reseller figure, provisional)
    * a human tender pays out, holds and hauls in on the pilot's call
Commands are rates, never instant length jumps. New length enters at the spool end only.

``auto`` is the constant-tension controller (setpoint, deadband, payout rate proportional to excess
tension through a slip clutch, slow haul-in when slack with the motor pull limited to the setpoint,
stall detection). It is a synthesis from shipboard_handling.md §3 "Inferences", not a vendor algorithm,
and it exceeds what a small hand-tended reel does, so the viewer registers it as the fidelity item
``autoPayout`` (off in the ``real`` preset).

The drum is modelled as an equivalent line inertia J (drum plus the tether still wound on it) that
the cable solver couples implicitly to the spool segment; brake and bearing drag are static and
kinetic friction; the tender or motor is a velocity servo with force limits.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ._cable_accel import (REEL_DRIVE, REEL_INV_MASS, REEL_KINETIC, REEL_ROOM_IN, REEL_ROOM_OUT,
                           REEL_SIZE, REEL_SPEED, REEL_STATIC, REEL_TENSION, REEL_VISCOUS)

MODES = ("free", "hold", "pay_out", "haul_in", "auto")
MIN_LENGTH_M = 2.0
# Load-cell low-pass for the constant-tension controller; the stiff cable makes the raw spool tension
# ring at the segment frequency, and a controller acting on it limit-cycles.
TENSION_FILTER_S = 0.5


@dataclass
class ReelParams:
    drum_mass_kg: float          # equivalent line inertia of the empty drum
    free_drag_n: float           # bearing and slip-ring drag of a freely turning drum
    brake_hold_n: float          # brake (or locked crank) holding force before the drum slips
    feed_rate: float             # tender hand-feeding rate, m/s
    feed_force_n: float          # tender pull while feeding
    haul_rate: float             # powered haul-in, m/s
    pull_cap_n: float            # motor line-pull cap, below the termination strength
    servo_tau: float             # servo time constant, s
    auto_setpoint_n: float       # constant-tension setpoint
    auto_deadband_n: float
    auto_gain: float             # m/s per N above setpoint + deadband
    auto_slack_rate: float       # slow haul-in when slack, m/s
    stall_speed: float           # m/s below which a commanded haul counts as stalled
    stall_time: float            # s


class Reel:
    """Topside reel state. ``mode`` is one of MODES; ``target`` is an optional length goal."""

    def __init__(self, params: ReelParams, mass_per_m: float, max_length: float, mode: str = "free"):
        self.p = params
        self.mass_per_m = float(mass_per_m)
        self.max_length = float(max_length)
        self.mode = mode
        self.target: float | None = None
        self._resume_mode = mode
        self.state = np.zeros(REEL_SIZE)
        self.stalled = False
        self._stall_clock = 0.0
        self.events: list[dict] = []
        self.filtered_tension = 0.0
        self._set_speed = None

    # ── commands ──────────────────────────────────────────────────────────
    def command(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown reel command: {mode}")
        self.mode = mode
        self.target = None
        self.stalled = False
        self._stall_clock = 0.0

    def request_length(self, length: float, current: float) -> None:
        """Legacy ``payout`` metres: move toward a length at the tender/motor rate, then resume the mode."""
        if self.target is None:
            self._resume_mode = self.mode
        self.target = float(np.clip(length, MIN_LENGTH_M, self.max_length))
        if abs(self.target - current) < 1e-6:
            self.target = None

    @property
    def speed(self) -> float:
        return float(self.state[REEL_SPEED])

    @property
    def tension(self) -> float:
        return float(self.state[REEL_TENSION])

    # ── per-tick set-up ───────────────────────────────────────────────────
    def _setpoint(self, current_length: float) -> tuple:
        """(speed setpoint or None, min servo force, max servo force, static, kinetic, viscous).

        A turning drum (tender feeding, motor hauling, passive payout) only feels bearing drag; the
        brake holds whenever the drum is meant to stand still. ``auto`` pays out through a slip
        clutch set at setpoint + deadband with a viscous term, so the payout rate is proportional
        to the excess tension (gain m/s per N); slack is taken in by a motor whose line pull is
        limited to the setpoint (plus the drum's own drag). A clutch reacts at once, which a filtered
        load-cell loop on this stiff cable cannot (it limit-cycles), and it is how TMS drums limit
        over-pull (SH §2, §3)."""
        p = self.p
        drag = p.free_drag_n
        feed = (p.feed_rate, 0.0, p.feed_force_n, drag, 0.8 * drag, 0.0)
        haul = (-p.haul_rate, -p.pull_cap_n, 0.0, drag, 0.8 * drag, 0.0)
        hold = (None, 0.0, 0.0, p.brake_hold_n, 0.8 * p.brake_hold_n, 0.0)
        if self.target is not None:
            if self.target > current_length + 1e-3:
                return feed
            if self.target < current_length - 1e-3:
                return haul
            self.target = None
            self.mode = self._resume_mode
        mode = self.mode
        if mode == "hold":
            return hold
        if mode == "pay_out":
            return feed
        if mode == "haul_in":
            return haul
        if mode == "auto":
            clutch = p.auto_setpoint_n + p.auto_deadband_n
            if self.filtered_tension < p.auto_setpoint_n - p.auto_deadband_n and self.speed <= 0.0:
                return -p.auto_slack_rate, -(p.auto_setpoint_n + drag), 0.0, drag, 0.8 * drag, 0.0
            return None, 0.0, 0.0, clutch, clutch, 1.0 / p.auto_gain
        return None, 0.0, 0.0, drag, 0.8 * drag, 0.0

    def prepare(self, current_length: float) -> np.ndarray:
        """Fill the solver's reel vector for this tick and return it (updated in place by the solver)."""
        p = self.p
        wound = max(self.max_length - current_length, 0.0)
        inertia = p.drum_mass_kg + self.mass_per_m * wound
        set_speed, low, high, static, kinetic, viscous = self._setpoint(current_length)
        drive = 0.0
        if set_speed is not None:
            # velocity servo plus feed-forward of the drum's own drag
            drive = inertia * (set_speed - self.speed) / p.servo_tau
            drive += np.sign(set_speed) * kinetic
            drive = float(np.clip(drive, low, high))
        state = self.state
        state[REEL_INV_MASS] = 1.0 / inertia
        state[REEL_DRIVE] = drive
        state[REEL_STATIC] = static
        state[REEL_KINETIC] = kinetic
        state[REEL_VISCOUS] = viscous
        lower_limit = MIN_LENGTH_M if self.target is None else max(MIN_LENGTH_M, min(self.target, current_length))
        upper_limit = self.max_length if self.target is None else max(self.target, current_length)
        state[REEL_ROOM_OUT] = upper_limit - current_length
        state[REEL_ROOM_IN] = current_length - lower_limit
        self._set_speed = set_speed
        return state

    def finish(self, dt: float, t_now: float) -> None:
        """Load-cell filter for the controller and stall detection after the solver ran."""
        blend = min(1.0, dt / TENSION_FILTER_S)
        self.filtered_tension += (self.tension - self.filtered_tension) * blend
        hauling = self._set_speed is not None and self._set_speed < 0.0
        if hauling and self.speed > -self.p.stall_speed:
            self._stall_clock += dt
        else:
            self._stall_clock = 0.0
            self.stalled = False
        if self._stall_clock >= self.p.stall_time and not self.stalled:
            self.stalled = True
            self.events.append({"t": round(t_now, 2), "type": "reel_stall",
                                "tension_n": round(self.tension, 1)})

    def state_dict(self) -> dict:
        return {"mode": self.mode, "speed": round(self.speed, 3), "stalled": self.stalled,
                "target_length": None if self.target is None else round(self.target, 1),
                "tension_n": round(self.tension, 1)}
