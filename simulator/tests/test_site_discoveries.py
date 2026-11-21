"""Host placement, visibility validation and collection identity for the field guide."""
import math
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.physics import q_from_euler, q_rot
from qysim.scenarios import LIBRARY


class SiteDiscoveriesTest(unittest.TestCase):
    def test_sites_supply_distinct_surface_roots_within_tether_reach(self):
        for key in (*LIBRARY, "random"):
            with self.subTest(key=key):
                sim = Simulator(key, seed=1)
                world = sim.world
                entries = world.discoveries
                if key == "tutorial_pool":
                    self.assertFalse(entries)
                    continue
                self.assertEqual(len(entries), 18)
                self.assertEqual(len({m["id"] for m in entries}), len(entries))
                for entry in entries:
                    pos = np.asarray(entry["pos"])
                    self.assertLess(abs(world.sdf(pos)[0]), .03, entry)
                    self.assertAlmostEqual(np.linalg.norm(entry["normal"]), 1., places=4)
                    self.assertLess(np.linalg.norm(pos - sim.scenario.spool_pos), sim.scenario.tether_length)
                    self.assertEqual(len(entry["normal"]), 3)

    def test_onboard_detail_is_confirmed_in_training_at_actual_surface(self):
        sim = Simulator("incident_jacket", seed=17)
        marker = sim.world.discoveries[0]
        normal = np.asarray(marker["normal"])
        target = np.asarray(marker["pos"])
        pitch = math.asin(normal[2])
        yaw = math.atan2(-normal[1], -normal[0])
        q = q_from_euler(0., pitch, yaw)
        lens = target + 1.3 * normal
        sim.vehicle.s.q = q
        sim.vehicle.s.pos = lens - q_rot(q, np.asarray(sim.vehicle.definition.camera_body))
        msg = dict(action="observation_photo", entity_id=marker["id"], photo_id="detail-test", view="onboard",
                   visible=True, coverage=.02, camera=dict(pos=lens.tolist(), q=q.tolist(), fov=70., aspect=1.6))
        result = sim.operations.command(msg)["observation"]
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["entry"]["entity_id"], marker["id"])
        self.assertEqual(result["entry"]["category"], marker["kind"])
        self.assertEqual(result["entry"]["world_seed"], 17)
        self.assertEqual(sim.operations.command(msg)["observation"], result)
        distant = dict(msg, photo_id="too-far", camera={**msg["camera"], "pos": (lens + 25 * normal).tolist()})
        self.assertFalse(sim.operations.command(distant)["observation"]["accepted"])
        self.assertFalse(sim.operations.command({**msg, "action": "expedition_start"})["ok"])
