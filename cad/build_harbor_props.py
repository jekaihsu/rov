"""Build original metre-scale harbour inspection props and studio views with blender -b -P cad/build_harbor_props.py.

Shell beds lie on the Blender XY plane, relief +Z. Hardware axes are documented at their builders.
The three meshes have independent topology and share one packed surface atlas per GLB.
"""

import math
import random
import sys
import tempfile
from functools import partial
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'simulator/viewer/models/harbor'
SHOTS = ROOT / 'docs/design/harbor-props-v2'
TAU = math.tau
SHELL, MUSSEL, WEED, SQUIRT, IRON, CORD, RUBBER, MUD = range(8)
PALETTE = [
    (179, 159, 133),
    (33, 42, 57),
    (66, 71, 34),
    (139, 125, 101),
    (52, 34, 25),
    (81, 78, 53),
    (46, 48, 46),
    (99, 88, 62),
]


def noise(rng, w, h, sx, sy):
    field = rng.integers(0, 256, (sy, sx), dtype=np.uint8)
    return np.asarray(Image.fromarray(field).resize((w, h), Image.Resampling.BICUBIC)) / 255.0


def write_maps(folder, prefix, color, height, rough, metal):
    dy, dx = np.gradient(height)
    normals = np.stack((-dx, dy, np.ones_like(dx)), axis=-1)
    normals /= np.linalg.norm(normals, axis=2, keepdims=True)
    orm = np.stack((1 - 0.16 * np.clip(-height, 0, 1), rough, metal), axis=-1)
    for suffix, values in [('color', color), ('normal', (normals + 1) * 127.5), ('orm', orm * 255)]:
        im = Image.fromarray(np.uint8(np.clip(values, 0, 255)))
        # Roughness, corrosion and sediment masks vary on a coarser scale than shell ridges.
        if suffix == 'orm':
            im = im.resize((im.width // 4, im.height // 4), Image.Resampling.LANCZOS)
        elif suffix == 'normal' or prefix == 'surface':
            im = im.resize((im.width // 2, im.height // 2), Image.Resampling.LANCZOS)
        im.save(folder / f'{prefix}-{suffix}.jpg', quality=91, subsampling=0)


def textures(folder):
    rng = np.random.default_rng(1751)
    w, h = 512, 512
    y, x = np.indices((h, w))
    grain = rng.normal(0, 0.12, (h, w))
    cloud = noise(rng, w, h, 32, 32) + grain
    slots = y // 64
    color = np.array(PALETTE)[slots].astype(float)
    oxide = np.clip((cloud - 0.45) * 3, 0, 1)
    color[slots == IRON] += oxide[slots == IRON, None] * [40, 8, -3]
    ridges = np.choose(
        slots,
        [
            np.cos(x * 0.31 + np.sin(y * 0.12)),
            np.cos(y * 0.79 + 3 * np.sin(x * 0.013)),
            np.cos(x * 0.2),
            np.cos(x * 0.14),
            grain,
            np.cos(0.43 * x + 0.74 * y),
            np.maximum(0, np.cos(0.16 * x + abs(y % 32 - 16) * 0.35)) ** 8,
            grain,
        ],
    )
    # Mineral plate boundaries radiate from the aperture. Inner mantle and valve lips are pigmented.
    plates = np.cos(TAU * 6 * x / w + 0.3 * np.sin(y * 0.09))
    boundary = np.maximum(0, plates) ** 16
    shell_mask = slots == SHELL
    color[shell_mask] *= (1 - 0.19 * boundary[shell_mask] - 0.51 * (y[shell_mask] / 64) ** 4)[:, None]
    height = ridges * 0.48 + cloud * 0.54
    height[shell_mask] -= boundary[shell_mask] * 1.4
    height[slots == MUSSEL] *= 0.28
    patina = noise(rng, w, h, 63, 16)
    # Eroded umbo exposes lighter shell. Fine, irregular accretion bands follow the valve margin.
    valve = slots == MUSSEL
    age = (y % 64) / 64
    wear = np.clip((0.23 - age + 0.12 * (patina - 0.5)) * 5, 0, 1)
    bands = np.maximum(0, np.cos(age * 58 + 2.1 * np.sin(x * TAU / w) + cloud * 0.7)) ** 6
    color[valve] += wear[valve, None] * [39, 31, 17] + bands[valve, None] * [8, 6, 7]
    rubber = slots == RUBBER
    silt = np.clip((patina + cloud * 0.36 - 0.79) * 2.7, 0, 1)
    film = silt * (slots >= IRON)
    color += film[..., None] * (np.array([93, 88, 63]) - color) * .65
    height += film * 1.6
    color[rubber] += silt[rubber, None] * [12, 10, 6]
    color[slots == MUD] *= 0.62 + 0.69 * patina[slots == MUD, None]

    color *= (1 + 0.27 * (cloud - 0.5) + 0.05 * ridges)[:, :, None]
    rough = np.choose(slots, [0.83, 0.44, 0.61, 0.52, 0.63, 0.89, 0.81, 0.95]) + 0.08 * (cloud - 0.5)
    write_maps(folder, 'surface', color, height, rough, (slots == IRON) * (0.8 - 0.73 * oxide))

    # The broad sidewall and forged stock have much more surface per UV than net cord.
    # Fine pitting and a low-contrast tide of silt keep both legible under the inspection lamp.
    hardware_color = color.copy()
    grit = noise(np.random.default_rng(45), w, h, 187, 170)
    rubber_tone = 7*grit + 4*patina + 7*silt
    hardware_color[rubber] = np.array([33, 35, 33]) + rubber_tone[rubber, None]
    iron = slots == IRON
    bloom = oxide*patina
    hardware_color[iron] = np.array([40, 26, 20]) + bloom[iron, None]*[49, 22, 8] + 8*grit[iron, None]
    crust = height.copy()
    crust[rubber] = .46*grit[rubber] + .23*silt[rubber]
    crust[iron] = 1.7*bloom[iron] + grit[iron]
    write_maps(folder, 'hardware', hardware_color, crust, np.maximum(rough, .79), iron*(.19-.15*oxide))

    # The unwrap covers 0.942 m by 20 m. Evaluate every animal in metres so valves
    # retain their proportions on different diameter piles and across the UV seam.
    w, h = 256, 2560
    circumference = .3 * math.pi
    fine = noise(rng, w, h, 190, 1100)
    mat = noise(rng, w, h, 15, 105)
    height = (.3 * fine + .7 * mat).astype('f')
    color = np.array([51, 54, 41]) + (32 * mat + 13 * fine)[..., None]
    for _ in range(18000):
        x, y = rng.integers(w), rng.integers(h)
        depth = y * 20 / h - 2
        zone = depth + .22 * math.sin(TAU * x / w) + .45 * (mat[y, x] - .5)
        if zone < -.5 or (zone > 7 and rng.random() > .16 + .38 * mat[y, x]):
            continue
        kind = SHELL if zone < 1.45 else MUSSEL if zone < 4.6 else WEED
        if rng.random() < (.8 if zone > 7 else .045):
            kind = rng.choice([SHELL, MUSSEL, WEED, SQUIRT])
        if kind == WEED and rng.random() < .18:
            kind = SQUIRT
        radius = rng.uniform(.009, .034)
        length = radius * {SHELL: 1, MUSSEL: 2.4, WEED: 4, SQUIRT: 1.5}[kind]
        width = radius * {SHELL: 1, MUSSEL: .82, WEED: .16, SQUIRT: .7}[kind]
        angle = rng.normal(.9 + 3 * mat[y, x], .65)
        dx = np.arange(-math.ceil(length*w/circumference), math.ceil(length*w/circumference)+1)
        dy = np.arange(-math.ceil(length*h/20), math.ceil(length*h/20)+1)
        rows = y + dy
        rows = rows[(rows >= 0) & (rows < h)]
        idx = np.ix_(rows, (x + dx) % w)
        u = dx[None, :] * circumference/w
        v = (rows[:, None] - y) * 20/h
        a = (u*math.cos(angle) + v*math.sin(angle))/length
        b = (v*math.cos(angle) - u*math.sin(angle))/width
        pigment = rng.uniform(.74, 1.2)
        if kind == SHELL:
            theta = np.arctan2(b, a)
            r = np.hypot(a, b) * (1 + .09*np.cos(6*theta))
            plate = np.maximum(0, np.cos(6*theta))**10
            relief = np.clip((1-r)*1.8, 0, 1) - .63*np.clip((.47-r)*7, 0, 1) - .12*plate
            shade = .64 + .47*relief - .13*plate - .25*((r < .4) & (abs(b) < .09))
            tint = [161, 152, 129]
        elif kind == MUSSEL:
            r = np.hypot(a, (b + .14*a*a) / np.clip(.85 + .27*a, .35, 1.2))
            relief = np.sqrt(np.maximum(0, 1-r*r)) * (.77 + .23*a)
            lip = np.exp(-(b/.07)**2) * np.clip(a+.4, 0, 1)
            nacre = np.exp(-((b+.33+.15*a*a)/.17)**2) * np.maximum(0, 1-a*a)
            shade = .43 + .85*relief + .17*np.cos(32*r + 3*a) - .54*lip + .91*nacre
            tint = [33, 41, 52]
        else:
            b = b - (.85*np.sin(3*a+angle) if kind == WEED else .18*a*a)
            r = np.hypot(a, b)
            relief = np.sqrt(np.maximum(0, 1-r*r))
            pore = np.exp(-30*((a-.63)**2 + b*b))
            shade = .62 + .44*relief - .46*pore
            tint = [64, 75, 42] if kind == WEED else [132, 118, 85]
        edge = np.clip((1-r)*7, 0, 1)
        # Local contact shadow under the overlapping shell margin, baked at the same scale as the valve.
        shadow = np.exp(-((r-1)/.19)**2) * np.clip(.45+.55*b, .12, 1)
        color[idx] *= (1-.46*shadow[..., None])
        color[idx] += edge[..., None] * (np.asarray(tint)*pigment*shade[..., None] - color[idx])
        height[idx] += edge * (radius*200*relief + .23*height[idx] - height[idx])
    rough = np.clip(.89 - .055*height + .10*(fine-.5), .37, .95)
    write_maps(OUT, 'pile', color, height, rough, np.zeros_like(height))
    relief_map = Image.fromarray(np.uint8(np.clip(height*32, 0, 255)))
    relief_map.resize((96, 768), Image.Resampling.BOX).save(OUT / 'pile-height.jpg', quality=93)


class Surface:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.uvs = []
        self.weights = []

    def rings(self, rings, slot, weighted=False):
        """Loft ordered cross sections. UV seams use face corners, so vertex normals stay continuous."""
        base = len(self.verts)
        n = len(rings[0])
        for j, ring in enumerate(rings):
            self.verts.extend(ring)
            self.weights.extend([j / (len(rings) - 1) if weighted else 0] * n)
            if not j:
                continue
            for i in range(n):
                k = (i + 1) % n
                self.faces.append(tuple(base + a * n + b for a, b in [(j - 1, i), (j - 1, k), (j, k), (j, i)]))
                self.uvs.extend(
                    [
                        (u, 1 - (slot + 0.04 + 0.92 * v / (len(rings) - 1)) / 8)
                        for u, v in [(i / n, j - 1), ((i + 1) / n, j - 1), ((i + 1) / n, j), (i / n, j)]
                    ]
                )

    def tube(self, path, radius, sides, slot, weighted=False):
        path = list(map(Vector, path))
        rings = []
        ref = None
        for j, p in enumerate(path):
            tangent = (path[min(j + 1, len(path) - 1)] - path[max(0, j - 1)]).normalized()
            if ref is None:
                ref = tangent.orthogonal()
            ref = (ref - tangent * ref.dot(tangent)).normalized()
            side = tangent.cross(ref)
            r = radius[j] if isinstance(radius, list) else radius
            rings.append([p + r * (ref * math.cos(a) + side * math.sin(a)) for a in angles(sides)])
        self.rings(rings, slot, weighted)

    def object(self, name, material, weighted):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.update()
        uv = mesh.uv_layers.new()
        uv.data.foreach_set('uv', np.asarray(self.uvs, dtype='f').ravel())
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        if weighted:
            attr = mesh.color_attributes.new(name='Sway', type='FLOAT_COLOR', domain='POINT')
            attr.data.foreach_set('color', np.array([(w, 1, 1, 1) for w in self.weights], dtype='f').ravel())
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        mesh.materials.append(material)
        return obj


def angles(n):
    return [TAU * i / n for i in range(n)]


def shell(m, x, y, z, r, n, phase):
    rings = []
    for scale, h in [(1, 0), (0.73, 0.54), (0.58, 0.87), (0.40, 0.82), (0.32, 0.18)]:
        ring = []
        for a in angles(n):
            flute = 1 + 0.12 * math.cos(5 * a + phase) + 0.07 * math.sin(3 * a)
            ring.append(
                (
                    x + r * (scale * flute * math.cos(a) + 0.17 * h),
                    y + r * scale * 0.85 * flute * math.sin(a),
                    z + r * h * (1 + 0.14 * math.sin(4 * a + phase)),
                )
            )
        rings.append(ring)
    m.rings(rings, SHELL)
    # The paired opercular plates sit recessed under the asymmetric rim.
    for side in (-1, 1):
        lid = [(x+r*(.10+u), y+r*side*v, z+r*h) for u,v,h in
               [(-.30,.02,.62), (.29,.025,.66), (.14,.24,.58), (-.15,.23,.56)]]
        ridge = (x+.1*r, y+side*.1*r, z+.7*r)
        m.rings([lid, [tuple(.03*p+.97*q for p,q in zip(vertex,ridge)) for vertex in lid]], SHELL)


def bed(m, kind, size, lod, rng):
    n = [9, 7, 5][lod]
    count = ([38, 15, 6] if kind == 'barnacles' else [26, 12, 5])[lod]
    for i in range(count):
        # Satellite shells gather around a handful of holdfasts, leaving irregular gaps.
        a = i % 5 * 2.4
        x = (0.13 * math.cos(a) + rng.uniform(-0.105, 0.105)) * size
        y = (0.13 * math.sin(a) + rng.uniform(-0.105, 0.105)) * size
        r = rng.uniform(0.055, 0.105) * min(size, 0.64)
        if kind == 'barnacles':
            shell(m, x, y, 0, r, n, rng.random() * TAU)
            continue
        bearing = a + rng.uniform(-0.8, 0.8)
        for k in range(3 if lod == 0 else 1):
            twist = bearing + rng.uniform(-1.4, 1.4)
            m.tube([(x,y,.006), (x+r*math.cos(twist), y+r*math.sin(twist),.003)],
                   .0018, 3, CORD)
        # Two opposing valves meet on a narrow dorsal ridge, with a slight gape near the broad end.
        for side in [-1, 1]:
            rings = []
            for t, width in [(0, 0.07), (0.18, 0.44), (0.53, 0.83), (0.78, 1), (0.93, 0.72), (1, 0.07)]:
                ring = []
                steps = [6, 5, 4][lod]
                for j in range(steps):
                    p = math.pi * j / (steps - 1)
                    bow = width * math.sin(p)
                    lateral = r * (side * (0.012 + .058*t*t + 0.46 * bow) + 0.17 * t**2)
                    along = r * ((t - 0.5) * 2.3 + 0.23 * width * math.cos(p))
                    h = 0.035 + width * (0.43 + 0.41 * math.cos(p)) + 0.10 * t
                    ring.append(
                        (
                            x + along * math.cos(bearing) - lateral * math.sin(bearing),
                            y + along * math.sin(bearing) + lateral * math.cos(bearing),
                            r * (h + .28*t + .21*(i%3)),
                        )
                    )
                rings.append(ring[::-1] if side > 0 else ring)
            m.rings(rings, MUSSEL)


def growth(m, lod, rng):
    for i in range([36, 20, 8][lod]):
        a = rng.random() * TAU
        x, y = rng.uniform(-0.10, 0.10), rng.uniform(-0.09, 0.09)
        steps = [8, 6, 4][lod]
        length = rng.uniform(0.14, 0.37)
        path = []
        for j in range(steps + 1):
            t = j / steps
            bend = (0.23 * t + 0.49 * math.sin(t * 5 + a) * t) * length
            path.append(
                (
                    x + length * t * t * 0.58 + bend * math.cos(a),
                    y + bend * math.sin(a) + length * t * 0.61,
                    length * (t - 0.68 * t * t),
                )
            )
        m.tube(path, [0.0022 * (1 - 0.88 * j / steps) for j in range(steps + 1)], 3, WEED, True)
    for i in range([7, 4, 2][lod]):
        x, y = rng.uniform(-0.09, 0.09), rng.uniform(-0.09, 0.09)
        h = rng.uniform(0.056, 0.12)
        bearing = rng.random() * TAU
        sides = [12, 9, 6][lod]
        # One irregular, leaning tunic tapers to its oral siphon.
        rings = []
        for t, r in [(0,.17), (.15,.33), (.39,.36), (.68,.25), (.86,.14), (.97,.105), (.90,.059)]:
            ring = []
            for a in angles(sides):
                rib = r * (1 + .10*math.sin(3*a+bearing) + .04*math.sin(6*a+t))
                ring.append((x+h*(rib*math.cos(a)+.4*t*t), y+h*rib*.71*math.sin(a),
                             h*(t+.09*r*math.cos(a))))
            rings.append(ring)
        m.rings(rings, SQUIRT, True)
        # A shorter atrial siphon emerges obliquely from the same body.
        rings = [[(x+h*(offset+r*math.cos(a)), y+h*r*math.sin(a), h*(t-.35*r*math.cos(a)))
                  for a in angles(sides)] for offset,t,r in [(.25,.51,.15), (.36,.65,.12),
                                                             (.42,.74,.09), (.40,.70,.048)]]
        m.rings(rings, SQUIRT, True)


def chain(m, lod, rng, terminal=True):
    # Four interlocking oval links along Z; the shackle replaces the first link.
    n, sides = [(24, 8), (16, 5), (9, 3)][lod]
    for i in range(4):
        path = []
        sweep = [TAU * j / n for j in range(n + 1)] if i or not terminal else [math.pi * (-0.30 + 1.60 * j / n) for j in range(n + 1)]
        for a in sweep:
            x = 0.058 * math.cos(a)
            z = i * 0.15 + 0.09 + 0.104 * math.sin(a)
            path.append((x if i % 2 == 0 else 0, x if i % 2 else 0, z))
        stock = .014 if i or not terminal else .018
        gauges = [stock*(1+.048*math.sin(3*a+i)+.039*math.cos(7*a-i)) for a in sweep]
        m.tube(path, gauges, sides, IRON)
        if not i and terminal:
            z = path[0][2]
            for sign in (-1, 1):
                # Forged bosses carry the transverse pin at both ends of the bow.
                m.tube([(sign*d, 0, z) for d in (.042,.053,.066)], [.019,.025,.023], sides, IRON)
            m.tube(
                [(-0.076, 0, z), (0.059, 0, z), (0.065, 0, z), (0.077, 0, z)], [0.015, 0.015, 0.023, 0.023], sides, IRON
            )
    for i in range([5, 2, 1][lod]):
        shell(m, 0.049, 0.002, 0.08 + 0.012 * i, 0.009, 5, i)


def tyre(m, lod, rng):
    section = [
        (0.22, -0.09),
        (0.223, 0.06),
        (0.24, 0.099),
        (0.32, 0.118),
        (0.387, 0.108),
        (0.437, 0.082),
        (0.45, 0.061),
        (0.45, 0.029),
        (0.442, 0.024),
        (0.45, 0.018),
        (0.45, -0.018),
        (0.442, -0.024),
        (0.45, -0.03),
        (0.445, -0.068),
        (0.42, -0.092),
        (0.34, -0.115),
        (0.22, -0.09),
    ]
    if lod:
        section = [section[i] for i in [0, 1, 3, 5, 6, 13, 15, 16]]
    rings = [[(r * math.cos(a), r * math.sin(a), h) for a in angles([52, 32, 16][lod])] for r, h in section[::-1]]
    # A continuous UV along the sidewall avoids repeating the same silt at every shoulder.
    start = len(m.uvs)
    m.rings(rings, RUBBER)
    m.uvs[start:] = [(u*4, v) for u,v in m.uvs[start:]]
    if lod < 2:
        for r,z in [(.25,.104), (.265,.109), (.376,.108)]:
            path = [(r*math.cos(a), r*math.sin(a), z) for a in angles(48) + [0]]
            m.tube(path, .0025, 3, RUBBER)
    # Paired angled shoulder cuts repeat around the circumference.
    for i in range([46, 22, 8][lod]):
        a = TAU * i / [46, 22, 8][lod]
        for sign in [-1, 1]:
            path = [
                (0.45 * math.cos(a + t * 0.044), 0.45 * math.sin(a + t * 0.044), sign * (0.013 + t * 0.049))
                for t in [0, 1]
            ]
            m.tube(path, 0.004, 3, RUBBER)
    for i in range([20, 8, 2][lod]):
        a = rng.uniform(0.3, 2.1)
        r = rng.uniform(0.29, 0.39)
        shell(m, r * math.cos(a), r * math.sin(a), 0.11, rng.uniform(0.009, 0.023), [7, 5, 4][lod], a)


def rope(m, lod, rng):
    for i in range(3):
        for k in range([4, 2, 1][lod]):
            path = []
            steps = [29, 20, 13][lod]
            split = rng.uniform(0.58, 0.77)
            end = rng.uniform(0.80, 1)
            for j in range(steps + 1):
                t = j / steps * end
                f = max(t - split, 0)
                a = i * TAU / 3 + 14 * t
                b = k * TAU / 4 + 33 * t
                path.append(
                    (
                        (0.017 + f * 0.19) * math.cos(a) + (0.008 + f * 0.08) * math.cos(b),
                        (0.017 + f * 0.14) * math.sin(a) + (0.008 + f * 0.06) * math.sin(b),
                        0.74 * t,
                    )
                )
            m.tube(path, [0.012 * (1 - 0.82 * (j / steps) ** 5) for j in range(steps + 1)], [4, 4, 3][lod], CORD)


def trap(m, lod, rng):
    n = [22, 16, 8][lod]
    for z, r in [(0, 0.37), (0.29, 0.32)]:
        m.tube([(r * math.cos(a), r * math.sin(a), z) for a in angles(n) + [0]], 0.009, 4, IRON)
    count = [22, 12, 4][lod]
    for i in range(count):
        a = TAU * i / count
        for direction in [-1, 1]:
            path = []
            for j in range([5, 3, 2][lod] + 1):
                t = j / [5, 3, 2][lod]
                b = a + direction * t * 0.82
                r = 0.37 - 0.05 * t - .053 * math.sin(math.pi*t) * (.55+.45*math.sin(3*b))
                path.append((r * math.cos(b), r * math.sin(b), 0.29 * t))
            m.tube(path, 0.003, 3, CORD)
        m.tube(
            [(0.32 * math.cos(a), 0.32 * math.sin(a), 0.29), (0.105 * math.cos(a), 0.105 * math.sin(a), 0.17)],
            0.003,
            3,
            CORD,
        )
        if i % max(1, count // (2 if lod == 2 else 4)) == 0:
            m.tube(
                [(0.37 * math.cos(a), 0.37 * math.sin(a), 0), (0.32 * math.cos(a), 0.32 * math.sin(a), 0.29)],
                0.008,
                4,
                IRON,
            )
    m.tube([(0.105 * math.cos(a), 0.105 * math.sin(a), 0.17) for a in angles(n) + [0]], 0.005, 3, CORD)
    for j in range(1, [12, 7, 3][lod]):
        off = 0.37 * (2 * j / [12, 7, 3][lod] - 1)
        extent = math.sqrt(0.37**2 - off**2)
        m.tube([(-extent, off, 0.003), (extent, off, 0.003)], 0.003, 3, CORD)
        m.tube([(off, -extent, 0.006), (off, extent, 0.006)], 0.003, 3, CORD)
    m.tube([(-0.32, 0, 0.29), (-0.04, 0.01, 0.48), (0.32, 0, 0.29)], 0.007, 4, CORD)
    m.tube([(-0.04, 0.01, 0.48), (-0.07, 0.04, 0.66), (-0.05, 0.08, 0.89)], 0.006, 4, CORD)
    m.tube(
        [(-0.05, 0.08, z) for z in [0.88, 0.89, 0.93, 0.97, 0.98]], [0.009, 0.032, 0.041, 0.026, 0.008], n // 2, SQUIRT
    )
    for i in range([8, 4, 1][lod]):
        shell(m, 0.32 * math.cos(i * 0.17), 0.32 * math.sin(i * 0.17), 0.29, 0.014, 5, i)


def atlas(folder, prefix='surface'):
    mat = bpy.data.materials.new('Harbour surfaces')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    link = mat.node_tree.links.new
    bsdf = nodes.get('Principled BSDF')
    for suffix in ['color', 'normal', 'orm']:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(folder / f'{prefix}-{suffix}.jpg'))
        if suffix == 'color':
            link(tex.outputs[0], bsdf.inputs['Base Color'])
        else:
            tex.image.colorspace_settings.name = 'Non-Color'
        if suffix == 'normal':
            bump = nodes.new('ShaderNodeNormalMap')
            link(tex.outputs[0], bump.inputs['Color'])
            link(bump.outputs[0], bsdf.inputs['Normal'])
        if suffix == 'orm':
            split = nodes.new('ShaderNodeSeparateColor')
            link(tex.outputs[0], split.inputs[0])
            link(split.outputs['Green'], bsdf.inputs['Roughness'])
            link(split.outputs['Blue'], bsdf.inputs['Metallic'])
            group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
            group.interface.new_socket(name='Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
            output = nodes.new('ShaderNodeGroup')
            output.node_tree = group
            link(split.outputs['Red'], output.inputs['Occlusion'])
    return mat


def photograph(name, obj):
    scene = bpy.context.scene
    coords = [Vector(c) for c in obj.bound_box]
    center = (coords[0] + coords[6]) * 0.5
    size = max(obj.dimensions)
    backdrop = min(c.z for c in coords) - size * 0.015
    bpy.ops.mesh.primitive_plane_add(size=size * 200, location=(0, 0, backdrop))
    plane = bpy.context.object
    grey = bpy.data.materials.new('Slate')
    grey.diffuse_color = (0.077, 0.092, 0.105, 1)
    plane.data.materials.append(grey)
    bpy.ops.object.camera_add(location=center + Vector((0.85, -1.55, 1.18)) * size)
    cam = bpy.context.object
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO'
    inverse = cam.rotation_euler.to_matrix().transposed()
    projected = [inverse @ (v.co - center) for v in obj.data.vertices]
    cam.data.ortho_scale = 1.16 * max(
        (max(v[i] for v in projected) - min(v[i] for v in projected)) * aspect for i, aspect in [(0, 1), (1, 16 / 9)]
    )
    offset = Vector([(max(v[i] for v in projected) + min(v[i] for v in projected)) * 0.5 for i in range(3)])
    cam.location += cam.rotation_euler.to_matrix() @ offset
    scene.camera = cam
    for pos, power, span in [((-1, -1, 2), 115, 1.1), ((0.5, 1, 1.5), 75, 0.85)]:
        bpy.ops.object.light_add(type='AREA', location=center + Vector(pos) * size)
        light = bpy.context.object
        light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
        light.data.energy = power * size**2
        light.data.shape = 'DISK'
        light.data.size = span * size
    scene.world.color = (0.36, 0.36, 0.36)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 86
    scene.render.filepath = str(SHOTS / f'{name}.jpg')
    bpy.ops.render.render(write_still=True)


def pile_samples():
    """Four one-metre coupons from the same cylindrical UV layout as the instanced game piles."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.world = bpy.data.worlds.new('Studio')
    coating = atlas(OUT, 'pile')
    samples = Surface()
    sides = 64
    depths = [0.4, 2.7, 5.6, 11]
    for i, depth in enumerate(depths):
        cx = (i - 1.5) * 0.82
        rings = [[(cx + 0.3 * math.cos(a), 0.3 * math.sin(a), z) for a in angles(sides)] for z in [0, 1]]
        samples.rings(rings, SHELL)
        # Wrap the height interval about the selected centre depth. V=0.9 is the waterline.
        samples.uvs[-4 * sides :] = [
            (2*u, (18 - depth + z - 0.5) / 20)
            for j in range(sides)
            for u, z in [(j / sides, 0), ((j + 1) / sides, 0), ((j + 1) / sides, 1), (j / sides, 1)]
        ]
    obj = samples.object('Concrete pile coupons', coating, False)
    photograph('pile-bands', obj)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    builders = {
        'filaments-ascidians': growth,
        'shackle-chain': chain,
        'chain-links': partial(chain, terminal=False),
        'discarded-tyre': tyre,
        'parted-hawser': rope,
        'crab-pot': trap,
    }
    for kind in ['barnacles', 'mussels']:
        for cm in [30, 60, 100]:
            builders[f'{kind}-{cm}'] = partial(bed, kind=kind, size=cm / 100)
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        textures(folder)
        selected = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
        for name, builder in builders.items():
            if selected and name not in selected:
                continue
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.context.scene.world = bpy.data.worlds.new('Studio')
            stock = name in ('shackle-chain', 'chain-links', 'discarded-tyre')
            mat = atlas(folder, 'hardware' if stock else 'surface')
            levels = []
            for lod, limit in enumerate([3000, 1000, 300]):
                m = Surface()
                builder(m, lod=lod, rng=random.Random(name))
                if builder == growth:
                    m.verts = [(x, y, z * 0.70) for x, y, z in m.verts]
                obj = m.object(f'LOD{lod}', mat, builder == growth)
                count = 2 * len(m.faces)
                if count > limit:
                    modifier = obj.modifiers.new('Triangle budget', 'DECIMATE')
                    modifier.ratio = (limit - 2) / count
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_apply(modifier=modifier.name)
                obj.data.calc_loop_triangles()
                if len(obj.data.loop_triangles) > limit:
                    raise ValueError(f'{name} LOD{lod} exceeds {limit} triangles')
                levels.append(obj)
            bpy.ops.export_scene.gltf(
                filepath=str(OUT / f'{name}.glb'),
                export_image_format='JPEG',
                export_vertex_color='ACTIVE',
                export_all_vertex_colors=True,
            )
            for obj in levels[1:]:
                obj.hide_render = True
            if (OUT / f'{name}.glb').stat().st_size > 1_000_000:
                raise ValueError(f'{name} exceeds the storage budget')
            photograph(name, levels[0])
    if not selected:
        pile_samples()


if __name__ == '__main__':
    build()
