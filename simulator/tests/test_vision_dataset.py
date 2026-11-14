"""Validate both dataset formats against one known normalized annotation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "vision_dataset", Path(__file__).parents[1] / "tools/vision/make_dataset.py")
DATASET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DATASET)


class DatasetTest(unittest.TestCase):
    def test_formats_and_negative_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = [{"split": "train", "file": "images/train/1.png", "width": 100, "height": 80,
                        "truth": [{"category": "fish", "box": [.1, .2, .4, .5],
                                   "occlusion": .25, "distance_m": 2}]},
                       {"split": "val", "file": "images/val/2.png", "width": 100, "height": 80, "truth": []}]
            DATASET.export_labels(root, records, ["fish"])
            coco = json.loads((root / "train.json").read_text())
            self.assertEqual(coco["annotations"][0]["bbox"], [10, 16, 40, 40])
            self.assertEqual((root / "labels/train/1.txt").read_text(),
                             "0 0.30000000 0.45000000 0.40000000 0.50000000")
            self.assertEqual((root / "labels/val/2.txt").read_text(), "")
            self.assertEqual(json.loads((root / "statistics.json").read_text()), {"fish": 1})
