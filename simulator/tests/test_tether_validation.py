"""Tether model against literature behaviour (gap 10, research_notes/臍帶纜物理與收放文獻/).

Each case prints the numbers that docs/reference/tether-validation.md tabulates. Tolerances are
stated per case; the literature itself only supports agreement of about 10-20 % for tether models
(cable_dynamics_models.md §7), and several cases here are trends, not reproductions.
"""
import math
import unittest

import numpy as np

from qysim.physics import RHO, Vehicle
from qysim.tether import BENCHMARK_TETHER_PARAMETERS, Tether, TetherParams
from qysim.vehicles import BENCHMARK_HEAVY
from qysim.world import World

IDENTITY = np.array([1.0, 0.0, 0.0, 0.0])


class UniformCurrent:
    """Spatially uniform, steady current: the literature cases assume one."""

    def __init__(self, velocity):
        self.velocity = np.asarray(velocity, float)

    def sample_many(self, positions, seabed, t=0.0):
        return np.tile(self.velocity, (len(np.atleast_2d(positions)), 1))

    def sample(self, position, seabed, t=0.0):
        return self.velocity.copy()

    def mean_at(self, depth, seabed):
        return self.velocity.copy()


def deep_world(current=(0.0, 0.0, 0.0)):
    world = World(500.0)
    world.current = UniformCurrent(current)
    return world


def hold_ends(tether, gland, seconds, dt=0.01):
    for i in range(int(round(seconds / dt))):
        tether.step(dt, i * dt, gland, IDENTITY, np.zeros(3))


def catenary_sag(length, span):
    """Mid-span sag of an inextensible catenary of ``length`` hung between level points ``span`` apart."""
    lo, hi = 1e-3, 1e4
    for _ in range(200):
        a = 0.5 * (lo + hi)
        if 2 * a * math.sinh(span / (2 * a)) > length:
            lo = a
        else:
            hi = a
    a = 0.5 * (lo + hi)
    return a * (math.cosh(span / (2 * a)) - 1.0), a


def drag_profile(params, length, span, speed):
    """Quasi-static cable across a uniform current: integrate T dphi/ds = -f_n, dT/ds = -f_t.

    Starts at mid-span (phi = 0 by symmetry) and shoots on the mid-span tension so the end lands at
    span / 2. Returns (mid-span deflection, end tension). Independent of the lumped-mass solver."""
    q = 0.5 * RHO * params.diameter

    def run(t_mid):
        x = y = phi = 0.0
        tension = t_mid
        steps = 4000
        ds = 0.5 * length / steps
        for _ in range(steps):
            un = speed * math.cos(phi)
            ut = speed * math.sin(phi)
            f_n = q * params.cd_normal * un * abs(un)
            f_t = q * params.cd_tangent * ut * abs(ut)
            stretch = 1.0 + tension / params.ea
            x += math.cos(phi) * ds * stretch
            y += math.sin(phi) * ds * stretch
            phi -= f_n / tension * ds
            tension -= f_t * ds
        return x, y, tension

    lo, hi = 1e-3, 1e5
    for _ in range(100):
        mid = math.sqrt(lo * hi)
        if run(mid)[0] < 0.5 * span:
            lo = mid
        else:
            hi = mid
    x, y, tension = run(math.sqrt(lo * hi))
    return -y, tension


class TetherValidation(unittest.TestCase):
    def test_von_benzon_passive_tether_force(self):
        """von Benzon et al. 2022 passive test: BlueROV2 Heavy on 15 m, current [0.3536, 0.3536, 0].

        Paper (Figs. 8-9, simulated): tether straight after ~30 s, ROV near the surface after ~100 s,
        forces constant after 150 s at around 30 N. Base fixed at the origin; ROV released at 10 m.
        Tolerance: steady horizontal force components within 25 % of 30 N; settled by 150 s."""
        current = np.array([0.3536, 0.3536, 0.0])
        world = deep_world(current)
        vehicle = Vehicle(definition=BENCHMARK_HEAVY)
        vehicle.seabed_depth = 500.0
        vehicle.s.pos[:] = [0.0, 0.0, 10.0]
        vehicle.current_ned = current
        gland_body = np.array(BENCHMARK_HEAVY.gland_body)
        params = TetherParams(**BENCHMARK_TETHER_PARAMETERS, wet_weight_per_m=0.0)
        tether = Tether(world, np.zeros(3), vehicle.s.pos + gland_body, 15.0, params, gland_body=gland_body)
        tether.reel_command("hold")
        history = []
        dt = 0.01
        for i in range(int(180 / dt)):
            wrench = tether.step(dt, i * dt, vehicle.s.pos, vehicle.s.q, vehicle.world_velocity())
            vehicle.step(dt, np.zeros(8), wrench)
            history.append(tether.force_on_rov.copy())
        force = np.array(history)
        late = force[int(150 / dt):]
        settled = np.ptp(np.linalg.norm(late, axis=1))
        steady = late.mean(axis=0)
        print(f"von Benzon passive: steady force x {steady[0]:.1f} N, y {steady[1]:.1f} N, z {steady[2]:.1f} N, "
              f"|F| {np.linalg.norm(steady):.1f} N, ROV depth {vehicle.s.pos[2]:.2f} m, "
              f"spread after 150 s {settled:.2f} N")
        self.assertFalse(tether.broken)
        self.assertLess(settled, 1.0)
        for value in steady[:2]:
            self.assertLess(abs(abs(value) / 30.0 - 1.0), 0.25)
        self.assertLess(vehicle.s.pos[2], 3.0)

    def test_buckham_pool_tether_settles_to_catenary(self):
        """Buckham 2003 pool tether (Table 3.4: 3.70 m, d 13.6 mm, 1643 kg/m3, EA 23.5 kN, Cd 1.25).

        Qualitative: released straight between level ends 3.0 m apart in still water, it sags into the
        catenary without ringing. Pass: final sag within 3 % of the analytic catenary, overshoot
        below 10 % of the sag, and the sag steady to 1 % over the last 5 s (a lightly damped
        breathing mode of a few millimetres remains). Sea-water density is used."""
        world = deep_world()
        params = TetherParams(diameter=0.0136, density=1643.0, ea=23.5e3, cd_normal=1.25, segments=30)
        spool = np.array([0.0, 0.0, 5.0])
        gland = np.array([3.0, 0.0, 5.0])
        tether = Tether(world, spool, gland, 3.7, params, gland_body=np.zeros(3))
        tether.layout([spool, gland])
        tether.length = 3.7
        tether.reel_command("hold")
        sags = []
        for i in range(1500):
            tether.step(0.01, i * 0.01, gland, IDENTITY, np.zeros(3))
            sags.append(float(tether.x[:, 2].max() - 5.0))
        expected, _ = catenary_sag(3.7, 3.0)
        final = sags[-1]
        overshoot = max(sags) - final
        wobble = float(np.ptp(sags[-500:]))
        print(f"Buckham pool: sag {final:.3f} m vs catenary {expected:.3f} m "
              f"({final / expected - 1:+.1%}), overshoot {overshoot:.3f} m, last-5-s sag range {wobble:.4f} m")
        self.assertLess(abs(final / expected - 1.0), 0.03)
        self.assertLess(overshoot, 0.10 * expected)
        self.assertLess(wobble, 0.01 * expected)

    def test_steady_cable_across_current_matches_quasi_static_solution(self):
        """Neutral X1 tether, 10.3 m between fixed points 10 m apart, 0.5 m/s current across it.

        Reference: quasi-static cable equations with the same Morison loads, integrated by shooting
        (drag_profile). Pass: mid-span deflection and end tension within 5 %."""
        speed = 0.5
        world = deep_world((0.0, speed, 0.0))
        params = TetherParams(wet_weight_per_m=0.0, segments=40)
        spool = np.array([0.0, 0.0, 20.0])
        gland = np.array([10.0, 0.0, 20.0])
        tether = Tether(world, spool, gland, 10.3, params, gland_body=np.zeros(3))
        tether.layout([spool, gland])
        tether.length = 10.3
        tether.reel_command("hold")
        hold_ends(tether, gland, 90.0)
        deflection = float(tether.x[:, 1].max())
        tension = float(tether._seg_tension[-1])
        ref_deflection, ref_tension = drag_profile(params, 10.3, 10.0, speed)
        print(f"Current catenary: deflection {deflection:.3f} m vs {ref_deflection:.3f} m "
              f"({deflection / ref_deflection - 1:+.1%}); end tension {tension:.2f} N vs {ref_tension:.2f} N "
              f"({tension / ref_tension - 1:+.1%})")
        self.assertLess(abs(deflection / ref_deflection - 1.0), 0.05)
        self.assertLess(abs(tension / ref_tension - 1.0), 0.05)

    def test_zand_falcon_tether_drag_trend(self):
        """Zand (UVic MASc) Falcon tether: d 14 mm, neutral (1025 kg/m3), Cd 1.65, 26 m ship lead.

        Zand's simulated surge load on the ROV: 23 N at 0.2 m/s, 255 N at 0.67 m/s, 568 N at 1.0 m/s
        with 350 m deployed, i.e. close to quadratic (exponent 1.99). This case uses 80 m and the ROV
        held 26 m behind and 40 m below the spool, so absolute loads are lower; the check is the
        trend: power-law exponent within 1.7-2.2 and load ratio 1.0/0.2 m/s within 18-30 (Zand 24.7)."""
        params = TetherParams(diameter=0.014, density=1025.0, cd_normal=1.65, segments=40)
        loads = []
        speeds = (0.2, 0.67, 1.0)
        for speed in speeds:
            world = deep_world((-speed, 0.0, 0.0))
            spool = np.zeros(3)
            gland = np.array([-26.0, 0.0, 40.0])
            tether = Tether(world, spool, gland, 80.0, params, gland_body=np.zeros(3))
            tether.reel_command("hold")
            seconds = 120.0 + 60.0 / speed
            hold_ends(tether, gland, seconds, dt=0.02)
            loads.append(float(np.linalg.norm(tether.force_on_rov)))
        exponent = math.log(loads[2] / loads[0]) / math.log(speeds[2] / speeds[0])
        ratio = loads[2] / loads[0]
        print("Zand trend: loads " + ", ".join(f"{u} m/s {f:.1f} N" for u, f in zip(speeds, loads))
              + f"; exponent {exponent:.2f} (Zand 1.99); ratio {ratio:.1f} (Zand 24.7)")
        self.assertTrue(1.7 < exponent < 2.2)
        self.assertTrue(18.0 < ratio < 30.0)
        self.assertGreater(loads[1], loads[0])


if __name__ == "__main__":
    unittest.main()
