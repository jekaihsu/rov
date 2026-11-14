"""Large A2 wreck debris must be represented in the rebuilt collision field."""

import unittest

from qysim import scenarios


class TestWreckDetailCollision(unittest.TestCase):
    def test_hatches_and_winch_have_collision_surfaces(self):
        wreck = scenarios.build("korean_castle").obstacles[0]
        # Local Blender coordinates at the authored hatch tops and winch flange.
        surfaces = [(32.0, 19.0, 0.22), (81.0, -19.0, 0.22), (94.75, 19.0, 1.38)]
        for point in surfaces:
            with self.subTest(point=point):
                distance, _ = wreck.sdf(wreck.world_point(point))
                # One existing field cell: do not require sub-grid contact precision.
                self.assertLess(distance, 0.3)


if __name__ == "__main__":
    unittest.main()
