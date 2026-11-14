"""Read-only cable observation and procedural training scores; thresholds are provisional."""
import math
import numpy as np


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
        self.events = self.events[-20:]

    def step(self, dt, cable, position, yaw):
        self.clock += dt
        self.broken = cable['broken']
        if self.previous_yaw is not None:
            self.turns += math.atan2(math.sin(yaw - self.previous_yaw),
                                     math.cos(yaw - self.previous_yaw)) / math.tau
        self.previous_yaw = yaw
        twist_warning = abs(self.turns) > 2
        if twist_warning and not self.twist_warning:
            self.emit('twist')
        self.twist_warning = twist_warning
        bucket = int(cable['length'] // 5)
        if bucket != self.bucket:
            self.emit('length', metres=bucket * 5)
            self.bucket = bucket
        tension = cable['tension_max']
        warn = tension > 250
        if warn and not self.warning:
            self.emit('tension')
        self.warning = warn
        nodes = np.asarray(cable['nodes'])
        span = np.linalg.norm(nodes[-1] - nodes[0])
        self.slack_seconds += dt if cable['length'] - span > 10 else 0
        self.taut_seconds += dt if warn else 0
        near_structure = bool(cable.get('snagged_on'))
        if near_structure and not self.near_structure:
            self.emit('structure')
        self.near_structure = near_structure
        wraps = cable.get('wraps', {})
        if self.episode is None and wraps and not self.broken:
            name = max(wraps, key=lambda key: abs(wraps[key]))
            # Freeze the nearest cable point at the structure as the return target.
            candidates = nodes[1:-1]
            target = candidates[np.argmin(np.linalg.norm(candidates - position, axis=1))].copy()
            if self.world is not None:
                obstacle = next((item for item in self.world.obstacles if item.name == name), None)
                if obstacle is not None:
                    distances = np.array([obstacle.sdf(point)[0] for point in candidates])
                    near = np.flatnonzero(distances < 0.5)
                    if len(near):
                        target = candidates[near[-1]].copy()
            self.episode = dict(name=name, initial=wraps[name], peak=0.0, elapsed=0.0,
                                returned=False, correct=False, tightening=0.0, target=target)
            self.emit('snag')
        episode = self.episode
        if episode is not None:
            episode['elapsed'] += dt
            episode['peak'] = max(episode['peak'], tension)
            episode['tightening'] += dt * max(0, tension / 250 - 1)
            delta = episode['target'] - position
            distance = np.linalg.norm(delta)
            facing = np.dot(delta[:2], [math.cos(yaw), math.sin(yaw)])
            if distance < 2 and facing > 0:
                episode['returned'] = True
            remaining = wraps.get(episode['name'], 0)
            if episode['returned'] and abs(remaining) < abs(episode['initial']) - 0.15:
                episode['correct'] = remaining * episode['initial'] >= 0
            if abs(remaining) < 0.25 or cable['broken']:
                score = 30 * episode['returned'] + 30 * episode['correct']
                score += max(0, 30 - episode['peak'] / 25)
                score += max(0, 10 - episode['elapsed'] / 30)
                score -= min(40, episode['tightening'] * 5)
                self.result = dict(score=round(max(0, score)) if not cable['broken'] else 0,
                                   peak_n=episode['peak'], elapsed=episode['elapsed'],
                                   returned=episode['returned'], correct=episode['correct'])
                self.episode = None
                self.emit('released')
        return 0.0 if self.broken else -min(8.0, max(-8.0, self.turns * 0.4))

    def state(self):
        episode = self.episode
        return dict(turns=round(self.turns, 2), torque_nm=0.0 if self.broken else -min(8, max(-8, self.turns * 0.4)),
                    events=self.events[-20:], result=self.result,
                    snag=None if episode is None else dict(name=episode['name'],
                        returned=episode['returned'], tightening=round(episode['tightening'], 2)),
                    discipline_score=round(max(0, 100 - self.slack_seconds - 2 * self.taut_seconds)),
                    slack_seconds=round(self.slack_seconds, 1), taut_seconds=round(self.taut_seconds, 1))
