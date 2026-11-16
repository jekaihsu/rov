"""Original circular pen and mission evidence; illustrative dimensions, NED metres."""
import math
import numpy as np
from .world import Box, Cylinder

STRINGS = {
    "name": "離岸養殖箱網",
    "brief": "繞網檢查、拍攝破洞，再使用配有機械臂的載具回收死魚。留意繫泊纜與網衣勾纏。",
    "lap": "繞網檢查一圈",
    "photo": "拍下網衣破洞",
    "recover": "夾起並提離網底一條死魚",
    "fish": "待回收死魚",
}
CENTER = (24., 0.)
RADIUS = 18.
SEGMENTS = 48
DEPTH = 16.
HOLES = ((23, 3), (24, 6))


def point(angle, radius=RADIUS, depth=0.):
    return (CENTER[0] + radius * math.cos(angle), radius * math.sin(angle), depth)


def layout():
    obstacles = []
    holes = []
    step = math.tau / SEGMENTS
    for i in range(SEGMENTS):
        a, b = i * step, (i + 1) * step
        mid = (a + b) / 2
        for radius, depth, thickness, kind in ((18., 0., .22, "pen_frame"),
                (18.8, 0., .22, "pen_frame"), (18., 16., .12, "pen_sinker"),
                (18.8, -1., .055, "pen_frame")):
            obstacles.append(Cylinder(f"{kind}-{radius}-{i}", point(a, radius, depth),
                                      point(b, radius, depth), thickness, kind))
        if i % 2 == 0:
            obstacles.append(Cylinder(f"pen-post-{i}", point(a, 18.8, 0),
                                      point(a, 18.8, -1), .055, "pen_frame"))
        damaged = next((j for panel, j in HOLES if panel == i), None)
        intervals = [(0., DEPTH)] if damaged is None else [(0., damaged * 2.), (damaged * 2. + 2., DEPTH)]
        if damaged is not None:
            center = point(mid, RADIUS * math.cos(step / 2), damaged * 2 + 1)
            holes.append(dict(id=f"hole-{len(holes)}", pos=center, size=[2.35, 2.], panel=i))
        for j, (top, bottom) in enumerate(intervals):
            center = point(mid, RADIUS * math.cos(step / 2), (top + bottom) / 2)
            panel = Box(f"pen-net-{i}-{j}", center,
                        (RADIUS * math.sin(step / 2), .025, (bottom - top) / 2),
                        math.degrees(mid) + 90, "pen_net")
            panel.snag_hold = (100., 220.)
            obstacles.append(panel)
    # Thin strips form a closed polygonal floor; no individual net strand geometry.
    for i in range(-9, 9):
        y = i * 2 + 1
        half_width = math.sqrt(RADIUS ** 2 - max(abs(y - 1), abs(y + 1)) ** 2)
        if half_width > 0:
            floor = Box(f"pen-floor-{i}", (24., y, DEPTH), (half_width, 1., .025), 0, "pen_net")
            floor.snag_hold = (100., 220.)
            obstacles.append(floor)
    corners = [(0., -24., 3.), (48., -24., 3.), (48., 24., 3.), (0., 24., 3.)]
    for i, corner in enumerate(corners):
        angle = math.atan2(corner[1], corner[0] - 24)
        lines = [(point(angle, 18.8, .2), corner), (corner, corners[(i + 1) % 4]),
                 (corner, (corner[0], corner[1], .1)),
                 (corner, (corner[0] + math.cos(angle) * 10, corner[1] + math.sin(angle) * 10, 24.7))]
        for j, (a, b) in enumerate(lines):
            cable = Cylinder(f"pen-mooring-{i}-{j}", a, b, .065 if j < 3 else .10, "pen_rope")
            cable.snag_hold = (150., 400.)
            obstacles.append(cable)
        obstacles.append(Cylinder(f"pen-buoy-{i}", (corner[0], corner[1], -.25),
                                  (corner[0], corner[1], .25), .45, "pen_buoy"))
        end = lines[-1][1]
        obstacles.append(Box(f"pen-anchor-{i}", end, (.8, .8, .3), 0, "pen_anchor"))
    fish = [dict(id=f"mort-{i}", pos=[x, y, 15.80])
            for i, (x, y) in enumerate(((9., 1.), (13., -3.), (21., 4.), (29., -5.)))]
    return obstacles, dict(center=list(CENTER), radius=RADIUS, net_depth=DEPTH, holes=holes, dead_fish=fish)


def work_objects():
    return {fish["id"]: dict(id=fish["id"], label=STRINGS["fish"], kind="dead_fish",
            pos=np.array(fish["pos"]), vel=np.zeros(3), mass=.8, buoyancy_kg=.75,
            radius=.15, held_by=None) for fish in layout()[1]["dead_fish"]}


def update_objective(scorer, ob, sim):
    pos = sim.vehicle.s.pos
    if ob.kind == "pen_lap":
        delta = pos[:2] - CENTER
        radius = np.linalg.norm(delta)
        if 19.2 < radius < 22.5 and 3 < pos[2] < 14:
            angle = math.atan2(delta[1], delta[0]) % math.tau
            scorer.pen_sectors.add(int(angle / math.tau * 24))
        ob.progress = len(scorer.pen_sectors) / 24
        ob.done = len(scorer.pen_sectors) == 24
    elif ob.kind == "pen_recover":
        held = sim.operations.held
        fish = getattr(sim.world, "work_objects", {}).get(held)
        if fish and fish.get("kind") == "dead_fish" and fish["pos"][2] < 15.3:
            ob.done = True
            ob.progress = 1.


def photo(sim):
    if not str(sim.scenario.key).startswith("aquaculture_pen"):
        return
    from .physics import q_rot
    pos = sim.vehicle.s.pos
    forward = q_rot(sim.vehicle.s.q, np.array([1., 0., 0.]))
    for hole in layout()[1]["holes"]:
        delta = np.array(hole["pos"]) - pos
        distance = np.linalg.norm(delta)
        if .6 < distance < 4 and np.dot(delta / distance, forward) > .94:
            # Reject photos through the far side of the pen.
            if any(sim.world.sdf(pos + delta * t)[0] < -.01 for t in np.linspace(.05, .95, 18)):
                continue
            for objective in sim.scenario.objectives:
                if objective.kind == "pen_photo":
                    objective.done = True
                    objective.progress = 1.
