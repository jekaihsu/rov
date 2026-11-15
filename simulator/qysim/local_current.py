"""Compact regional currents in NED m/s; illustrative, not CFD."""
import numpy as np


def sample_regions(points, regions):
    points = np.atleast_2d(np.asarray(points, float))
    result = np.zeros_like(points)
    for region in regions:
        center = np.asarray(region['center'], float)
        velocity = np.asarray(region['velocity'], float)
        radius = float(region['radius_m'])
        if (center.shape != (3,) or velocity.shape != (3,) or not np.isfinite(radius)
                or radius <= 0 or not np.all(np.isfinite(center)) or not np.all(np.isfinite(velocity))):
            raise ValueError('expected finite NED vectors and positive radius_m')
        distance = np.linalg.norm(points-center, axis=1)/radius
        result += np.maximum(0., 1.-distance**2)[:, None]**2 * velocity
    return result
