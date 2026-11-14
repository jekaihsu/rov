"""What the viewer draws must be what the physics hits.

The viewer's structure meshes (viewer/structures.js) are built in Node by tools/scene_manifest.mjs for every
scenario (and the random generator's structure kinds), and each vertex is checked against the Python collision
shapes:

* every underwater vertex of a solid or attached part lies inside the obstacles or at most SCENE_TOLERANCE
  outside them (nothing visible that the vehicle or tether could pass through), on the medium and low tiers;
* every exposed collider surface (underwater, above the seabed, not buried in another shape) has a solid visual
  surface within COVER_TOLERANCE (no invisible collision bulk), on the medium tier (the low tier packs fewer,
  larger armour rocks);
* every structure obstacle is drawn by some part.

The ship-hull test points also compare the Python and JavaScript hull distance functions. Requires Node 18.19+;
skipped (with a message) when ``node`` is not installed.
"""

import json
import math
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import numpy as np

from qysim import scenarios
from qysim import site_dressing
from qysim.world import Box, Cylinder, ShipHull, Wall, World, _half_breadth

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
COVER_TOLERANCE = 0.3          # m from an exposed collision surface to the nearest drawn surface
SURFACE = 0.05                 # m below the waterline: higher vertices are out of the vehicle's reach
RANDOM_SEEDS = range(40)       # two of each random structure kind (jacket, piles, hull, quay)


def world_for(sc):
    world = World(sc.seabed_depth)
    world.obstacles = list(sc.obstacles)
    message = world.as_dict()
    message["scenario"] = {"key": sc.key, "seed": sc.seed}
    return world, message


def scenario_worlds():
    out = {}
    for key in scenarios.LIBRARY:
        out[key] = world_for(scenarios.build(key, 0))
    seen = {}
    for seed in RANDOM_SEEDS:
        sc = scenarios.build("random", seed)
        kind = sc.brief.split("（")[1].split("）")[0]
        if seen.get(kind, 0) < 2:
            seen[kind] = seen.get(kind, 0) + 1
            out[f"random-{seed}"] = world_for(sc)
    return out


def obstacle_distance(obstacles, X):
    """Distance to the nearest structure obstacle (seabed excluded); +inf when there is none."""
    best = np.full(len(X), np.inf)
    for ob in obstacles:
        d, _ = ob.sdf_many(X)
        best = np.minimum(best, d)
    return best


def _orthonormal(axis):
    axis = axis / np.linalg.norm(axis)
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    return axis, u, np.cross(axis, u)


def surface_samples(ob, step=0.25):
    """Points on a collider's surface, about ``step`` apart (walls are covered by their face plane)."""
    if isinstance(ob, Cylinder):
        a, b = np.asarray(ob.p0, float), np.asarray(ob.p1, float)
        axis, u, v = _orthonormal(b - a)
        length = float(np.linalg.norm(b - a))
        n_ang = max(8, int(2 * math.pi * ob.radius / step))
        ang = np.linspace(0, 2 * math.pi, n_ang, endpoint=False)
        ring = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
        ts = np.linspace(0, length, max(2, int(length / step) + 1))
        side = (a + ts[:, None, None] * axis + ob.radius * ring[None]).reshape(-1, 3)
        caps = []
        for end, sign in ((a, -1), (b, 1)):
            for polar in np.linspace(0.2, math.pi / 2, 4):
                caps.append(end + ob.radius * (math.cos(polar) * sign * axis + math.sin(polar) * ring))
        return np.vstack([side, *caps])
    if isinstance(ob, Box):
        h = np.asarray(ob.half, float)
        pts = []
        for axis in range(3):
            others = [k for k in range(3) if k != axis]
            g0 = np.linspace(-h[others[0]], h[others[0]], max(2, int(2 * h[others[0]] / step) + 1))
            g1 = np.linspace(-h[others[1]], h[others[1]], max(2, int(2 * h[others[1]] / step) + 1))
            G0, G1 = np.meshgrid(g0, g1, indexing="ij")
            for sign in (-1, 1):
                local = np.zeros((G0.size, 3))
                local[:, others[0]] = G0.ravel()
                local[:, others[1]] = G1.ravel()
                local[:, axis] = sign * h[axis]
                pts.append(local)
        return np.vstack(pts) @ ob._rot().T + np.asarray(ob.center, float)
    if isinstance(ob, ShipHull):
        hp = ob.hp
        xs = np.arange(-hp["length"] / 2, hp["length"] / 2, step * 2)
        zs = np.arange(0.0, hp["draft"] + 1e-6, step * 2)
        X, Z = np.meshgrid(xs, zs, indexing="ij")
        pts = []
        hb, fwd = _half_breadth(X.ravel(), Z.ravel(), hp)
        ok = (hb > 0) & (X.ravel() <= fwd)
        for side in (-1, 1):
            pts.append(np.column_stack([X.ravel()[ok], side * hb[ok], Z.ravel()[ok]]))
        return ob.world_point(np.vstack(pts))
    return np.zeros((0, 3))


class PointGrid:
    """Occupancy of visual sample points on a fine voxel grid, for vectorised "is anything drawn near" queries.

    A query point counts as covered when an occupied voxel centre lies within ``radius``; with ``cell`` = 0.06 m
    the answer is exact to about 0.05 m.
    """

    def __init__(self, points, radius, cell=0.06):
        self.cell = cell
        pts = np.asarray(points, float).reshape(-1, 3)
        self.keys = np.unique(self._encode(np.floor(pts / cell).astype(np.int64)))
        r = int(math.ceil(radius / cell))
        grid = np.arange(-r, r + 1)
        offsets = np.array(np.meshgrid(grid, grid, grid, indexing="ij")).reshape(3, -1).T
        self.offsets = offsets[np.linalg.norm(offsets, axis=1) * cell <= radius]

    @staticmethod
    def _encode(ijk):
        ijk = ijk + (1 << 19)
        return (ijk[:, 0] << 42) | (ijk[:, 1] << 21) | ijk[:, 2]

    def covered(self, X):
        base = np.floor(np.asarray(X, float) / self.cell).astype(np.int64)
        hit = np.zeros(len(base), bool)
        if not len(self.keys):
            return hit
        for offset in self.offsets:
            keys = self._encode(base + offset)
            i = np.clip(np.searchsorted(self.keys, keys), 0, len(self.keys) - 1)
            hit |= self.keys[i] == keys
        return hit


@unittest.skipUnless(NODE, "node is not installed; the viewer meshes cannot be built")
class SceneConsistencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worlds = scenario_worlds()
        payload = json.dumps({k: m for k, (_, m) in cls.worlds.items()})
        cls.tiers = {}
        for detail in ("medium", "low"):
            run = subprocess.run([NODE, str(ROOT / "tools" / "scene_manifest.mjs")], input=payload, text=True,
                                 capture_output=True, timeout=300, cwd=ROOT,
                                 env={**os.environ, "SCENE_DETAIL": detail})
            if run.returncode:
                raise AssertionError(run.stderr[-3000:])
            manifest = json.loads(run.stdout)
            cls.tolerance = manifest["tolerance"]
            cls.tiers[detail] = manifest["worlds"]
        cls.parts = cls.tiers["medium"]

    def structure_obstacles(self, world):
        return [o for o in world.obstacles if o.kind != "habitat" and o.as_dict()["type"] != "model"]

    def test_visible_surfaces_have_collision(self):
        for (key, (world, _)), detail in [(w, d) for w in self.worlds.items() for d in self.tiers]:
            obstacles = self.structure_obstacles(world)
            for part in self.tiers[detail][key]:
                if part["role"] == "above":
                    continue
                X = np.asarray(part["points"], float).reshape(-1, 3)
                reachable = X[(X[:, 2] > SURFACE) & (X[:, 2] < world.seabed_depth - 0.02)]
                if not len(reachable):
                    continue
                d = obstacle_distance(obstacles, reachable)
                worst = int(np.argmax(d))
                with self.subTest(scenario=key, detail=detail, part=part["colliders"][:2], role=part["role"]):
                    self.assertLessEqual(float(d[worst]), self.tolerance + 1e-3,
                                         f"vertex {reachable[worst].tolist()} stands {d[worst]:.3f} m outside")

    def test_collision_surfaces_are_drawn(self):
        """Every exposed, reachable collider surface point has a solid visual surface within COVER_TOLERANCE."""
        for key, (world, _) in self.worlds.items():
            obstacles = self.structure_obstacles(world)
            solid = [p for part in self.parts[key] if part["role"] == "solid" for p in part["points"]]
            grid = PointGrid(solid, COVER_TOLERANCE)
            for ob in obstacles:
                S = surface_samples(ob)
                S = S[(S[:, 2] > SURFACE) & (S[:, 2] < world.seabed_depth - 0.05)]
                others = [o for o in obstacles if o is not ob]
                if len(S) and others:
                    S = S[obstacle_distance(others, S) > 0.02]          # surfaces buried in other shapes are hidden
                if not len(S):
                    continue
                missing = S[~grid.covered(S)]
                with self.subTest(scenario=key, obstacle=ob.name):
                    self.assertEqual(len(missing), 0, f"{len(missing)}/{len(S)} collision surface points have nothing "
                                     f"drawn within {COVER_TOLERANCE} m, e.g. {missing[:3].round(2).tolist()}")

    def test_every_structure_obstacle_is_drawn(self):
        for key, (world, _) in self.worlds.items():
            drawn = {n for part in self.parts[key] for n in part["colliders"]}
            for ob in self.structure_obstacles(world):
                with self.subTest(scenario=key, obstacle=ob.name):
                    self.assertIn(ob.name, drawn)


class SiteDressingTest(unittest.TestCase):
    def test_inspection_targets_unchanged(self):
        sc = scenarios.build("jacket_inspection", 0)
        targets = [(round(o.face_point[2]), o.label) for o in sc.objectives if o.kind == "inspect"]
        self.assertEqual([t[0] for t in targets], [6, 12, 16, 10])
        anodes = [o for o in sc.obstacles if o.kind == "anode"]
        for depth, label in targets:
            leg = label.split(" 陽極塊")[0]
            with self.subTest(leg=leg):
                self.assertTrue(any(o.name == f"{leg} anode {depth}m" for o in anodes))

    def test_anode_faces_the_inspection_standoff_and_leaves_clearance(self):
        sc = scenarios.build("jacket_inspection", 0)
        world, _ = world_for(sc)
        for objective in (o for o in sc.objectives if o.kind == "inspect"):
            stand = np.asarray(objective.point, float)
            face = np.asarray(objective.face_point, float)
            anode = min((o for o in sc.obstacles if o.kind == "anode"),
                        key=lambda o: o.sdf(face)[0])
            with self.subTest(objective=objective.label):
                self.assertLess(anode.sdf(face)[0], 0.8)          # the anode stands on the inspected leg
                self.assertLess(anode.sdf(stand)[0], np.linalg.norm(stand - face) - 0.6)   # on the side faced
                self.assertGreater(world.sdf(stand)[0], 0.5)       # the stand-off point stays free

    def test_objectives_and_starts_remain_free(self):
        for key in scenarios.LIBRARY:
            sc = scenarios.build(key, 0)
            world, _ = world_for(sc)
            points = [sc.start_pos] + [o.point for o in sc.objectives if o.kind != "untangle"]
            for p in points:
                with self.subTest(scenario=key, point=p):
                    self.assertGreater(world.sdf(np.asarray(p, float))[0], 0.4)

    def test_ship_hull_distance_signs(self):
        hull = ShipHull("h", (50, 0, 0), 0, 80, 18, 8)
        inside = np.array([[50, 0, 4], [80, 0, 3], [15, 0, 1.5]])
        outside = np.array([[50, 10, 4], [50, 0, 9], [92, 0, 2], [14, 0, 5]])
        self.assertTrue(np.all(hull.sdf_many(inside)[0] < 0))
        self.assertTrue(np.all(hull.sdf_many(outside)[0] > 0))
        self.assertAlmostEqual(float(hull.sdf_many(np.array([[50, 10, 4]]))[0][0]), 1.0, places=3)

    def test_mock_sdk_camera_sees_the_same_hull(self):
        import sys
        sys.path.insert(0, str(ROOT / "sdk_mock"))
        from qysea.sdk import _render
        hull = ShipHull("h", (50, 3, 0), 25, 80, 18, 8)
        scene = _render.Scene({"obstacles": [hull.as_dict()], "seabed_depth": 100})
        X = np.random.default_rng(1).uniform([0, -40, -5], [100, 40, 12], (2000, 3))
        np.testing.assert_allclose(scene.prims[0][1](X), hull.sdf_many(X)[0], atol=1e-9)

    def test_propeller_and_rudder_sit_in_the_aperture(self):
        obs = site_dressing.ship_hull("S", (0, 0), 30, 80, 18, 8)
        hull = obs[0]
        for ob in obs[1:]:
            if ob.kind not in ("propeller", "rudder"):
                continue
            centre = np.asarray(ob.p0 if isinstance(ob, Cylinder) else ob.center, float)
            with self.subTest(part=ob.name):
                self.assertGreater(hull.sdf(centre)[0], 0.0)      # in the open water under the counter
                self.assertLess(hull.sdf(centre)[0], 6.0)

    def test_seabed_props_list_snag_sized_items(self):
        for key in ("monopile_current", "harbor_inspection", "jacket_inspection"):
            sc = scenarios.build(key, 0)
            world, message = world_for(sc)
            props = message["seabed_props"]
            names = {o.name for o in world.obstacles}
            with self.subTest(scenario=key):
                self.assertTrue(props)
                for prop in props:
                    self.assertIn(prop["collider"], names)
                    self.assertGreater(prop["size"][2], 0.2)
                    self.assertEqual(len(prop["pos"]), 3)
                    self.assertAlmostEqual(prop["pos"][2], sc.seabed_depth)

    def test_quay_fittings_stay_out_of_the_inspection_lane(self):
        sc = scenarios.build("harbor_inspection", 0)
        lane = np.array([39.0, 0.0, 10.0])
        for ob in sc.obstacles:
            if ob.kind in ("fender", "ladder", "tyre", "debris_block", "debris_pipe"):
                d = ob.sdf(lane)[0]
                with self.subTest(fitting=ob.name):
                    self.assertGreater(d, 3.0)

    def test_habitat_keeps_clear_of_structures(self):
        for key in ("jacket_inspection", "monopile_current", "harbor_inspection", "hull_inspection"):
            sc = scenarios.build(key, 0)
            world = World(sc.seabed_depth)
            world.obstacles = list(sc.obstacles)
            world.configure_habitat(sc.biome, 0, keep_clear=[sc.start_pos])
            structures = [o for o in world.obstacles if o.kind != "habitat"]
            for entity in world.habitat_entities:
                pos = np.asarray(entity["pos"], float) - [0, 0, 0.5]
                d = min(o.sdf(pos)[0] for o in structures)
                with self.subTest(scenario=key, entity=entity["id"]):
                    self.assertGreater(d, 1.5)

    def test_walls_keep_their_type_and_quays_are_marked(self):
        quay = [o for o in scenarios.build("harbor_inspection", 0).obstacles if isinstance(o, Wall)]
        pool = [o for o in scenarios.build("tutorial_pool", 0).obstacles if isinstance(o, Wall)]
        self.assertEqual([o.kind for o in quay], ["quay"])
        self.assertTrue(all(o.kind == "wall" for o in pool))
        self.assertTrue(math.isclose(quay[0].top, -2.0))


if __name__ == "__main__":
    unittest.main()
