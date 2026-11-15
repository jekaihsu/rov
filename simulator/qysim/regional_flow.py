"""Compact regional currents in NED metres and m/s; training approximation, not CFD."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class RegionalFlow:
    center: tuple
    radii: tuple
    velocity: tuple

    def __post_init__(self):
        for name in ("center", "radii", "velocity"):
            a = np.asarray(getattr(self, name), float)
            if a.shape != (3,) or not np.isfinite(a).all():
                raise ValueError("regional flow requires finite three-vectors")
            object.__setattr__(self, name, tuple(float(v) for v in a))
        if np.any(np.asarray(self.radii) <= 0):
            raise ValueError("regional flow radii must be positive")

    def sample_many(self, points):
        p = np.atleast_2d(np.asarray(points, float))
        r = np.linalg.norm((p - self.center) / self.radii, axis=1)
        x = np.clip(1 - r, 0, 1)
        weight = x * x * (3 - 2 * x)
        return weight[:, None] * np.asarray(self.velocity)

    def as_dict(self):
        return dict(center=list(self.center), radii=list(self.radii), velocity=list(self.velocity))
