"""Opt-in, per-vehicle deployment gates; generic training assumptions, not a vessel SOP."""
import math
from datetime import datetime, timezone

CHECKS = ('seals', 'connector', 'trim', 'power', 'communication', 'camera', 'lights',
          'thrusters', 'instruments', 'unlock')


class Procedure:
    def __init__(self, sim):
        self.sim = sim
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.active = False
        self.phase = 'quick'
        self.checked = []
        self.events = []
        self.failures = []
        self.dry_seconds = 0.
        self.penalty = 0
        self.max_depth = 0.
        self.max_cable = 0.
        self.elapsed = 0.
        self.recovered = 0.
        self.tests = set()
        self.notes = ''
        self.confirmed = False
        self.diagnostic = None
        self.diagnostic_left = 0.

    @property
    def can_unlock(self):
        return not self.active or self.phase == 'diving'

    def action(self, msg):
        action = msg.get('action')
        sim = self.sim
        if action == 'begin' and not self.active:
            self.active = True
            self.phase = 'checks'
            sim.vehicle.s.pos[:] = sim.scenario.spool_pos
            sim.vehicle.s.pos[0] += 2.
            sim.vehicle.s.pos[2] = -.5
            sim.vehicle.s.vel[:] = 0
            sim.rc_physical.rc_lock = sim.rc_sdk.rc_lock = 1
        elif action == 'check' and self.phase == 'checks':
            key = msg.get('key')
            if key != CHECKS[len(self.checked)]:
                raise ValueError('請依序完成檢查')
            if key == 'thrusters' and len(self.tests) != len(sim.health):
                raise ValueError('請逐顆短測推進器')
            self.checked.append(key)
            if len(self.checked) == len(CHECKS):
                self.phase = 'launch'
        elif action == 'test' and self.phase == 'checks' and self.checked == list(CHECKS[:7]):
            index = msg.get('index')
            if not isinstance(index, int) or not 0 <= index < len(sim.health):
                raise ValueError('無效推進器')
            # Diagnostic pulse is accounted separately from the locked flight controller.
            if self.diagnostic_left > 0:
                raise ValueError('短測進行中')
            self.diagnostic = index
            self.diagnostic_left = 2.
        elif action == 'skip' and self.phase == 'checks':
            for key in CHECKS:
                if key not in self.checked and sim.rng.random() < .35:
                    self.failures.append(key)
            self.penalty += len(CHECKS) - len(self.checked)
            self.phase = 'launch'
        elif action == 'tender' and self.phase == 'launch':
            self.confirmed = True
        elif action == 'lower' and self.phase == 'launch':
            if msg.get('point') != 'upstream' or not self.confirmed:
                raise ValueError('請選上游下水點並與纜線手確認；禁止拋擲')
            self.phase = 'water_check'
            sim.vehicle.s.pos[:] = sim.scenario.spool_pos
            sim.vehicle.s.pos[2] = .5
            flow = sim.world.current.sample(sim.vehicle.s.pos, sim.world.seabed_depth, sim.t)
            horizontal = math.hypot(float(flow[0]), float(flow[1]))
            if horizontal > .01:
                sim.vehicle.s.pos[0] -= float(flow[0]) / horizontal
                sim.vehicle.s.pos[1] -= float(flow[1]) / horizontal
            sim.vehicle.s.vel[:] = 0
            from .tether import Tether
            from .physics import q_rot
            gland = sim.vehicle.s.pos + q_rot(sim.vehicle.s.q, sim.tether.gland_body)
            sim.tether = Tether(sim.world, sim.tether.spool, gland,
                                sim.tether.length, gland_body=sim.tether.gland_body)
            sim.tether.settle(2., sim.vehicle.s.pos, sim.vehicle.s.q)
        elif action == 'water_confirm' and self.phase == 'water_check':
            self.phase = 'diving'
        elif action == 'recover' and self.phase == 'diving':
            if sim.depth > .8 or sim.rc.rc_lock != 1:
                raise ValueError('請先回到水面並上鎖')
            sim._stop_record()
            self.phase = 'recovering'
        elif action == 'rinse' and self.phase == 'post':
            self.phase = 'inspect'
        elif action == 'inspect' and self.phase == 'inspect':
            self.phase = 'log'
        elif action == 'save' and self.phase == 'log':
            self.notes = str(msg.get('notes', ''))[:4000]
            self.phase = 'complete'
        else:
            raise ValueError('目前階段無法執行此操作')
        self.events.append({'t': round(sim.t, 2), 'action': action, 'phase': self.phase})
        return {'type': 'procedure_result', 'procedure': self.state()}

    def _dry_warning(self):
        if self.dry_seconds > 30 and not any(e.get('action') == 'dry_warning' for e in self.events):
            self.penalty += 10
            self.events.append({'t': self.sim.t, 'action': 'dry_warning'})

    def step(self, dt):
        if not self.active:
            return
        sim = self.sim
        if not self.can_unlock:
            sim.rc_physical.rc_lock = sim.rc_sdk.rc_lock = 1
        self.elapsed += dt
        self.max_depth = max(self.max_depth, sim.depth)
        self.max_cable = max(self.max_cable, sim.tether.length)
        if self.diagnostic_left > 0:
            duration = min(dt, self.diagnostic_left)
            self.dry_seconds += duration
            self.diagnostic_left = max(0., self.diagnostic_left - dt)
            if self.diagnostic_left == 0:
                self.tests.add(self.diagnostic)
            self._dry_warning()
        if self.phase in ('checks', 'launch', 'post', 'inspect', 'log', 'complete'):
            sim.vehicle.s.pos[2] = -.5
            sim.vehicle.s.vel[:] = 0
        if self.phase == 'diving' and sim.depth > 1 and self.failures:
            key = self.failures.pop(0)
            if key not in ('thrusters', 'lights'):
                self.phase = 'recovering'
                sim.rc_physical.rc_lock = sim.rc_sdk.rc_lock = 1
            elif key == 'thrusters':
                sim.health[0] = .5
            else:
                sim.rc_physical.right_switch = sim.rc_sdk.right_switch = 0
            self.penalty += 10
            self.events.append({'t': sim.t, 'action': 'fault', 'check': key})
        if self.phase == 'recovering':
            sim.vehicle.current_ned = sim.world.current.sample(
                sim.vehicle.s.pos, sim.world.seabed_depth, sim.t)
            # A training recovery rate, reduced by current and wave phase; not a measured limit.
            speed = float(sum(x * x for x in sim.vehicle.current_ned)) ** .5
            rate = .4 / (1 + speed + .3 * abs(math.sin(sim.t)))
            target = sim.scenario.spool_pos
            dx = float(target[0] - sim.vehicle.s.pos[0])
            dy = float(target[1] - sim.vehicle.s.pos[1])
            distance = math.hypot(dx, dy)
            if distance > .01:
                fraction = min(1., rate * dt / distance)
                sim.vehicle.s.pos[0] += dx * fraction
                sim.vehicle.s.pos[1] += dy * fraction
            sim.vehicle.s.pos[2] -= rate * dt
            if sim.depth <= .05 and distance < .75:
                self.recovered += rate * dt
            if self.recovered >= .5:
                self.phase = 'post'

    def state(self):
        return dict(started_at=self.started_at, active=self.active, phase=self.phase,
                    checked=self.checked, tests=sorted(self.tests),
                    dry_seconds=self.dry_seconds, penalty=self.penalty, events=self.events[-200:],
                    elapsed=round(self.elapsed, 1), max_depth=round(self.max_depth, 2),
                    max_cable=round(self.max_cable, 1), notes=self.notes, confirmed=self.confirmed,
                    thrusters=len(self.sim.health), diagnostic=self.diagnostic_left)

    def score(self, base):
        if not self.active:
            return base
        result = dict(base)
        result['score'] = max(0, result.get('score', 0) - self.penalty)
        result['penalty_total'] = result.get('penalty_total', 0) + self.penalty
        result['procedure_penalty'] = self.penalty
        return result

    def deck_step(self, dt):
        """Deck or recovery line supports the hull; recovery uses a prescribed hauling rate."""
        supported = ('checks', 'launch', 'recovering', 'post', 'inspect', 'log', 'complete')
        if not self.active or self.phase not in supported:
            return False
        sim = self.sim
        sim.vehicle.s.thrust[:] = 0
        sim.vehicle.s.vel[:] = 0
        if self.diagnostic_left > 0:
            sim.vehicle.s.thrust[self.diagnostic] = .05 * sim.vehicle.p.thruster_max
        sim.t += dt
        return True
