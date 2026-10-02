"""Shared habitat contracts: reproducibility, placement, contact and local water."""
import json
import unittest

import numpy as np

from qysim import scenarios
from qysim.world import Box, Cylinder, World
from qysim.tether import Tether, TetherParams


def make_world(key="coral_reef", seed=42):
    sc = scenarios.build(key, seed)
    w = World(sc.seabed_depth)
    w.obstacles = list(sc.obstacles)
    w.current = sc.current
    clear = [sc.start_pos, sc.spool_pos] + [o.point for o in sc.objectives if o.point is not None]
    w.configure_habitat(sc.biome, sc.seed, clear)
    return w, sc


class HabitatTests(unittest.TestCase):
    def test_seed_reproduces_static_world_and_fish(self):
        a, _ = make_world(seed=21)
        b, _ = make_world(seed=21)
        c, _ = make_world(seed=22)
        self.assertEqual(a.as_dict(), b.as_dict())
        self.assertNotEqual(a.as_dict()["habitat"], c.as_dict()["habitat"])
        for _ in range(12):
            a.step(.1)
            b.step(.1)
        self.assertEqual(a.environment_state(), b.environment_state())
        json.dumps(a.environment_state(), allow_nan=False)

    def test_biomes_spawn_requested_life_on_shared_terrain(self):
        for key in ("coral_reef", "seagrass_meadow", "harbor_inspection"):
            w, sc = make_world(key)
            kinds = {e["kind"] for e in w.habitat_entities}
            self.assertIn("seastar", kinds)
            self.assertIn("coral" if sc.biome == "reef" else "seagrass" if sc.biome == "seagrass" else "kelp", kinds)
            for entity in w.habitat_entities:
                p = np.asarray(entity["pos"])
                self.assertAlmostEqual(p[2], w.depth_at(p), delta=.0002)
                self.assertGreater(np.linalg.norm(p[:2] - np.asarray(sc.start_pos)[:2]), 4)
            self.assertGreater(w.sdf(np.array(sc.start_pos))[0], 1)
            for ob in sc.objectives:
                if ob.point is not None:
                    self.assertGreater(w.sdf(np.asarray(ob.point))[0], .4)
            json.dumps(w.as_dict(), allow_nan=False)

    def test_terrain_scalar_and_batch_contacts_agree(self):
        w, _ = make_world()
        points = np.array([[70, 50, w.depth_at([70, 50, 0]) + .3], [80, 50, 2]])
        d, n, _ = w.sdf_many(points, [])
        for i, p in enumerate(points):
            ds, ns, name = w.sdf(p)
            self.assertAlmostEqual(d[i], ds)
            np.testing.assert_allclose(n[i], ns)
            self.assertEqual(name, "seabed")
        self.assertLess(d[0], 0)
        self.assertGreater(d[1], 0)

    def test_spherical_capsule_is_finite_at_centre(self):
        ob = Cylinder("coral", (1, 2, 3), (1, 2, 3), .4)
        d, n = ob.sdf(np.array([1., 2., 3.]))
        db, nb = ob.sdf_many(np.array([[1., 2., 3.], [2., 2., 3.]]))
        self.assertEqual(d, -.4)
        self.assertTrue(np.isfinite(n).all())
        np.testing.assert_allclose(db, [-.4, .6])
        self.assertTrue(np.isfinite(nb).all())

    def test_vectorised_colliders_match_scalar_queries(self):
        w = World(20)
        w.obstacles = [Cylinder("pile",(1,2,0),(1,2,20),.6),
                       Cylinder("coral",(-2,1,18),(-2,1,18),.4,"habitat"),
                       Box("box",(4,-2,16),(1,2,1),25)]
        points = np.random.default_rng(7).uniform([-5,-5,0],[7,5,21],(90,3))
        batch_d,batch_n,batch_i = w.sdf_many(points)
        for i,p in enumerate(points):
            distance,normal,name = w.sdf(p)
            self.assertAlmostEqual(batch_d[i],distance,places=9)
            np.testing.assert_allclose(batch_n[i],normal,atol=1e-8)
            self.assertEqual(name,"seabed" if batch_i[i]<0 else w.obstacles[batch_i[i]].name)

    def test_shared_world_contacts_are_vehicle_specific(self):
        w = World(10)
        q, v = np.array([1., 0, 0, 0]), np.zeros(3)
        for vehicle in ("alpha", "beta"):
            w.vehicle_contact(0, np.array([0., 0., 9.95]), q, v, v, vehicle_id=vehicle)
        self.assertEqual({e.vehicle_id for e in w.events}, {"alpha", "beta"})
        count = len(w.events)
        w.vehicle_contact(.01, np.array([0., 0., 9.95]), q, v, v, vehicle_id="alpha")
        self.assertEqual(len(w.events), count)

    def test_silt_is_local_advects_and_expires(self):
        w = World(20)
        w.current.surface_kn = w.current.mid_kn = w.current.bottom_kn = 1
        w.emit_silt([0, 0, 10], 1, "alpha")
        self.assertGreater(w.silt_at([0, 0, 10]), .9)
        self.assertLess(w.silt_at([50, 0, 10]), .001)
        for _ in range(20):
            w.step(.1)
        self.assertGreater(np.linalg.norm(w.silt_clouds[0]["pos"][:2]), .5)
        for _ in range(400):
            w.step(.1)
        self.assertFalse(w.silt_clouds)

    def test_local_current_is_continuous_and_batch_consistent(self):
        w = World(20)
        w.current.surface_kn = w.current.mid_kn = w.current.bottom_kn = 1
        p = np.array([[0, 0, 5], [40, 10, 5], [40.001, 10, 5]])
        current = w.current.sample_many(p, 20, 12)
        np.testing.assert_allclose(current[1], w.current.sample(p[1], 20, 12))
        self.assertGreater(np.linalg.norm(current[0]-current[1]), .01)
        self.assertLess(np.linalg.norm(current[1]-current[2]), .001)

    def test_fish_remain_finite_above_terrain(self):
        w, _ = make_world()
        for _ in range(35):
            w.step(.1, [{"id": "a", "pos": [20, 0, 9], "thrust": .5}])
        for fish in w.fish_schools:
            self.assertTrue(np.isfinite(fish["pos"]).all())
            self.assertGreater(w.sdf(fish["pos"])[0], 1.8)
            self.assertGreater(fish["pos"][2], 1)

    def test_cached_cable_contacts_track_full_queries(self):
        w = World(12)
        w.obstacles.append(Cylinder("pile",(4,0,0),(4,0,13),.7))
        pos = np.array([6.,1.5,8.])
        q = np.array([1.,0,0,0])
        cached = Tether(w,np.zeros(3),pos,18,TetherParams(contact_cache_m=.01))
        exact = Tether(w,np.zeros(3),pos,18,TetherParams(contact_cache_m=0))
        cached.auto_payout = exact.auto_payout = False
        tensions = []
        for i in range(250):
            moving = pos + np.array([0., i*.001, 0.])
            cached.step(.01,i*.01,moving,q,np.array([0.,.1,0.]))
            exact.step(.01,i*.01,moving,q,np.array([0.,.1,0.]))
            tensions.append(abs(cached.tension_rov-exact.tension_rov))
        self.assertLess(np.max(np.linalg.norm(cached.x-exact.x,axis=1)),.02)
        self.assertLess(np.mean(tensions),1.)
        self.assertEqual(cached.broken,exact.broken)

    def test_compiled_cable_matches_numpy_force_integrator(self):
        from qysim._cable_accel import advance
        if advance is None:
            self.skipTest("optional Numba is not installed")
        w = World(14)
        w.current.surface_kn = w.current.mid_kn = .4
        pos,q = np.array([5.,1.,7.]),np.array([1.,0,0,0])
        compiled = Tether(w,np.zeros(3),pos,16,TetherParams(accelerated=True,contact_cache_m=.01))
        reference = Tether(w,np.zeros(3),pos,16,TetherParams(accelerated=False,contact_cache_m=.01))
        compiled.auto_payout = reference.auto_payout = False
        for i in range(45):
            a = compiled.step(.01,i*.01,pos,q,np.zeros(3))
            b = reference.step(.01,i*.01,pos,q,np.zeros(3))
            np.testing.assert_allclose(a,b,atol=1e-8,rtol=1e-8)
        np.testing.assert_allclose(compiled.x,reference.x,atol=1e-8,rtol=1e-8)
        np.testing.assert_allclose(compiled.v,reference.v,atol=1e-8,rtol=1e-8)


if __name__ == "__main__":
    unittest.main()
