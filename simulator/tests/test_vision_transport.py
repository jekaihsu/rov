"""Simulator detection reports expire and cannot modify authoritative scoring."""
import time
import unittest
from qysim.engine import Simulator
from qysim.server import SimHost


class VisionTransportTest(unittest.TestCase):
    def setUp(self):
        self.host = SimHost(Simulator("open_water", 42))

    def test_optional_report_and_expiry(self):
        self.assertFalse(self.host.handle_rpc({"type": "vision_results"})["available"])
        detections = [{"cls": "coral", "score": .9, "box": [.1, .2, .3, .4]}]
        self.host.handle_viewer({"type": "vision_results", "detections": detections})
        result = self.host.handle_rpc({"type": "vision_results"})
        self.assertEqual(result["detections"], detections)
        self.assertTrue(result["available"])
        self.host.vision_results[self.host.sim] = (time.monotonic()-2, detections)
        self.assertFalse(self.host.handle_rpc({"type": "vision_results"})["available"])

    def test_reject_invalid_coordinates(self):
        for box in ([0, 0, -1, 1], [0, 0, float("nan"), 1], [0, 1]):
            with self.assertRaises(ValueError):
                self.host.handle_viewer({"type": "vision_results", "detections": [{"cls": "coral", "score": 1, "box": box}]})
