"""Cable operations observer: tender radio calls, twist warning, untangle/snag procedure scoring, payout discipline.

Read-only: it reads the tether solver's own fields (``Tether`` in tether.py) after each step and never applies a
force. The twist moment is the solver's physical GJ term (``Tether.twist_torque_nm``, from ``Tether.turns``); the
two-turn twist call here is a console / tender warning only, as on real tether-turn counters. Wraps come from the
solver's winding count (``tether_contact.wrap_counts``, reported from a quarter turn) and seabed or structure snags
from its snag tracker (``Tether.snags.hooks``); nothing is recounted here.
Every threshold and score weight is a provisional training assumption (PROTOCOL.md, ``state.tether_ops``).
Peak load and tightening are measured against the termination's rated working load, as ``warn`` is.
"""
import math

import numpy as np

TWIST_WARN_TURNS = 2.0         # net turns before the tender calls for unwinding (warning only, no force)
EXCESS_SLACK_M = 10.0          # paid-out length beyond the direct span that counts as poor discipline
LENGTH_CALL_M = 5
EVENT_LIMIT = 20
UNWOUND_TURNS = 0.25           # wrap counts below this are no longer reported by the solver
PROGRESS_TURNS = 0.15          # reduction of the winding that judges the unwinding direction


def _load_ratio(tether):
    """Vehicle-end pull as a fraction of the termination's rated working load (the binding limit near the ROV)."""
    return tether.tension_rov / max(tether.p.gland_warn_n, 1e-9)


class TetherOperations:
    def __init__(self, world=None):
        self.world = world
        self.broken = False
        self.turns = 0.0
        self.torque_nm = 0.0
        self.bucket = None
        self.reel_mode = None
        self.reel_stalled = False
        self.events = []
        self.event_id = 0
        self.episode = None
        self.result = None
        self.slack_seconds = 0.0
        self.taut_seconds = 0.0
        self.clock = 0.0
        self.warning = False
        self.twist_warning = False
        self.near_structure = False

    def emit(self, code, **data):
        self.event_id += 1
        self.events.append(dict(id=self.event_id, code=code, **data))
        if len(self.events) > EVENT_LIMIT:
            del self.events[0]

    # ── episodes ──────────────────────────────────────────────────────────
    def _wrap_target(self, name, nodes, position):
        """The cable point at the structure, frozen as the place the pilot must return to."""
        candidates = nodes[1:-1]
        target = candidates[np.argmin(np.linalg.norm(candidates - position, axis=1))].copy()
        if self.world is None:
            return target
        obstacle = next((item for item in self.world.obstacles if item.name == name), None)
        if obstacle is None:
            return target
        distances = np.array([obstacle.sdf(point)[0] for point in candidates])
        near = np.flatnonzero(distances < 0.5)
        return candidates[near[-1]].copy() if len(near) else target

    def _start_episode(self, tether, position):
        hooks = tether.snags.hooks
        if hooks:
            hook = hooks[0]
            name, kind, initial, target = hook.name, 'snag', 0.0, np.array(hook.target, float)
        else:
            wraps = tether.wraps
            name = max(wraps, key=lambda key: abs(wraps[key]))
            kind, initial = 'wrap', wraps[name]
            target = self._wrap_target(name, tether.x, position)
        self.episode = dict(name=name, kind=kind, initial=initial, peak=0.0, peak_n=0.0, elapsed=0.0,
                            returned=False, correct=False, tightening=0.0, target=target)
        self.emit('snag')

    def _finish_episode(self, episode, broken):
        score = 30 * episode['returned'] + 30 * episode['correct']
        score += max(0, 30 * (1 - episode['peak']))
        score += max(0, 10 - episode['elapsed'] / 30)
        score -= min(40, episode['tightening'] * 5)
        self.result = dict(score=0 if broken else round(max(0, score)),
                           peak_n=round(float(episode['peak_n']), 1), elapsed=round(episode['elapsed'], 1),
                           returned=episode['returned'], correct=episode['correct'], kind=episode['kind'])
        self.episode = None
        self.emit('released')

    def _track_episode(self, dt, tether, position, yaw):
        episode = self.episode
        ratio = _load_ratio(tether)
        episode['elapsed'] += dt
        if ratio > episode['peak']:
            episode['peak'] = ratio
            episode['peak_n'] = tether.tension_rov
        episode['tightening'] += dt * max(0.0, ratio - 1.0)
        dx = episode['target'][0] - position[0]
        dy = episode['target'][1] - position[1]
        dz = episode['target'][2] - position[2]
        facing = dx * math.cos(yaw) + dy * math.sin(yaw)
        if dx * dx + dy * dy + dz * dz < 4.0 and facing > 0:
            episode['returned'] = True
        if episode['kind'] == 'snag':
            held = any(hook.name == episode['name'] for hook in tether.snags.hooks)
            if episode['returned'] and not held:
                episode['correct'] = True             # the tracker only lets go once the pilot backs out
            done = not held
        else:
            remaining = tether.wraps.get(episode['name'], 0.0)
            if episode['returned'] and abs(remaining) < abs(episode['initial']) - PROGRESS_TURNS:
                episode['correct'] = bool(remaining * episode['initial'] >= 0)
            done = abs(remaining) < UNWOUND_TURNS
        if done or tether.broken:
            self._finish_episode(episode, tether.broken)

    # ── per step ──────────────────────────────────────────────────────────
    def _radio(self, tether):
        bucket = int(tether.length // LENGTH_CALL_M)
        if bucket != self.bucket:
            self.emit('length', metres=bucket * LENGTH_CALL_M)
            self.bucket = bucket
        reel = tether.reel
        if reel.mode != self.reel_mode:
            if self.reel_mode is not None:
                self.emit('reel', mode=reel.mode)
            self.reel_mode = reel.mode
        if reel.stalled and not self.reel_stalled:
            self.emit('stall')
        self.reel_stalled = reel.stalled
        twist_warning = abs(self.turns) > TWIST_WARN_TURNS
        if twist_warning and not self.twist_warning:
            self.emit('twist')
        self.twist_warning = twist_warning
        near_structure = bool(tether.snag_names)
        if near_structure and not self.near_structure:
            self.emit('structure')
        self.near_structure = near_structure

    def step(self, dt, tether, position, yaw):
        """Observe one physics step of ``tether`` (after ``Tether.step``). Applies no force."""
        self.clock += dt
        self.broken = tether.broken
        self.turns = tether.turns
        self.torque_nm = 0.0 if self.broken else tether.twist_torque_nm
        self._radio(tether)
        warn = tether.over_working_load
        if warn and not self.warning:
            self.emit('tension')
        self.warning = warn
        nodes = tether.x
        if tether.length - math.dist(nodes[-1], nodes[0]) > EXCESS_SLACK_M:
            self.slack_seconds += dt
        if warn:
            self.taut_seconds += dt
        if self.episode is None and not self.broken and (tether.snags.hooks or tether.wraps):
            self._start_episode(tether, position)
        if self.episode is not None:
            self._track_episode(dt, tether, position, yaw)

    def state(self):
        episode = self.episode
        snag = None
        if episode is not None:
            snag = dict(name=episode['name'], kind=episode['kind'], returned=episode['returned'],
                        tightening=round(episode['tightening'], 2))
        return dict(turns=round(self.turns, 2), torque_nm=round(self.torque_nm, 3),
                    twist_warning=self.twist_warning, events=list(self.events), result=self.result, snag=snag,
                    discipline_score=round(max(0, 100 - self.slack_seconds - 2 * self.taut_seconds)),
                    slack_seconds=round(self.slack_seconds, 1), taut_seconds=round(self.taut_seconds, 1))
