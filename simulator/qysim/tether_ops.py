"""Cable operations: tender radio calls, twist counting, snag procedure scoring and payout discipline.

Reads the tether's state without changing its solver. Every threshold, stiffness and score weight here is a
provisional training assumption (see PROTOCOL.md, `state.tether_ops`), not a measured vehicle or cable value.
"""
import math

import numpy as np

TWIST_WARN_TURNS = 2.0         # turns before the tender warns and twist torque starts
TWIST_STIFFNESS_NM = 0.4       # restoring yaw moment per turn beyond the threshold
TWIST_TORQUE_CAP_NM = 8.0
TENSION_WARN_N = 250.0
EXCESS_SLACK_M = 10.0
LENGTH_CALL_M = 5
EVENT_LIMIT = 20


def cable_view(tether):
    """The fields this module reads, taken straight from the solver without copying or rounding."""
    return {"nodes": tether.x, "length": tether.length, "tension_max": tether.tension_max,
            "broken": tether.broken, "snagged_on": tether.snag_names, "wraps": tether.wraps}


def twist_torque(turns):
    """Body yaw moment opposing net rotation, zero until the warning threshold is passed."""
    excess = turns - max(-TWIST_WARN_TURNS, min(TWIST_WARN_TURNS, turns))
    return -max(-TWIST_TORQUE_CAP_NM, min(TWIST_TORQUE_CAP_NM, excess * TWIST_STIFFNESS_NM))


class TetherOperations:
    def __init__(self, world=None):
        self.world = world
        self.broken = False
        self.turns = 0.0
        self.previous_yaw = None
        self.bucket = None
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
        self.events = self.events[-EVENT_LIMIT:]

    def _count_turns(self, yaw):
        if self.previous_yaw is not None:
            delta = yaw - self.previous_yaw
            self.turns += math.atan2(math.sin(delta), math.cos(delta)) / math.tau
        self.previous_yaw = yaw
        twist_warning = abs(self.turns) > TWIST_WARN_TURNS
        if twist_warning and not self.twist_warning:
            self.emit('twist')
        self.twist_warning = twist_warning

    def _snag_target(self, name, nodes, position):
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

    def _finish_episode(self, episode, broken):
        score = 30 * episode['returned'] + 30 * episode['correct']
        score += max(0, 30 - episode['peak'] / 25)
        score += max(0, 10 - episode['elapsed'] / 30)
        score -= min(40, episode['tightening'] * 5)
        self.result = dict(score=0 if broken else round(max(0, score)), peak_n=round(float(episode['peak']), 1),
                           elapsed=round(episode['elapsed'], 1), returned=episode['returned'], correct=episode['correct'])
        self.episode = None
        self.emit('released')

    def _track_episode(self, dt, cable, position, yaw, tension):
        episode = self.episode
        episode['elapsed'] += dt
        episode['peak'] = max(episode['peak'], tension)
        episode['tightening'] += dt * max(0, tension / TENSION_WARN_N - 1)
        delta = episode['target'] - position
        facing = np.dot(delta[:2], [math.cos(yaw), math.sin(yaw)])
        if np.linalg.norm(delta) < 2 and facing > 0:
            episode['returned'] = True
        remaining = cable['wraps'].get(episode['name'], 0)
        if episode['returned'] and abs(remaining) < abs(episode['initial']) - 0.15:
            episode['correct'] = bool(remaining * episode['initial'] >= 0)
        if abs(remaining) < 0.25 or cable['broken']:
            self._finish_episode(episode, cable['broken'])

    def step(self, dt, cable, position, yaw):
        """Advance one physics step; returns the body yaw moment the twisted cable applies."""
        self.clock += dt
        self.broken = cable['broken']
        position = np.asarray(position, float)
        self._count_turns(yaw)
        bucket = int(cable['length'] // LENGTH_CALL_M)
        if bucket != self.bucket:
            self.emit('length', metres=bucket * LENGTH_CALL_M)
            self.bucket = bucket
        tension = cable['tension_max']
        warn = tension > TENSION_WARN_N
        if warn and not self.warning:
            self.emit('tension')
        self.warning = warn
        nodes = np.asarray(cable['nodes'], float)
        span = np.linalg.norm(nodes[-1] - nodes[0])
        if cable['length'] - span > EXCESS_SLACK_M:
            self.slack_seconds += dt
        if warn:
            self.taut_seconds += dt
        near_structure = bool(cable.get('snagged_on'))
        if near_structure and not self.near_structure:
            self.emit('structure')
        self.near_structure = near_structure
        wraps = cable.get('wraps') or {}
        if self.episode is None and wraps and not self.broken:
            name = max(wraps, key=lambda key: abs(wraps[key]))
            self.episode = dict(name=name, initial=wraps[name], peak=0.0, elapsed=0.0, returned=False,
                                correct=False, tightening=0.0, target=self._snag_target(name, nodes, position))
            self.emit('snag')
        if self.episode is not None:
            self._track_episode(dt, cable, position, yaw, tension)
        return 0.0 if self.broken else twist_torque(self.turns)

    def state(self):
        episode = self.episode
        snag = None
        if episode is not None:
            snag = dict(name=episode['name'], returned=episode['returned'],
                        tightening=round(episode['tightening'], 2))
        return dict(turns=round(self.turns, 2), torque_nm=0.0 if self.broken else round(twist_torque(self.turns), 2),
                    events=self.events[-EVENT_LIMIT:], result=self.result, snag=snag,
                    discipline_score=round(max(0, 100 - self.slack_seconds - 2 * self.taut_seconds)),
                    slack_seconds=round(self.slack_seconds, 1), taut_seconds=round(self.taut_seconds, 1))
