"""Vehicle catalogue. FRD metres about CG; hydrodynamics are engineering estimates.

Topology references: Blue Robotics Heavy configuration (four vectored + four
vertical), Saab Seaeye Falcon (four horizontal + one vertical). These models
are visual reconstructions, not manufacturer CAD or certified digital twins.
"""
from dataclasses import asdict, dataclass, replace

# Canonical provisional X1 values and evidence levels; no measured data yet.
X1_PARAMETERS = {'mass': {'value': 30.0, 'level': 'official', 'source': 'real-rov-research.md: X1 官方 ≤30 kg（此處取上限）'},
 'net_buoyancy': {'value': 2.943,
                  'level': 'estimated',
                  'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'gm': {'value': 0.03, 'level': 'estimated', 'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'added_mass': {'value': (15.0, 25.0, 30.0),
                'level': 'estimated',
                'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'inertia': {'value': (1.1, 1.6, 1.8),
             'level': 'estimated',
             'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'thruster_max': {'value': 148.0,
                  'level': 'estimated',
                  'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'motor_tau': {'value': 0.08, 'level': 'estimated', 'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'vmax': {'value': (2.314998, 1.28611, 0.771666),
          'level': 'reseller',
          'source': 'real-rov-research.md: 經銷商分軸速度；前進亦有官網宣稱'},
 'wmax': {'value': (2.0943951023931953, 1.5707963267948966, 1.5707963267948966),
          'level': 'estimated',
          'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'quadratic_drag': {'value': None,
                    'level': 'estimated',
                    'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'reverse_ratio': {'value': 1.0,
                   'level': 'estimated',
                   'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'thrust_asymmetry': {'value': True,
                      'level': 'estimated',
                      'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'linear_drag': {'value': (8.0, 12.0, 15.0, 1.0, 1.0, 1.0),
                 'level': 'estimated',
                 'source': '暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單'},
 'thrusters': {'value': (('T1 PORT_FRONT', (0.25, -0.193, 0.032), (0.32, -0.54, -0.78)),
                         ('T2 STBD_FRONT', (0.25, 0.193, 0.032), (0.32, 0.54, -0.78)),
                         ('T3 PORT_AFT', (-0.251, -0.171, -0.035), (-0.28, -0.48, 0.83)),
                         ('T4 STBD_AFT', (-0.251, 0.171, -0.035), (-0.28, 0.48, 0.83)),
                         ('T5 PORT_LONG', (-0.061, -0.205, 0.068), (-1.0, 0.0, 0.0)),
                         ('T6 STBD_LONG', (-0.061, 0.205, 0.068), (-1.0, 0.0, 0.0))),
               'level': 'estimated',
               'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'hull_centres': {'value': ((-0.25, 0.0, 0.0), (0.0, 0.0, 0.0), (0.25, 0.0, 0.0)),
                  'level': 'estimated',
                  'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'hull_radius': {'value': 0.22,
                 'level': 'estimated',
                 'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'gland_body': {'value': (-0.38, 0.0, -0.06),
                'level': 'estimated',
                'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'camera_body': {'value': (0.39, 0.0, -0.03),
                 'level': 'estimated',
                 'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'lamp_body': {'value': ((0.36, -0.12, 0.02), (0.36, 0.12, 0.02)),
               'level': 'estimated',
               'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'arm_mount_body': {'value': (0.27, 0.0, 0.16),
                    'level': 'estimated',
                    'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'hull_extra': {'value': (),
                'level': 'estimated',
                'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'},
 'capabilities': {'value': ('surge', 'sway', 'heave', 'roll', 'pitch', 'yaw'),
                  'level': 'estimated',
                  'source': 'Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口'}}


X1_TETHER_PARAMETERS = {'segments': {'value': 40, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'diameter': {'value': 0.0095,
              'level': 'reseller',
              'source': 'real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf'},
 'mass_per_m': {'value': 0.12, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'wet_weight_per_m': {'value': 0.004, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'ea': {'value': 20000.0, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'k_max': {'value': 9000.0, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'damping_ratio': {'value': 0.6, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'cd_normal': {'value': 1.2, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'cd_tangent': {'value': 0.02, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'max_length': {'value': 350.0,
                'level': 'reseller',
                'source': 'real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf'},
 'breaking_n': {'value': 2943.0,
                'level': 'reseller',
                'source': 'real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf'},
 'warn_n': {'value': 250.0, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'payout_threshold_n': {'value': 45.0, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'payout_rate': {'value': 1.0, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'node_radius': {'value': 0.03, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'friction': {'value': 0.6, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'substeps': {'value': 10, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'contact_cache_m': {'value': 0.01, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'},
 'accelerated': {'value': True, 'level': 'estimated', 'source': '工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測'}}

X1_THRUSTERS = X1_PARAMETERS["thrusters"]["value"]

def vectored(length, width):
    return tuple((f"T{i+1} HORIZONTAL", (x*length, y*width, 0.),
                  (.70710678, -x*y*.70710678, 0.))
                 for i, (x, y) in enumerate(((1, -1), (1, 1), (-1, -1), (-1, 1))))


@dataclass(frozen=True)
class VehicleDefinition:
    id: str
    name: str
    model: str
    params: dict
    thrusters: tuple
    hull_centres: tuple
    hull_radius: float
    gland_body: tuple
    camera_body: tuple
    lamp_body: tuple
    arm_mount_body: tuple
    capabilities: tuple = ("surge", "sway", "heave", "roll", "pitch", "yaw")
    hull_extra: tuple = ()

    @property
    def hull_spheres(self):
        return tuple((c, self.hull_radius) for c in self.hull_centres) + self.hull_extra

    def public(self):
        value = asdict(self)
        value["thrusters"] = [{"name": n, "pos": list(p), "axis": list(a)} for n, p, a in self.thrusters]
        value["estimated"] = True
        return value


X1_PHYSICS_KEYS = ('mass',
 'net_buoyancy',
 'gm',
 'added_mass',
 'inertia',
 'thruster_max',
 'motor_tau',
 'vmax',
 'wmax',
 'quadratic_drag',
 'reverse_ratio',
 'thrust_asymmetry',
 'linear_drag')


VEHICLE_DEFINITIONS = {
    "x1": VehicleDefinition(
        "x1", "X1", "models/rov.glb",
        params={key: item["value"] for key, item in X1_PARAMETERS.items()
                if key in X1_PHYSICS_KEYS},
        **{key: item["value"] for key, item in X1_PARAMETERS.items()
           if key not in X1_PHYSICS_KEYS}),
    "bluerov2_heavy": VehicleDefinition("bluerov2_heavy", "BlueROV2 Heavy", "models/bluerov2_heavy.glb",
        dict(mass=13.5, net_buoyancy=1.5, gm=.055, added_mass=(7., 10., 13.),
             inertia=(.7, .9, 1.), thruster_max=50., motor_tau=.12,
             vmax=(1.5, 1.0, .8), wmax=(1.1, 1., 1.2), linear_drag=(7., 10., 12., 1., 1., 1.)),
        vectored(.18, .20) + tuple((f"T{i+5} VERTICAL", (x*.13, y*.24, -.11), (0., 0., -1.))
                                  for i, (x, y) in enumerate(((1, -1), (1, 1), (-1, -1), (-1, 1)))),
        ((-.17, 0., 0.), (.17, 0., 0.)), .24,
        (-.20, 0., -.15), (.245, 0., -.015), ((.24, -.18, -.09), (.24, .18, -.09)), (.18, 0., .15)),
    "falcon": VehicleDefinition("falcon", "Falcon", "models/falcon.glb",
        dict(mass=60., net_buoyancy=5., gm=.095, added_mass=(30., 45., 55.),
             inertia=(4., 7., 8.), thruster_max=110., motor_tau=.18,
             vmax=(1.5, 1., .6), wmax=(.5, .5, .8), linear_drag=(18., 28., 35., 3., 4., 4.)),
        tuple((f"T{i+1} HORIZONTAL", (x*.29, y*.16, .075), (.86, -x*y*.51, 0.))
              for i, (x,y) in enumerate(((1,-1),(1,1),(-1,-1),(-1,1))))
        + (("T5 VERTICAL", (0., 0., .02), (0., 0., -1.)),),
        ((-.32, 0., 0.), (0., 0., 0.), (.32, 0., 0.)), .30,
        (-.25, 0., -.27), (.485, 0., -.175), ((.418, -.225, .025), (.418, .225, .025)), (.30, -.12, .40),
        ("surge", "sway", "heave", "yaw"),
        (((-.25, 0., .33), .17), ((.25, 0., .33), .17))),
}


def get_vehicle_definition(model_id="x1"):
    try:
        return VEHICLE_DEFINITIONS[model_id]
    except KeyError:
        raise ValueError(f"Unknown vehicle model: {model_id}") from None


def vehicle_catalogue():
    return [definition.public() for definition in VEHICLE_DEFINITIONS.values()]


# Offline reference profile, deliberately excluded from the operator catalogue.
# Source: von Benzon 2022 Appendix A (see docs/rov-dynamics-research.md).
# Motor axis signs are paired, unlike the visually reoriented legacy geometry.
_heavy = VEHICLE_DEFINITIONS["bluerov2_heavy"]
BENCHMARK_HEAVY = replace(
    _heavy,
    params=dict(mass=13.5, net_buoyancy=-.982, gm=.01,
                added_mass=(6.36, 7.12, 18.68), inertia=(.449, .365, .592),
                thruster_max=5.25 * 9.81, reverse_ratio=4.1 / 5.25, motor_tau=.076,
                linear_drag=(13.7, 0., 33., 0., .8, 0.),
                quadratic_drag=(141., 217., 190., 1.19, .47, 1.5)),
    thrusters=tuple((name, pos, tuple(c * (-1 if i % 2 else 1) for c in axis))
                    for i, (name, pos, axis) in enumerate(_heavy.thrusters)),
)
