"""Original reservoir training layout, NED metres. Dimensions are assumptions, not a surveyed site."""
import math
import numpy as np
from .world import Box, Cylinder

STRINGS = {
    'name': '水庫進水口',
    'brief': '沿護坡下潛，檢查攔污柵堵塞並拍照，再回到浮動碼頭。留意沉木勾纜及進水口局部吸入流。',
    'descend': '沿護坡下潛到進水口',
    'photo': '檢查攔污柵並拍下堵塞處',
    'return': '回到浮動碼頭',
}
TARGET = (20., 0., 10.)
CAMERAS = {
    'reservoir_overlook': {'eye': [-16, -16, -12], 'target': [8, 4, 0]},
    'reservoir_equipment': {'eye': [4, -5, -2], 'target': [7, -3, -.6]},
}


def layout():
    obs = []

    def box(name, center, half, kind='concrete', yaw=0):
        obs.append(Box(name, center, half, yaw, 'reservoir_' + kind))

    def tube(name, a, b, radius, kind='steel', snag=False):
        ob = Cylinder(name, a, b, radius, 'reservoir_' + kind)
        if snag:
            ob.snag_hold = (100., 220.)
        obs.append(ob)

    # Existing yaw-only boxes approximate the slope in 0.15 m vertical steps.
    for i in range(100):
        x = -12 + i * .3
        z = min(22.9, 1.2 * x + 1)
        box(f'revetment-{i}', (x, 0, (z + 23) / 2), (.15, 25, (23 - z) / 2))
    for i in range(36):
        box(f'stair-{i}', (-10 + i * .3, -8, -5 + i * .15), (.16, .7, .16))
    for y in (-3., 5.):
        for i in range(22):
            for j in range(3):
                box(f'float-{y}-{i}-{j}', (i * .5, y + j * .5, -.05),
                    (.245, .245, .22), 'orange' if (i // 4) % 2 == 0 else 'blue')
        for i in range(6):
            x = i * 2.
            tube(f'post-{y}-{i}', (x, y, -.3), (x, y, -1.3), .035, 'white')
            if i:
                tube(f'rail-{y}-{i}', (x-2, y, -1.1), (x, y, -1.1), .018, 'rope')
    # Concrete portal, rear gate and paired gate slots, open approach on north-facing side.
    for y in (-3.3, 3.3):
        box(f'intake-pier-{y}', (22, y, 8), (2, .5, 8))
        box(f'gate-slot-{y}', (22.8, y * .82, 10), (.12, .12, 5), 'steel')
    box('intake-header', (22, 0, 4.5), (2, 3, .5))
    box('intake-sill', (22, 0, 15.5), (2, 3, .5))
    box('closed-gate', (23.5, 0, 10), (.15, 2.8, 5), 'steel')
    for i in range(17):
        y = -2.8 + i * .35
        tube(f'rack-bar-{i}', (20, y, 5), (20, y, 15), .055, snag=True)
    for z in (6., 10., 14.):
        tube(f'rack-cross-{z}', (20, -2.8, z), (20, 2.8, z), .08, snag=True)
    for i in range(8):
        y = -2 + i * .48
        tube(f'rack-branch-{i}', (19.8, y, 9 + i % 3 * .3),
             (19.7, y + 1., 10.4 + i % 2 * .3), .06, 'wood', True)
    for i in range(3):
        box(f'rack-litter-{i}', (19.82, i*.6-.6, 10.5), (.06, .2, .14), 'white', i*27)
    tube('sunken-trunk', (13, -6, 19), (19, -3, 22), .24, 'wood', True)
    for i in range(4):
        tube(f'sunken-branch-{i}', (14+i, -5, 20), (14+i, -7, 18.5), .07, 'wood', True)
    box('control-case', (7, -2.5, -.65), (.5, .35, .35), 'steel')
    box('tool-case', (8.5, -2.5, -.5), (.4, .25, .2), 'orange')
    for loop in range(12):
        for i in range(24):
            a, b = i*math.tau/24, (i+1)*math.tau/24
            radius = .4 + loop*.012
            tube(f'umbilical-{loop}-{i}',
                 (6+radius*math.cos(a), -2.5+radius*math.sin(a), -.32-loop*.012),
                 (6+radius*math.cos(b), -2.5+radius*math.sin(b), -.32-loop*.012), .012, 'cable')
    for i in range(32):
        box(f'gauge-{i}', (-3, -5, -i*.2), (.08, .16, .1), 'white' if i % 2 else 'red')
    # Generic small service boat and canopy work platform; no brands, signage or crew.
    for x, y, canopy in ((6, -5, False), (7, 8, True)):
        box(f'boat-deck-{y}', (x, y, -.1), (2.5, 1, .22), 'blue')
        for side in (-1, 1):
            box(f'boat-gunwale-{y}-{side}', (x, y+side, -.45), (2.5, .08, .25), 'white')
        box(f'boat-stern-{y}', (x-2.5, y, -.4), (.08, 1, .25), 'white')
        if canopy:
            for dx in (-2, 2):
                for dy in (-.8, .8):
                    tube(f'canopy-post-{dx}-{dy}', (x+dx, y+dy, -.2),
                         (x+dx, y+dy, -2.5), .04, 'white')
            box('canopy', (x, y, -2.5), (2.4, 1.2, .05), 'blue')
    return obs


def above_water(ob):
    if isinstance(ob, Box):
        return ob.center[2] + ob.half[2] < 0
    return max(ob.p0[2], ob.p1[2]) + ob.radius < 0


def collision_layout():
    return [ob for ob in layout() if not above_water(ob)]


def decoration():
    return [dict(ob.as_dict(), above_water=True) for ob in layout() if above_water(ob)]


def photo(sim):
    if sim.scenario.key != 'reservoir_intake' or sim.scorer.current_index != 1:
        return
    from .physics import q_rot
    pos = sim.vehicle.s.pos
    delta = np.asarray(TARGET) - pos
    distance = np.linalg.norm(delta)
    if not .6 < distance < 2.8:
        return
    forward = q_rot(sim.vehicle.s.q, np.array([1., 0., 0.]))
    if np.dot(delta / distance, forward) < .94:
        return
    # Rack bars and lodged debris are the subject, not an occluder of their own photograph.
    blockers = [o for o in sim.world.obstacles if not o.name.startswith('rack-')]
    for t in np.linspace(.05, .95, 20):
        if any(o.sdf(pos + delta*t)[0] < -.01 for o in blockers):
            return
    ob = sim.scenario.objectives[1]
    ob.done = True
    ob.progress = 1.
