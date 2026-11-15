"""Wind foundation geometry and mission access regression checks."""
import unittest
import numpy as np
from qysim.scenarios import jacket_inspection


class WindJacketTests(unittest.TestCase):
    def test_rigid_fittings_and_access(self):
        scene = jacket_inspection()
        names = [ob.name for ob in scene.obstacles]
        self.assertEqual(len(names), len(set(names)))
        for feature in ('grillage', 'stair', 'landing column', 'ladder rung', 'grout sleeve', 'J section'):
            self.assertTrue(any(feature in name for name in names), feature)
        for objective in scene.objectives:
            distance = min(ob.sdf_many(np.array([objective.point]))[0][0] for ob in scene.obstacles)
            self.assertGreaterEqual(distance, 0.4)

    def test_complete_cross_bracing(self):
        scene = jacket_inspection()
        diagonals = [ob for ob in scene.obstacles if ob.kind == 'brace' and ob.p0[2] != ob.p1[2]]
        self.assertEqual(len(diagonals), 32)
        self.assertEqual(len([ob for ob in scene.obstacles if ob.kind == 'jacket_leg']), 4)

    def test_scour_is_shared_terrain(self):
        from qysim.world import World
        scene = jacket_inspection()
        world = World(scene.seabed_depth)
        world.obstacles = list(scene.obstacles)
        world.configure_habitat('offshore', 42)
        terrain = world.terrain
        self.assertEqual(terrain.spacing, 1.5)
        self.assertGreater(terrain.relief, 0)
        self.assertLess(float(terrain.depths.min()), scene.seabed_depth - 0.3)
        self.assertLessEqual(float(terrain.depths.max()), scene.seabed_depth)
        exported = np.array(terrain.as_dict()['depths'])
        np.testing.assert_allclose(exported, terrain.depths, atol=0.00005)

    def test_dry_fittings_do_not_shed_water_wakes(self):
        from qysim.flow import StructureFlow
        scene = jacket_inspection()
        dry = [ob for ob in scene.obstacles if
               (hasattr(ob, 'p0') and max(ob.p0[2], ob.p1[2]) + ob.radius < 0) or
               (hasattr(ob, 'center') and ob.center[2] + ob.half[2] < 0)]
        self.assertGreater(len(dry), 100)
        fittings = [ob for ob in dry if ob.kind in ('wind_dry', 'wind_paint', 'wind_tower')]
        self.assertGreater(len(fittings), 100)
        self.assertTrue(StructureFlow(fittings).empty)

    def test_sonar_bounds_preserve_exact_nearest_surface(self):
        from qysim.world import Box, Cylinder, ShipHull, World
        world = World(32)
        world.obstacles = [Cylinder('leg', (2, 0, -4), (4, 0, 32), 0.7),
                           Box('dry deck', (0, 0, -10), (7, 7, 0.2), 30),
                           Box('submerged', (8, 8, 10), (2, 3, 1), 45),
                           ShipHull('hull', (35, 0, 0), 20, 24, 8, 5)]
        rng = np.random.default_rng(1101)
        for centre in ((0, 0, 10), (0, 0, -10), (8, 8, 10), (20, 20, 31), (30, 12, 2)):
            points = np.array(centre) + rng.uniform(-1, 1, (17, 3))
            expected = 32 - points[:, 2]
            index = np.full(len(points), -1)
            normals = np.tile([0., 0., -1.], (len(points), 1))
            for i, ob in enumerate(world.obstacles):
                distance, normal = ob.sdf_many(points)
                closer = distance < expected
                expected[closer] = distance[closer]
                normals[closer] = normal[closer]
                index[closer] = i
            actual, actual_normals, actual_index = world.sdf_many(points)
            np.testing.assert_allclose(actual, expected, atol=1e-12)
            np.testing.assert_allclose(actual_normals, normals, atol=1e-12)
            np.testing.assert_array_equal(actual_index, index)
