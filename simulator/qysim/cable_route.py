"""Original shelf cable training site; NED metres, KP kilometres. All dimensions are assumptions."""
import math
import numpy as np
from .ecology import SeabedTerrain
from .world import Box, Cylinder, SnagFeature

SEED = 51
STRINGS = {
    'name': '海底電纜巡線',
    'brief': '沿纜巡查 300 m，側偏保持 2 m 內；拍照記錄四種異常與懸空兩端。KP 使用公里。',
    'route': '從 KP 0.000 巡至 0.300，側偏 ≤ 2 m',
    'events': '拍照標記所有異常',
    'span': '拍攝懸空兩端，量測沿纜長度',
}


class CableTerrain(SeabedTerrain):
    def __init__(self):
        self.origin = np.array([-20., -40.])
        self.spacing = 2.
        n, e = np.meshgrid(np.arange(171) * 2 - 20, np.arange(41) * 2 - 40, indexing='ij')
        self.depths = 30.5 + .38 * np.sin(n * .07) + .15 * np.cos(e * .18 + n * .04)
        self.depths += 1.0 * np.exp(-((n - 140) / 7)**4 - ((e - 2) / 7)**4)
        self.relief = 3.


def route():
    terrain = CableTerrain()
    x = np.arange(0., 310.01, .5)
    y = 3 * np.sin(x * .035) + 1.3 * np.sin(x * .083)
    pos = np.column_stack((x, y, np.zeros(len(x))))
    bed = terrain.sample_many(pos)[0]
    z = bed - .09
    z[x < 40] = bed[x < 40] + .3 * np.minimum(1, (40 - x[x < 40]) / 5)
    partial = (x >= 40) & (x < 75)
    z[partial] = bed[partial] + .03 * np.sin(x[partial])
    span = (x >= 130) & (x <= 150)
    z[span] = np.interp(x[span], [130, 150], [z[np.searchsorted(x, 130)], z[np.searchsorted(x, 150)]])
    z -= .5 * np.exp(-((x - 242) / 3)**2)
    pos[:, 2] = z
    chain = np.r_[0., np.cumsum(np.linalg.norm(np.diff(pos, axis=0), axis=1))]
    end = np.searchsorted(chain, 300.)
    pos[end] = pos[end - 1] + (pos[end] - pos[end - 1]) * (300 - chain[end - 1]) / (chain[end] - chain[end - 1])
    pos, chain = pos[:end + 1], chain[:end + 1]
    chain[-1] = 300.
    points = []
    for p, s in zip(pos, chain):
        state = ('buried' if p[0] < 38 else 'partial' if p[0] < 75 else
                 'free_span' if 130 <= p[0] <= 150 else 'protected' if 190 <= p[0] <= 215 else
                 'crossing' if 238 <= p[0] <= 246 else 'exposed')
        points.append(dict(pos=p.tolist(), chainage_m=float(s), kp_km=float(s / 1000), burial=state))
    return points


def at(points, chainage):
    s = np.array([p['chainage_m'] for p in points])
    xyz = np.array([p['pos'] for p in points])
    return np.array([np.interp(chainage, s, xyz[:, j]) for j in range(3)])


def project(points, position):
    """Nearest horizontal segment; interpolated three-dimensional chainage, endpoint clamped."""
    xyz = np.array([p['pos'] for p in points])
    a, delta = xyz[:-1, :2], np.diff(xyz[:, :2], axis=0)
    t = np.clip(np.sum((np.asarray(position)[:2] - a) * delta, axis=1) / np.sum(delta**2, axis=1), 0, 1)
    distances = np.linalg.norm(a + delta * t[:, None] - np.asarray(position)[:2], axis=1)
    i = int(np.argmin(distances))
    s = points[i]['chainage_m'] + t[i] * (points[i + 1]['chainage_m'] - points[i]['chainage_m'])
    return float(s), float(distances[i])


def layout(seed=SEED):
    rng = np.random.default_rng(seed)
    points = route()
    terrain = CableTerrain()
    obstacles = []
    damage_s = float(rng.uniform(90, 110))
    drag_s = float(rng.uniform(165, 180))
    rope_s = float(rng.uniform(260, 280))
    for i, (a, b) in enumerate(zip(points, points[1:])):
        if a['burial'] == 'buried':
            continue
        kind = 'route_damage' if abs(a['chainage_m'] - damage_s) < .65 else 'route_cable'
        obstacles.append(Cylinder(f'route-{i}', a['pos'], b['pos'], .10, kind))
    markers = []
    for s in range(0, 301, 50):
        p = at(points, s) + [0, 1.4, 0]
        p[2] = terrain.sample_many([p])[0][0]
        obstacles.append(Cylinder(f'kp-post-{s}', p, p - [0, 0, .65], .035, 'route_steel'))
        obstacles.append(Box(f'kp-face-{s}', p - [0, 0, .6], (.02, .23, .14), 0, 'route_sign'))
        markers.append(dict(chainage_m=s, kp_km=s / 1000, face=f'kp-face-{s}'))
    for x0, length in ((190, 25), (238, 8)):
        for x in np.arange(x0, x0 + length, .65):
            p = min(points, key=lambda p: abs(p['pos'][0] - x))['pos']
            for dy in np.arange(-1.2, 1.21, .65):
                depth = p[2] - .15 if x0 == 190 else p[2] + .23
                center = (p[0], p[1] + dy, depth + rng.uniform(-.025, .025))
                obstacles.append(Box(f'mattress-{len(obstacles)}', center, (.3, .3, .16),
                                     float(rng.uniform(-3, 3)), 'route_concrete'))
    crossing = min(points, key=lambda p: abs(p['pos'][0] - 242))['pos']
    for dy in np.arange(-9., 9., .5):
        a = np.array(crossing) + [0, dy, .65]
        obstacles.append(Cylinder(f'old-cable-{dy}', a, a + [0, .5, 0], .12, 'route_steel'))
    rope = at(points, rope_s)
    for j in range(50):
        angle = j * .4
        a = rope + [.6 * math.cos(angle), .4 * math.sin(angle), -.12 - .12 * math.sin(angle * 2)]
        b = rope + [.6 * math.cos(angle + .4), .4 * math.sin(angle + .4), -.12 - .12 * math.sin((angle + .4) * 2)]
        ob = Cylinder(f'fouling-rope-{j}', a, b, .025, 'route_rope')
        ob.snag_hold = (150., 300.)
        obstacles.append(ob)
    for j in range(65):
        p = at(points, float(rng.uniform(0, 300))) + [0, rng.choice([-1, 1]) * rng.uniform(2.5, 9), 0]
        p[2] = terrain.sample_many([p])[0][0]
        radius = float(rng.uniform(.08, .3))
        obstacles.append(SnagFeature(f'route-rock-{j}', p, radius, radius + .04, item='rock'))
    for j, s in enumerate((22., 82., 156., 230., 288.)):
        p = at(points, s) + [0, 2.2, 0]
        p[2] = terrain.sample_many([p])[0][0] - .025
        if j % 2 == 0:
            for arm in range(5):
                angle = arm * math.tau / 5 + j
                end = p + [.17 * math.cos(angle), .17 * math.sin(angle), 0]
                obstacles.append(Cylinder(f'star-{j}-{arm}', p, end, .025, 'route_star'))
        else:
            obstacles.append(Cylinder(f'urchin-{j}', p, p - [0, 0, .04], .085, 'route_urchin'))
    spans = [p for p in points if p['burial'] == 'free_span']
    start, end = spans[0], spans[-1]
    anomalies = [dict(id=kind, chainage_m=s, kp_km=s / 1000, pos=at(points, s).tolist())
                 for kind, s in [('sheath_damage', damage_s), ('anchor_drag', drag_s),
                                 ('fouling_rope', rope_s), ('excess_span',
                                  (start['chainage_m'] + end['chainage_m']) / 2)]]
    data = dict(seed=seed, centerline=points, markers=markers, anomalies=anomalies,
                free_span=dict(start=start, end=end, length_m=end['chainage_m'] - start['chainage_m'],
                               allowable_m=10.), max_deviation_m=2.)
    for obstacle in obstacles:
        if isinstance(obstacle, Cylinder):
            obstacle.p0 = tuple(float(v) for v in obstacle.p0)
            obstacle.p1 = tuple(float(v) for v in obstacle.p1)
    return obstacles, data


def update(scorer, sim):
    data = sim.scenario.cable_route
    if not data:
        return
    s, deviation = project(data['centerline'], sim.vehicle.s.pos)
    if not hasattr(scorer, 'cable_coverage'):
        scorer.cable_coverage = set()
    depth = at(data['centerline'], s)[2]
    if deviation <= 2 and .4 < depth - sim.vehicle.s.pos[2] < 4:
        scorer.cable_coverage.add(min(299, int(s)))
    for ob in sim.scenario.objectives:
        if ob.kind == 'cable_route':
            ob.progress = len(scorer.cable_coverage) / 300
            ob.done = len(scorer.cable_coverage) == 300


def photo(sim):
    """An explicit shutter records visible evidence, including both span endpoints for length measurement."""
    data = sim.scenario.cable_route
    if not data:
        return
    from .physics import q_rot
    records = getattr(sim.scorer, 'cable_records', {})
    sim.scorer.cable_records = records
    pos = sim.vehicle.s.pos
    forward = q_rot(sim.vehicle.s.q, np.array([1., 0., 0.]))
    targets = data['anomalies'] + [dict(id='span_' + key, **data['free_span'][key]) for key in ('start', 'end')]
    for target in targets:
        delta = np.array(target['pos']) - pos
        distance = np.linalg.norm(delta)
        if not .5 < distance < 4 or np.dot(delta / distance, forward) < .85:
            continue
        if any(sim.world.sdf(pos + delta * t)[0] < -.02 for t in np.linspace(.05, max(.05, 1 - .15 / distance), 24)):
            continue
        records[target['id']] = dict(t=float(sim.t), kp_km=target['kp_km'], pos=target['pos'])
    for ob in sim.scenario.objectives:
        if ob.kind == 'cable_events':
            count = sum(a['id'] in records for a in data['anomalies'])
            ob.progress = count / len(data['anomalies'])
            ob.done = count == len(data['anomalies'])
        elif ob.kind == 'cable_span':
            ob.progress = sum('span_' + key in records for key in ('start', 'end')) / 2
            ob.done = ob.progress == 1
            if ob.done:
                scorer = sim.scorer
                scorer.cable_span_m = 1000 * abs(records['span_end']['kp_km'] - records['span_start']['kp_km'])
