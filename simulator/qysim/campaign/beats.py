"""Host evidence for directed campaign beats, including the pose recorded by the real shutter."""
from math import atan2, degrees, hypot


def photo_matches(target, photo):
    if not photo['name'].endswith('.JPG'):
        return False
    pose = photo['pose']
    n, e, d = (coord - pose[axis] for coord, axis in zip(target, ('n', 'e', 'depth')))
    angle = abs((degrees(atan2(e, n)) - pose['yaw'] + 180) % 360 - 180)
    horizontal = hypot(n, e)
    stand_off = (n * target[0] + e * target[1]) / hypot(target[0], target[1])
    return stand_off >= 2 and hypot(n, e, d) < 8 and abs(d) < horizontal * .3 and angle < 20


class BeatRun:
    def __init__(self, script, sim):
        self.beats = script
        self.indices = {beat['id']: i for i, beat in enumerate(script)}
        self.plates = [dict(id=b['id'], target=b['target']) for b in script if 'target' in b]
        self.accepted = 0
        self.missed = False
        self.enter(sim)

    def enter(self, sim):
        self.since = sim.t
        self.depth = sim.depth
        self.neutral_since = sim.t
        self.files = len(sim.camera.files)

    def observe(self, sim, beat):
        if beat.get('condition', {}).get('path') != 'drift':
            return
        axes = ('left_ud', 'left_lr', 'right_ud', 'right_lr')
        if any(abs(getattr(sim.rc, axis) - 1500) >= 40 for axis in axes):
            self.depth = sim.depth
            self.neutral_since = sim.t

    def evidence(self, sim, beat):
        framed = bool(beat and beat.get('target') and any(
            photo_matches(beat['target'], photo) for photo in sim.camera.files[self.files:]))
        drift = abs(self.depth - sim.depth) if sim.t - self.neutral_since >= 1 else 0
        return dict(framedPhoto=framed, drift=round(drift, 3))

    def advance(self, node, msg, sim, matches):
        if not node or msg.get('beat') != node['id']:
            return None
        evidence = self.evidence(sim, node)
        condition = node.get('condition')
        passed = condition and matches(condition, {**sim.viewer_state(), **evidence})
        if not passed and sim.t - self.since < node['limit']:
            return None
        target = node['next'] if passed else node.get('timeout', node['next'])
        if msg.get('next') != target:
            return None
        self.missed = bool(condition and not passed)
        self.accepted += int(evidence['framedPhoto'])
        self.enter(sim)
        return self.indices.get(target, len(self.beats))

    def state(self, sim, node):
        return dict(directed=True, plates=self.plates, beat_since=self.since, accepted=self.accepted,
                    missed=self.missed, **self.evidence(sim, node))
