"""Shared, server-authoritative gameplay objectives without changing ROV physics."""
import math
import numpy as np

MODES = {'free_explore': '自由探索', 'inspection_coop': '協作定點巡檢', 'scenario_training': '場景訓練'}
MODES['expedition'] = '海洋探索與工程'


class MissionRun:
    def __init__(self, sim, mode='scenario_training'):
        if mode not in MODES:
            raise ValueError('Unknown mission mode')
        self.mode = mode
        self.started_at = float(sim.t)
        self.elapsed = 0.
        self.status = {'free_explore':'exploring', 'expedition':'exploring', 'scenario_training':'training', 'inspection_coop':'active'}[mode]
        self.targets = self._targets(sim) if mode == 'inspection_coop' else []
        self.dwell = {}
        self.last_photo = None

    @staticmethod
    def _targets(sim):
        candidates = [(o.label, np.asarray(o.point, float), o.face_point)
                      for o in sim.scenario.objectives
                      if o.kind in ('inspect', 'station_keep', 'checkpoint')]
        origin = np.asarray(sim.scenario.start_pos, float)
        for radius in (5., 9., 13.):
            for angle in np.linspace(0, 2*math.pi, 12, endpoint=False):
                point = origin + [radius*math.cos(angle), radius*math.sin(angle), 0.]
                candidates.append(('觀測站', point, None))
        targets = []
        for label, point, face in candidates:
            if point[2] < .8 or sim.world.sdf(point)[0] < .8:
                continue
            if any(np.linalg.norm(point-np.asarray(t['point'])) < 3.5 for t in targets):
                continue
            index = len(targets)+1
            targets.append(dict(id=f'survey-{index}', label=f'{index}. {label}',
                point=point.tolist(), face_point=None if face is None else list(face),
                radius=1.5, hold_s=3., completed=False, completed_by=None, completed_at=None))
            if len(targets) == 3:
                break
        if not targets:
            raise ValueError('This scene has no clear inspection station')
        return targets

    def _eligible(self, sim, target):
        if sim.tether.broken:
            return False
        position = sim.vehicle.s.pos
        if np.linalg.norm(position-np.asarray(target['point'])) > target['radius']:
            return False
        if np.linalg.norm(sim.vehicle.world_velocity()) > .35:
            return False
        if target['face_point'] is not None:
            delta = np.asarray(target['face_point'])-position
            error = (math.atan2(delta[1], delta[0])-sim.yaw+math.pi) % (2*math.pi)-math.pi
            if abs(error) > math.radians(35):
                return False
        return True

    def update(self, sim, dt):
        if self.status != 'active':
            return
        # Vehicle clocks share a room tick; max prevents three pilots from
        # consuming the timer three times as quickly.
        self.elapsed = max(self.elapsed, float(sim.t)-self.started_at)
        if self.elapsed >= 720.:
            self.elapsed, self.status = 720., 'expired'
            return
        vehicle_id = str(sim.vehicle_id)
        progress = self.dwell.setdefault(vehicle_id, {})
        for target in self.targets:
            if not target['completed']:
                progress[target['id']] = (min(target['hold_s'], progress.get(target['id'], 0.)+dt)
                    if self._eligible(sim, target) else 0.)

    def photo(self, sim):
        if self.mode != 'inspection_coop':
            return
        self.update(sim, 0.)
        vehicle_id = str(sim.vehicle_id)
        completed = None
        message = '靠近觀測站，保持低速穩定 3 秒後再拍照；有巡檢物時須朝向目標。'
        if self.status != 'active':
            message = '本次任務已完成。' if self.status == 'completed' else '本次任務時間已結束。'
        else:
            for target in self.targets:
                dwell = self.dwell.get(vehicle_id, {}).get(target['id'], 0.)
                if not target['completed'] and dwell >= target['hold_s']-1e-8 and self._eligible(sim, target):
                    target.update(completed=True, completed_by=vehicle_id,
                                  completed_at=round(self.elapsed, 2))
                    completed = target['id']
                    message = '觀測站拍照完成，已同步給全隊。'
                    if all(t['completed'] for t in self.targets):
                        self.status = 'completed'
                    break
        self.last_photo = dict(vehicle_id=vehicle_id, target_id=completed, message=message, t=round(sim.t, 2))

    def state(self, sim):
        targets, ready_target = [], None
        for target in self.targets:
            own = min(1., self.dwell.get(str(sim.vehicle_id), {}).get(target['id'], 0.)/target['hold_s'])
            progress = max((p.get(target['id'], 0.)/target['hold_s'] for p in self.dwell.values()), default=0.)
            ready = self.status == 'active' and not target['completed'] and own >= 1.-1e-8 and self._eligible(sim, target)
            if ready and ready_target is None:
                ready_target = target['id']
            targets.append({**target, 'progress': 1. if target['completed'] else round(progress, 3),
                            'own_progress': round(own, 3), 'ready': ready})
        complete = sum(t['completed'] for t in targets)
        return dict(mode=self.mode, label=MODES[self.mode], status=self.status,
            elapsed=round(self.elapsed, 2), time_limit=720 if targets else None,
            remaining=round(max(0., 720-self.elapsed), 2) if targets else None,
            completed=complete, total=len(targets), score=round(100*complete/len(targets)) if targets else None,
            ready_target=ready_target, targets=targets, last_photo=self.last_photo)

    def score_state(self, sim):
        if self.mode == 'scenario_training':
            return sim.scorer.as_dict()
        state = self.state(sim)
        return dict(score=state['score'] or 0, elapsed=state['elapsed'],
            failed='巡檢時間結束' if self.status == 'expired' else '', finished=self.status == 'completed',
            current_index=state['completed'], objectives=[{**target, 'kind':'inspect', 'done':target['completed']}
                for target in state['targets']], penalties=[], penalty_total=0)


def ensure_mission(sim):
    if not hasattr(sim.world, 'mission_run'):
        sim.world.mission_run = MissionRun(sim)
    return sim.world.mission_run
