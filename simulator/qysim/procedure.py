"""Opt-in, per-vehicle deployment gates; generic training assumptions, not a vessel SOP.

Two check flows share the launch, dive and recovery phases:

* legacy (``begin`` without ``flow``): the ten ordered confirmations of T23, unchanged.
* deck (``begin`` with ``flow:"deck"``): only checks that are a real, observable action on the aft deck
  (walk-around, power on, thruster short test, lamp test, camera feed). Routine items (trim, compass and depth
  zero, communication, tender ready) are reported by the deck crew over the radio and need no click.
  In a career or training context the client may ask for a planted defect (``defects:true``); one realistic
  defect is then sometimes placed where the walk-around can reveal it. A defect that is missed becomes a fault
  after launch through models that already exist (thruster health, the leak alarm, link degradation).

Probabilities, timings and fault thresholds are training assumptions (docs/reference/real-rov-research.md,
BlueROV2 pre-dive list), not measured X1 values.
"""
import math
import random
from datetime import datetime, timezone

CHECKS = ('seals', 'connector', 'trim', 'power', 'communication', 'camera', 'lights',
          'thrusters', 'instruments', 'unlock')
# Deck flow: hands-on checks in order. Visual first (power off), then power and the in-air function tests.
DECK_CHECKS = ('walkaround', 'power', 'thrusters', 'lights', 'camera')
# Routine items the crew reports over the radio: (key, event that starts the timer, delay in seconds).
CREW_REPORTS = (('trim', 'begin', 4.), ('instruments', 'power', 2.), ('communication', 'power', 4.),
                ('tender', 'launch', 2.))
# Walk-around stations, in the order the camera walks round the vehicle on deck.
STATIONS = ('front', 'port', 'top', 'rear', 'starboard')
# Planted defects: where the walk-around can see them and the existing model a missed one drives after launch.
DEFECTS = {
    'line_fouled': {'station': 'side', 'fault': 'thruster_degraded'},
    'guard_cracked': {'station': 'side', 'fault': 'thruster_failed'},
    'oring_debris': {'station': 'top', 'fault': 'leak'},
    'connector_unlocked': {'station': 'rear', 'fault': 'link_degraded'},
}
PLANT_PROBABILITY = .5          # chance of one defect when the context allows it (training assumption)
DIAGNOSTIC_S = 2.               # one thruster short-test pulse
BOOT_S = 3.                     # power on until the vehicle answers (status LEDs, start-up tone); assumed
FIX_S = 3.                      # time to clear a found defect on deck
FALSE_REPORT_PENALTY = 2
FAULT_PENALTY = 10
# Missed-defect fault thresholds (training assumptions).
LINE_RUN_S = 2.                 # thruster running in the water before a loose line is drawn into the prop
LINE_HEALTH = .35               # line wound on the shaft: reduced thrust, same health model as collision damage
GUARD_RUN_S = 15.               # running time before a cracked guard piece breaks into the prop
LEAK_DEPTH_M = 3.               # debris on an O-ring seeps once the pressure differential builds
CONNECTOR_DIVE_S = 8.           # loose locking ring: the connector works under tether load and vibration
CONNECTOR_SEVERITY = .6         # above the comms model's freeze threshold: intermittent video and telemetry
RUNNING_FRACTION = .1           # thrust fraction counted as "running" for the line and guard faults


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
        # Deck flow only (flow == 'deck'); the legacy flow leaves these untouched.
        self.flow = 'legacy'
        self.powered = False
        self.boot_left = 0.
        self.lamps = False
        self.seen = set()
        self.defect = None
        self.missed = None
        self.fix_left = 0.
        self.crew = []
        self.crew_due = {}
        self.dive_time = 0.
        self.run_time = 0.

    @property
    def can_unlock(self):
        return not self.active or self.phase == 'diving'

    @property
    def next_check(self):
        order = DECK_CHECKS if self.flow == 'deck' else CHECKS
        return order[len(self.checked)] if len(self.checked) < len(order) else None

    def action(self, msg):
        action = msg.get('action')
        sim = self.sim
        if action == 'begin' and not self.active:
            if msg.get('flow') not in (None, 'deck'):
                raise ValueError('未知的檢查流程')
            # Validated before anything moves, so a refused begin leaves the vehicle where it was.
            defect = self._plant(msg) if msg.get('flow') == 'deck' else None
            self.active = True
            self.phase = 'checks'
            sim.vehicle.s.pos[:] = sim.scenario.spool_pos
            sim.vehicle.s.pos[0] += 2.
            sim.vehicle.s.pos[2] = -.5
            sim.vehicle.s.vel[:] = 0
            sim.rc_physical.rc_lock = sim.rc_sdk.rc_lock = 1
            # The sensors read the deck, not the water the scenario would have started in.
            sim.sensors.reset(sim)
            if msg.get('flow') == 'deck':
                self._begin_deck(msg, defect)
        elif self.flow == 'deck' and self._deck_action(action, msg):
            return {'type': 'procedure_result', 'procedure': self.state()}
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
            self._pulse(msg)
        elif action == 'skip' and self.phase == 'checks' and self.flow == 'deck':
            # Skipping creates no fault by itself; a planted defect that was not found stays on the vehicle.
            self.penalty += len(DECK_CHECKS) - len(self.checked)
            self.diagnostic_left = self.boot_left = self.fix_left = 0.
            self.lamps = False
            self._enter_launch()
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
            sim.sensors.reset(sim)
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

    def _pulse(self, msg):
        index = msg.get('index')
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.sim.health):
            raise ValueError('無效推進器')
        # Diagnostic pulse is accounted separately from the locked flight controller.
        if self.diagnostic_left > 0:
            raise ValueError('短測進行中')
        self.diagnostic = index
        self.diagnostic_left = DIAGNOSTIC_S

    # ── deck flow ────────────────────────────────────────────────────────────
    def _begin_deck(self, msg, defect):
        self.flow = 'deck'
        self._schedule('begin')
        if msg.get('checks') == 'crew':
            # Easier presets: the crew has done the checks; no defect is planted and nothing is penalised.
            self.checked = list(DECK_CHECKS)
            self.powered = True
            self._enter_launch()
            self._report('tender')
            return
        self.defect = defect

    def _plant(self, msg):
        """One seeded defect, only when the client's context allows it (career, campaign, exam) or forces one."""
        forced = msg.get('defect')
        seed = msg.get('seed', 0)
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError('seed must be an integer')
        if forced is not None and forced != 'none' and forced not in DEFECTS:
            raise ValueError('未知的瑕疵種類')
        if forced == 'none' or (forced is None and msg.get('defects') is not True):
            return None
        scenario = self.sim.scenario
        rng = random.Random(f'predive:{scenario.key}:{scenario.seed}:{seed}')
        if forced is None:
            if rng.random() >= PLANT_PROBABILITY:
                return None
            forced = rng.choice(sorted(DEFECTS))
        defect = {'kind': forced, 'thruster': None, 'found': False, 'fixed': False}
        station = DEFECTS[forced]['station']
        if station == 'side':
            thrusters = self.sim.vehicle.thrusters
            sides = [i for i, (_, pos, _) in enumerate(thrusters) if abs(pos[1]) > .01]
            index = rng.choice(sides or list(range(len(self.sim.health))))
            defect['thruster'] = index
            station = 'port' if thrusters[index][1][1] < 0 else 'starboard'
        defect['station'] = STATIONS.index(station)
        return defect

    def _schedule(self, trigger):
        for key, start, delay in CREW_REPORTS:
            if start == trigger and key not in self.crew and key not in self.crew_due:
                self.crew_due[key] = self.elapsed + delay

    def _report(self, key):
        self.crew_due.pop(key, None)
        if key in self.crew:
            return
        self.crew.append(key)
        if key == 'tender':
            self.confirmed = True
        self.events.append({'t': round(self.sim.t, 2), 'action': 'crew', 'key': key, 'phase': self.phase})

    def _enter_launch(self):
        """All deck checks done or skipped: a defect not cleared by now is missed and armed as a dive fault."""
        for key, _, _ in CREW_REPORTS:
            if key != 'tender':
                self._report(key)
        if self.defect and not self.defect['fixed']:
            self.missed = self.defect['kind']
        self.phase = 'launch'
        self._schedule('launch')

    def _complete(self, key):
        self.checked.append(key)
        self.events.append({'t': round(self.sim.t, 2), 'action': 'checked', 'key': key, 'phase': self.phase})
        if key == 'power':
            self._schedule('power')
        if len(self.checked) == len(DECK_CHECKS):
            self._enter_launch()

    @staticmethod
    def _station(msg):
        station = msg.get('station')
        if isinstance(station, bool) or not isinstance(station, int) or not 0 <= station < len(STATIONS):
            raise ValueError('無效檢查位置')
        return station

    def _deck_action(self, action, msg):
        """Deck-flow actions during the checks. Returns False for actions the shared code handles."""
        if self.phase != 'checks' or action not in ('look', 'report', 'fix', 'check', 'test'):
            return False
        expected = self.next_check
        if action == 'look' and expected == 'walkaround':
            self.seen.add(self._station(msg))
        elif action == 'report' and expected == 'walkaround':
            self._report_defect(self._station(msg))
        elif action == 'fix' and expected == 'walkaround':
            defect = self.defect
            if not defect or not defect['found'] or defect['fixed'] or self.fix_left > 0:
                raise ValueError('沒有待排除的異常')
            self.fix_left = FIX_S
        elif action == 'test' and expected == 'thrusters':
            self._pulse(msg)
        elif action == 'check' and msg.get('key') == expected:
            self._deck_check(expected)
        else:
            raise ValueError('請依序完成檢查')
        self.events.append({'t': round(self.sim.t, 2), 'action': action, 'phase': self.phase})
        return True

    def _report_defect(self, station):
        if station not in self.seen:
            raise ValueError('請先走到該位置查看')
        defect = self.defect
        t = round(self.sim.t, 2)
        if defect and defect['station'] == station:
            if not defect['found']:
                defect['found'] = True
                self.events.append({'t': t, 'action': 'defect_found', 'defect': defect['kind']})
            return
        self.penalty += FALSE_REPORT_PENALTY
        self.events.append({'t': t, 'action': 'false_report', 'station': station})

    def _deck_check(self, key):
        if key == 'walkaround':
            if len(self.seen) < len(STATIONS):
                raise ValueError('請繞機看完每個位置')
            if self.fix_left > 0 or (self.defect and self.defect['found'] and not self.defect['fixed']):
                raise ValueError('先排除發現的異常')
            if self.defect and not self.defect['found']:
                self.missed = self.defect['kind']    # walked past it: it goes into the water
            self._complete(key)
        elif key == 'power':
            if self.powered:
                raise ValueError('開機中')
            self.powered = True
            self.boot_left = BOOT_S
        elif key == 'lights':
            # First press lights both lamps on deck; the second confirms them and switches them off again
            # (lamps are not left burning in air).
            if not self.lamps:
                self.lamps = True
                return
            self.lamps = False
            self._complete(key)
        elif key == 'camera':
            self._complete(key)
        else:
            raise ValueError('逐顆短測後自動完成')

    def _deck_step(self, dt):
        if self.phase == 'checks':
            for key, due in list(self.crew_due.items()):
                if key != 'tender' and self.elapsed >= due:
                    self._report(key)
            if self.fix_left > 0:
                self.fix_left = max(0., self.fix_left - dt)
                if self.fix_left == 0:
                    self.defect['fixed'] = True
                    self.events.append({'t': round(self.sim.t, 2), 'action': 'defect_fixed',
                                        'defect': self.defect['kind']})
            if self.boot_left > 0:
                self.boot_left = max(0., self.boot_left - dt)
                if self.boot_left == 0:
                    self._complete('power')
            if (self.next_check == 'thrusters' and self.diagnostic_left == 0
                    and len(self.tests) == len(self.sim.health)):
                self._complete('thrusters')
        elif self.phase == 'launch' and self.elapsed >= self.crew_due.get('tender', math.inf):
            self._report('tender')
        elif self.phase == 'diving' and self.missed:
            self._missed_fault(dt)

    def _missed_fault(self, dt):
        """A missed defect shows up after launch through the models the simulator already has."""
        sim = self.sim
        self.dive_time += dt
        kind = self.missed
        index = self.defect['thruster']
        if index is not None:                    # in the water: the dive phase starts afloat
            limit = RUNNING_FRACTION * sim.vehicle.p.thruster_max
            if abs(float(sim.vehicle.s.thrust[index])) > limit:
                self.run_time += dt
        if kind == 'line_fouled' and self.run_time >= LINE_RUN_S:
            sim.health[index] = min(float(sim.health[index]), LINE_HEALTH)
            sim._log('damage', f'T{index + 1} 推進器被纜繩纏住，推力剩 {sim.health[index] * 100:.0f}%')
        elif kind == 'guard_cracked' and self.run_time >= GUARD_RUN_S:
            sim.health[index] = 0.
            sim._log('damage', f'T{index + 1} 護罩碎片卡入螺旋槳，推進器失效')
        elif kind == 'oring_debris' and sim.depth >= LEAK_DEPTH_M:
            sim.leak = True
            sim._log('leak', '艙體漏水警報：O 形環密封面有異物')
        elif kind == 'connector_unlocked' and sim.depth > 1 and self.dive_time >= CONNECTOR_DIVE_S:
            sim.link.degrade(CONNECTOR_SEVERITY)
            sim._log('link', '纜線接頭固定環未鎖緊，通訊時斷時續')
        else:
            return
        self.missed = None
        self.penalty += FAULT_PENALTY
        self.events.append({'t': round(sim.t, 2), 'action': 'fault', 'check': 'walkaround', 'defect': kind,
                            'fault': DEFECTS[kind]['fault'], 'thruster': index})

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
        if self.flow == 'deck':
            self._deck_step(dt)
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
        state = dict(started_at=self.started_at, active=self.active, phase=self.phase,
                     checked=self.checked, tests=sorted(self.tests),
                     dry_seconds=self.dry_seconds, penalty=self.penalty, events=self.events[-200:],
                     elapsed=round(self.elapsed, 1), max_depth=round(self.max_depth, 2),
                     max_cable=round(self.max_cable, 1), notes=self.notes, confirmed=self.confirmed,
                     thrusters=len(self.sim.health), diagnostic=self.diagnostic_left)
        if self.diagnostic_left > 0:
            state['diagnostic_index'] = self.diagnostic
        if self.flow == 'deck':
            state.update(flow='deck', order=list(DECK_CHECKS), stations=list(STATIONS), seen=sorted(self.seen),
                         crew=list(self.crew), powered=self.powered, boot=round(self.boot_left, 2),
                         lamps=self.lamps, fix=round(self.fix_left, 2),
                         defect=dict(self.defect) if self.defect else None)
        return state

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
