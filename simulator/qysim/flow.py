"""Ocean flow building blocks shared by ``world.CurrentProfile``.

Every number marked "assumed" is a provisional simulator value from
``research_notes/洋流與波浪對ROV作業/`` and must be replaced by measurements when they exist.

Pieces
    TurbulenceField  smooth anisotropic frozen turbulence: random Fourier modes (Matern-3/2
                     spectrum) advected with the depth-averaged mean current (Taylor hypothesis)
                     plus a slow eddy evolution. The state is integrated once per tick, so the
                     field and its time derivative are bounded and independent of the step size.
"""

from __future__ import annotations

import math

import numpy as np

# streamwise : cross-stream : vertical turbulence ratios (Islay 1 : 0.75 : 0.55, open channel 0.71/0.55)
COMPONENT_RATIOS = np.array([1.0, 0.7, 0.5])


def turbulence_length(seabed: float) -> float:
    """Integral length scale (m): about half the water depth, 2..15 m (Islay 11-14 m; assumed)."""
    return float(min(15.0, max(2.0, 0.5 * seabed)))


# ── turbulence ───────────────────────────────────────────────────────────────
class TurbulenceField:
    """Frozen, smoothly evolving unit-variance turbulence with three independent components.

    Each component is ``sqrt(2/N) * sum cos(k_j . (x - D) / ell + psi_j + theta_j)``. Wave
    vectors follow a 3-D Student-t (3 dof) law, whose characteristic function is the Matern-3/2
    correlation: once differentiable, so the field and its time derivative stay bounded.
    ``D`` is the integrated advection displacement and ``theta`` the integrated eddy-evolution
    phase; both advance in ``advance`` with the midpoint rule, so results do not depend on dt.
    """

    MODES = 32
    K_MAX = 5.0                      # truncate the heavy tail of |k| * ell
    # ell = SCALE * L gives correlation 0.36 at the integral length L and integral scale ~0.92 L.
    SCALE = 0.8

    def __init__(self, seed: int = 0):
        rng = np.random.default_rng(int(seed) + 0x5EED)
        z = rng.standard_normal((3, self.MODES, 3))
        chi = rng.chisquare(3, (3, self.MODES))
        k = z * np.sqrt(3.0 / chi)[..., None]
        mag = np.linalg.norm(k, axis=2, keepdims=True)
        self.k = k * np.minimum(1.0, self.K_MAX / np.maximum(mag, 1e-9))
        self.psi = rng.uniform(0.0, 2 * math.pi, (3, self.MODES))
        self.evolve = rng.standard_normal((3, self.MODES))
        self.amp = math.sqrt(2.0 / self.MODES)
        self.displacement = np.zeros(3)
        self.theta = np.zeros((3, self.MODES))
        self._k_all = self.k.reshape(3 * self.MODES, 3).T.copy()

    def advance(self, dt: float, advect: np.ndarray, ell: float, sigma: float) -> None:
        """Integrate advection displacement and eddy evolution over ``dt`` (midpoint velocities)."""
        self.displacement = self.displacement + np.array([advect[0], advect[1], 0.0]) * dt
        rate = max(sigma, 0.02) / ell
        self.theta = self.theta + self.evolve * rate * dt

    def unit(self, points: np.ndarray, ell: float) -> np.ndarray:
        """(N, 3) unit-variance fluctuations (u, v, w) at NED points, before frame rotation."""
        X = (np.asarray(points, float) - self.displacement) * (1.0 / ell)
        arg = X @ self._k_all + (self.psi + self.theta).ravel()
        return self.amp * np.cos(arg).reshape(len(X), 3, self.MODES).sum(axis=2)

    def unit_rate(self, points: np.ndarray, ell: float, advect: np.ndarray, sigma: float) -> np.ndarray:
        """Analytic time derivative of ``unit`` at fixed points (1/s), for bound checks and tests."""
        X = (np.asarray(points, float) - self.displacement) / ell
        adv = np.array([advect[0], advect[1], 0.0]) / ell
        rate = max(sigma, 0.02) / ell
        out = np.empty((len(X), 3))
        for c in range(3):
            arg = X @ self.k[c].T + (self.psi[c] + self.theta[c])
            omega = -(self.k[c] @ adv) + self.evolve[c] * rate
            out[:, c] = -self.amp * (np.sin(arg) * omega).sum(axis=1)
        return out

    def state(self) -> dict:
        return {"displacement": self.displacement.copy(), "theta": self.theta.copy()}


def turbulence_vectors(unit: np.ndarray, mean: np.ndarray, intensity: float, depths: np.ndarray,
                       fallback_dir: np.ndarray) -> np.ndarray:
    """Scale unit fluctuations into the local mean-flow frame with ratios (1, 0.7, 0.5).

    sigma_u = intensity * |mean|. Vertical fluctuations taper to zero within 2 m of the surface.
    """
    mx, my = mean[:, 0], mean[:, 1]
    speed_h = np.sqrt(mx * mx + my * my)
    sigma = intensity * np.sqrt(speed_h * speed_h + mean[:, 2] * mean[:, 2])
    calm = speed_h < 1e-6
    inv = 1.0 / np.where(calm, 1.0, speed_h)
    ex = np.where(calm, fallback_dir[0], mx * inv)
    ey = np.where(calm, fallback_dir[1], my * inv)
    u = unit[:, 0] * (COMPONENT_RATIOS[0] * sigma)
    v = unit[:, 1] * (COMPONENT_RATIOS[1] * sigma)
    w = unit[:, 2] * (COMPONENT_RATIOS[2] * sigma) * np.clip(np.asarray(depths, float) * 0.5, 0.0, 1.0)
    return np.stack([ex * u - ey * v, ey * u + ex * v, w], axis=1)
