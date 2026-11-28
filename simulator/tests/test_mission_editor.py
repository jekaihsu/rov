"""Local course validation and persistence use the same contract as flight."""

import os
import tempfile
import unittest
from unittest.mock import patch
from qysim.campaign.custom import check, courses, save


def course():
    config = dict(
        start_pos=[0, 0, 2],
        spool_pos=[0, 0, 0],
        visibility_m=5,
        tether_length=12,
        current_kn=0,
        current_deg=90,
        pass_score=60,
        targets=[dict(kind="checkpoint", point=[0, 0, 2], radius=1, points=10)],
    )
    return dict(
        id="custom_exam",
        title="Exam",
        scenario="open_water",
        mode="scenario_training",
        category="course",
        order=0,
        nodes=[],
        instructor=config,
        strings={"zh-TW": {}},
        beats=[dict(id="a", next="done", limit=10, hud=[])],
    )


class LocalCourses(unittest.TestCase):
    def test_atomic_replacement_and_steam(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, ROV_MISSION_DIR=folder):
            lesson = course()
            save(lesson)
            lesson["title"] = "Updated"
            save(lesson)
            self.assertEqual(list(courses()), [lesson])
            with patch.dict(os.environ, ROV_BUILD_EDITION="steam"):
                self.assertEqual(list(courses()), [])

    def test_error_fields(self):
        lesson = course()
        lesson["instructor"]["targets"][0]["point"][2] = -1
        with self.assertRaisesRegex(ValueError, r"targets\[0\].point\[2\]"):
            check(lesson)
        lesson = course()
        lesson["id"] = "../x"
        with self.assertRaisesRegex(ValueError, "id"):
            check(lesson)

    def test_photo_requires_a_new_framed_shutter(self):
        from types import SimpleNamespace as NS
        from qysim.campaign.custom import CourseRun

        lesson = course()
        target = lesson["instructor"]["targets"][0]
        target.update(kind="photo", point=[1, 0, 2], radius=2)
        run = CourseRun(lesson)
        sim = NS(
            camera=NS(files=[]),
            vehicle=NS(s=NS(pos=[0, 0, 2])),
            t=1,
            rc=NS(left_ud=1500, left_lr=1500, right_ud=1500, right_lr=1500),
        )
        self.assertFalse(run.step(sim, 0.1))
        sim.camera.files.append(dict(name="1.JPG", pose=dict(n=0, e=0, depth=2, yaw=180)))
        self.assertFalse(run.step(sim, 0.1))
        sim.camera.files.append(dict(name="2.JPG", pose=dict(n=0, e=0, depth=2, yaw=0)))
        self.assertTrue(run.step(sim, 0.1))
        self.assertEqual(run.state()["score"], 100)
