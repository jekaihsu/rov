"""Authenticated room supervision, timed physical overrides and training evidence.

All assessment limits are provisional until calibrated by company operators.
"""
from collections import deque
from copy import deepcopy
import math
import secrets

import numpy as np

PHASES = ('descent', 'transit', 'hover', 'orbit', 'dock')
DEFAULT_LIMITS = {'path': 2., 'heading': 15., 'depth': 1., 'hover': 1., 'distance': 1., 'speed': .3}
# Evidence is sampled at 1 Hz, so this keeps the most recent hour of each vehicle's run.
# Older samples are dropped first; a report then covers only the retained window.
MAX_SAMPLES_PER_VEHICLE = 3600
# Archived reports carry their full trajectory. Only the newest ones are kept.
MAX_REPORTS = 16
PHYSICAL_KINDS = ('thruster', 'battery', 'current', 'visibility', 'freeze')
# Vehicle-system faults. 'freeze' above pauses physics; 'video_freeze' only freezes the video link.
SYSTEM_KINDS = ('video_delay', 'video_freeze', 'link_degrade', 'comms_loss', 'power_trip', 'leak', 'overheat')
# Overheat strength 1 adds this many degrees to motor and driver readings (provisional).
OVERHEAT_C = 50.
# Sensor faults act on the vehicle's sensor layer (qysim/sensors.py), never on physics truth.
SENSOR_FAULTS = ('compass', 'depth_sensor', 'dvl', 'altimeter')


def statistics(values, tolerance):
    if not values:
        return None
    return {'rms': math.sqrt(sum(v * v for v in values) / len(values)),
            'min': min(values), 'max': max(values),
            'outside_fraction': sum(abs(v) > tolerance for v in values) / len(values)}


class Instructor:
    def __init__(self, room):
        self.room = room
        self.clock = 0.
        self.active = []
        self.events = []
        self.samples = {}
        self.reports = []
        self.supervised = False
        self.finalized = set()
        self.phase = 'descent'
        self.reference = {}
        self.limits = {'still': dict(DEFAULT_LIMITS), 'current': dict(DEFAULT_LIMITS)}
        self.grade_limits = {'green': .1, 'yellow': .3, 'smoothness': .25}

    @staticmethod
    def authorized(configured, supplied):
        return bool(configured and isinstance(supplied, str)
                    and secrets.compare_digest(configured.encode(), supplied.encode()))

    def inject(self, msg):
        kind = msg['kind']
        vid = msg.get('vehicle_id', 'v1')
        sim = self.room.vehicles[vid]
        if 'cancel_start' in msg:
            start = msg['cancel_start']
            if isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start):
                raise ValueError('cancel_start must be finite')
            event = next((e for e in self.active if e['kind'] == kind
                          and e['vehicle_id'] == vid and e['start'] == start), None)
            if event is None:
                raise ValueError('override no longer active')
            self.restore(event)
            self.active.remove(event)
            self.room._snapshot = None
            return
        strength = float(msg.get('strength', 1))
        duration = float(msg.get('duration', 10))
        if not math.isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError('strength must be 0..1')
        if not math.isfinite(duration) or not 0 < duration <= 3600:
            raise ValueError('duration must be 0..3600 seconds')
        if kind not in PHYSICAL_KINDS + SYSTEM_KINDS + SENSOR_FAULTS:
            raise ValueError('unsupported physical override')
        if kind in SENSOR_FAULTS and sim.sensors.ideal:
            raise ValueError('sensor faults need the realistic sensor layer')
        scope = 'room' if kind in ('current', 'visibility') else vid
        if any(e['scope'] == scope and e['kind'] == kind for e in self.active):
            raise ValueError('overlapping override')
        event = {'kind': kind, 'vehicle_id': vid, 'scope': scope, 'strength': strength,
                 'start': self.clock, 'end': self.clock + duration, 'reaction_s': None}
        if kind == 'thruster':
            index = int(msg.get('index', 0))
            if not 0 <= index < len(sim.health):
                raise ValueError('invalid thruster index')
            event['index'] = index
            event['original'] = float(sim.health[index])
        elif kind == 'battery':
            event['original'] = sim.battery
        elif kind == 'visibility':
            event['original'] = sim.scenario.visibility_m
        elif kind == 'current':
            event['original'] = deepcopy(sim.world.current)
        elif kind == 'comms_loss':
            event['original'] = dict(sim.link.config)
            self.configure_loss(sim, msg)
        elif kind in SYSTEM_KINDS or kind in SENSOR_FAULTS:
            event['original'] = None
        else:
            event['original'] = sim.paused
        event['controls'] = sim.rc.as_dict()
        self.active.append(event)
        self.events.append({k: v for k, v in event.items() if k not in ('original', 'controls')})
        self.enforce(event)
        self.room._snapshot = None

    @staticmethod
    def configure_loss(sim, msg):
        """Optional failsafe policy and reconnect time for one comms-loss injection."""
        values = {}
        if 'failsafe' in msg:
            values['failsafe_action'] = msg['failsafe']
        for field, key in (('failsafe_delay', 'failsafe_delay_s'), ('reconnect', 'reconnect_s')):
            if field in msg:
                value = msg[field]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 600:
                    raise ValueError(f'{field} must be 0..600 seconds')
                values[key] = value
        sim.link.configure(values)

    def enforce_system(self, sim, kind, strength):
        if kind == 'video_delay':
            sim.link.fixed_lag_s = strength * sim.link.config['max_video_lag_s']
        elif kind == 'video_freeze':
            sim.link.forced_freeze = True
        elif kind == 'link_degrade':
            sim.link.degrade(strength)
        elif kind == 'comms_loss':
            sim.link.lose(rc=sim.rc)
        elif kind == 'power_trip':
            sim.power.trip()
            sim.link.lose(cause='power', immediate=True)
        elif kind == 'leak':
            sim.leak = True
        elif kind == 'overheat':
            sim.thermal.injected_c = strength * OVERHEAT_C

    @staticmethod
    def restore_system(sim, event):
        kind = event['kind']
        if kind == 'video_delay':
            sim.link.fixed_lag_s = 0.
        elif kind == 'video_freeze':
            sim.link.forced_freeze = False
        elif kind == 'link_degrade':
            sim.link.clear_degrade()
        elif kind == 'comms_loss':
            sim.link.restore()
            sim.link.config.update(event['original'])
        elif kind == 'power_trip':
            sim.power.reset()
            sim.link.restore()
        elif kind == 'leak':
            sim.leak = False
        elif kind == 'overheat':
            sim.thermal.injected_c = 0.

    def enforce(self, event):
        sim = self.room.vehicles.get(event['vehicle_id'])
        if sim is None:
            return
        kind, strength = event['kind'], event['strength']
        if kind in SYSTEM_KINDS:
            self.enforce_system(sim, kind, strength)
        elif kind == 'thruster':
            sim.health[event['index']] = min(sim.health[event['index']], event['original'] * (1 - strength))
        elif kind == 'battery':
            sim.battery = min(sim.battery, event['original'] * (1 - strength))
        elif kind == 'visibility':
            for vehicle in self.room.vehicles.values():
                vehicle.scenario.visibility_m = max(.1, event['original'] * (1 - strength))
        elif kind == 'current':
            current = sim.world.current
            current.surface_kn = strength * 4
            current.mid_kn = strength * 4
            current.bottom_kn = strength * 4
        elif kind == 'freeze':
            sim.paused = True
        elif kind in SENSOR_FAULTS:
            sim.sensors.set_fault(kind, strength)

    def restore(self, event):
        sim = self.room.vehicles.get(event['vehicle_id'])
        if sim is None:
            return
        kind = event['kind']
        if kind in SYSTEM_KINDS:
            self.restore_system(sim, event)
        elif kind == 'thruster':
            sim.health[event['index']] = event['original']
        elif kind == 'battery':
            sim.battery = event['original']
        elif kind == 'visibility':
            for vehicle in self.room.vehicles.values():
                vehicle.scenario.visibility_m = event['original']
        elif kind == 'current':
            sim.world.current.__dict__.update(deepcopy(event['original'].__dict__))
        elif kind == 'freeze':
            sim.paused = event['original']
        elif kind in SENSOR_FAULTS:
            sim.sensors.clear_fault(kind)
        self.events.append({'kind': kind, 'vehicle_id': event['vehicle_id'], 'restored_at': self.clock})

    def update(self, dt):
        self.clock += dt
        for event in list(self.active):
            if self.clock >= event['end']:
                self.restore(event)
                self.active.remove(event)
            else:
                self.enforce(event)
                sim = self.room.vehicles.get(event['vehicle_id'])
                if sim and event['reaction_s'] is None and sim.rc.as_dict() != event['controls']:
                    event['reaction_s'] = self.clock - event['start']
                    self.events.append({'kind': 'control_response', 'vehicle_id': event['vehicle_id'],
                                        'reaction_s': event['reaction_s'], 'injection_start': event['start']})
        if self.sampling and int(self.clock) != int(self.clock - dt):
            for vid, sim in self.room.vehicles.items():
                self.sample(vid, sim)

    @property
    def sampling(self):
        """Evidence is collected only while someone supervises or an override is running."""
        return bool(self.supervised or self.active)

    def archive(self, report):
        self.reports.append(report)
        del self.reports[:-MAX_REPORTS]

    def sample(self, vid, sim):
        state = sim.viewer_state()
        ref = self.reference.get(vid, {})
        point = np.asarray(ref.get('target', sim.scenario.start_pos), float)
        delta = sim.vehicle.s.pos - point
        yaw = state['euler'][2]
        origin = np.asarray(ref.get('path_start', sim.scenario.start_pos), float)
        segment = point[:2] - origin[:2]
        projection = float(np.dot(sim.vehicle.s.pos[:2] - origin[:2], segment))
        fraction = np.clip(projection / max(float(np.dot(segment, segment)), 1e-12), 0, 1)
        nearest = origin[:2] + segment * fraction
        errors = {'path': float(np.linalg.norm(sim.vehicle.s.pos[:2] - nearest)),
                  'heading': (yaw - ref.get('heading', yaw) + 180) % 360 - 180,
                  'depth': sim.depth - ref.get('depth', point[2]),
                  'hover': float(np.linalg.norm(delta[:2])),
                  'distance': float(np.linalg.norm(delta)) - ref.get('distance', 0),
                  'speed': max(ref.get('speed_min', 0) - float(np.linalg.norm(sim.vehicle.s.vel)),
                               float(np.linalg.norm(sim.vehicle.s.vel)) - ref.get('speed_max', .5), 0)}
        if vid in self.finalized:
            return
        self.samples.setdefault(vid, deque(maxlen=MAX_SAMPLES_PER_VEHICLE)).append({'t': self.clock, 'phase': self.phase,
            'pos': state['pos'], 'errors': errors, 'controls': [getattr(sim, 'last_pilot', {}).get(k, 0)
                for k in ('surge', 'sway', 'heave', 'roll', 'pitch', 'yaw')],
            'tension': state['tether']['tension_rov'], 'wraps': state['tether']['wraps'],
            'current': state['current_kn'] > .1, 'completion': state['score'],
            'collisions': state['events']})

        if state['score'].get('finished') or state['score'].get('failed'):
            self.archive(self.report(vid))
            self.finalized.add(vid)

    def report(self, vid):
        samples = list(self.samples.get(vid, []))
        matrix = {}
        for phase in PHASES:
            matrix[phase] = {}
            for flow in ('still', 'current'):
                rows = [s for s in samples if s['phase'] == phase and s['current'] == (flow == 'current')]
                result = {}
                for key, tolerance in self.limits[flow].items():
                    metric = statistics([s['errors'][key] for s in rows], tolerance)
                    if metric:
                        fraction = metric['outside_fraction']
                        metric['grade'] = ('green' if fraction <= self.grade_limits['green']
                                           and metric['rms'] <= tolerance else
                                           'yellow' if fraction <= self.grade_limits['yellow']
                                           and metric['rms'] <= 2 * tolerance else 'red')
                    result[key] = metric
                matrix[phase][flow] = result
        controls = np.array([s['controls'] for s in samples])
        smoothness = None
        if len(controls) > 1:
            changes = np.diff(controls, axis=0)
            smoothness = {'variance': np.var(controls, axis=0).tolist(),
                          'zero_crossings': np.sum(controls[1:] * controls[:-1] < 0, axis=0).tolist(),
                          'reversals': np.sum(changes[1:] * changes[:-1] < 0, axis=0).tolist()}
            variance = float(np.max(np.var(controls, axis=0)))
            limit = self.grade_limits['smoothness']
            smoothness['grade'] = 'green' if variance <= limit else 'yellow' if variance <= 2 * limit else 'red'
        collisions = {str(e): e for s in samples for e in s['collisions']}
        return {'version': 1, 'vehicle_id': vid, 'provisional': True, 'limits': deepcopy(self.limits),
                'grade_limits': dict(self.grade_limits), 'elapsed': self.clock,
                'completion': samples[-1]['completion'] if samples else None,
                'supervision': {'phase': self.phase, 'reference': deepcopy(self.reference),
                                'world': {'obstacles': [o.as_dict() for o in self.room.primary.world.obstacles],
                                          'objectives': [o.as_dict() for o in self.room.primary.scenario.objectives]},
                                'active': [{k: v for k, v in e.items() if k not in ('original', 'controls')}
                                           for e in self.active]},
                'matrix': matrix, 'smoothness': smoothness, 'collisions': list(collisions.values()),
                'max_tension': max((s['tension'] for s in samples), default=0),
                'wraps': [s['wraps'] for s in samples if s['wraps']],
                'events': deepcopy(self.events), 'trajectory': deepcopy(samples)}

    def finish(self):
        for vid in self.samples:
            if vid not in self.finalized:
                self.archive(self.report(vid))
        for event in self.active:
            self.restore(event)
        self.active.clear()
        self.samples.clear()
        self.finalized.clear()
        self.events.clear()
        self.clock = 0.
