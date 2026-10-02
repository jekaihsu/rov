"""Shared artwork validation, bounded retention and room isolation."""
import unittest
from unittest.mock import patch

from qysim.engine import Simulator
from qysim.room import Room
from tests.test_operations import operator


def paint(**kwargs):
    return dict(action="paint", pos=[0, 0, 8.5], normal=[0, 0, -1],
                radius=.12, color="#f0c75e", **kwargs)


class TestPaint(unittest.TestCase):
    def test_rejects_invalid_values_atomically(self):
        sim = operator()
        for key, value in (("pos", [0, 0, float("nan")]), ("pos", [0, 0, -1]),
                           ("pos", [5, 0, 8]), ("normal", [0, 0, 0]),
                           ("normal", [0, 0, 2]), ("normal", [float("inf"), 0, 1]),
                           ("radius", float("nan")), ("radius", .301),
                           ("radius", .029), ("color", "red"), ("color", [])):
            msg = paint()
            msg[key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(sim.operations.command(msg)["ok"])
                self.assertEqual(sim.world.paint_marks, [])
                self.assertEqual(sim.world.paint_serial, 0)

    def test_per_vehicle_wall_clock_rate_and_bounded_retention(self):
        a = operator()
        b = operator(a.world, "beta")
        with patch("qysim.operations.time.monotonic", return_value=100.):
            self.assertTrue(a.operations.command(paint())["ok"])
            self.assertFalse(a.operations.command(paint())["ok"])
            self.assertTrue(b.operations.command(paint())["ok"])
        for i in range(305):
            with patch("qysim.operations.time.monotonic", return_value=101. + i * .101):
                self.assertTrue(a.operations.command(paint())["ok"])
        self.assertEqual(len(a.world.paint_marks), 300)
        self.assertEqual(a.world.paint_marks[0]["id"], "paint-8")
        self.assertEqual(a.world.paint_marks[-1]["owner_id"], "alpha")
        self.assertEqual(operator().world.paint_marks, [])

    def test_appearance_is_per_vehicle_and_validated(self):
        a = operator()
        b = operator(a.world, "beta")
        self.assertTrue(a.operations.command({"action": "appearance", "sticker": "dive"})["ok"])
        self.assertFalse(a.operations.command({"action": "appearance", "sticker": "unknown"})["ok"])
        self.assertEqual(a.appearance, {"sticker": "dive"})
        self.assertFalse(hasattr(b, "appearance"))

    def test_room_snapshot_peer_appearance_and_scene_reset(self):
        # No cable simulation is required to exercise room state publication.
        with patch("qysim.tether.Tether.settle"):
            room = Room(Simulator("open_water", 42), "art")
            a = room.join("A")
            b = room.join("B")
            sim = room.vehicles[a.vehicle_id]
            msg = paint()
            msg["pos"] = sim.vehicle.s.pos.tolist()
            self.assertTrue(sim.operations.command(msg)["ok"])
            sim.operations.command({"action": "appearance", "sticker": "hazard"})
            sa, sb = room.state(a), room.state(b)
            self.assertEqual(sa["paint_marks"], sb["paint_marks"])
            self.assertEqual(len(sb["paint_marks"]), 1)
            peer = next(v for v in sb["vehicles"] if v["id"] == a.vehicle_id)
            self.assertEqual(peer["appearance"], {"sticker": "hazard"})
            room.reset()
            self.assertEqual(room.state(a)["paint_marks"], [])
            self.assertEqual(sa["paint_marks"][0]["id"], "paint-1")


if __name__ == "__main__":
    unittest.main()
