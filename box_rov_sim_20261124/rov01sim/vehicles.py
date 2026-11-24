"""Vehicle catalogue. FRD metres about CG; hydrodynamics are engineering estimates.

Topology references: ROV-01 open-frame 6-thruster configuration (four 45-deg vectored
horizontal/pitch thrusters + two vertical Z thrusters), ROV-02-HEAVY (four vectored +
four vertical), ROV-01-PRO (four horizontal + one vertical).
"""
from dataclasses import asdict, dataclass

ROV01_THRUSTERS = (
    ("T1 PORT_FRONT", (0.36, -0.24, 0.10944061), (0.49713, 0.78946929, -0.36)),
    ("T2 STBD_FRONT", (0.36, 0.24, 0.10944061), (0.49713, -0.78946929, -0.36)),
    ("T3 PORT_AFT", (-0.36, -0.24, -0.10944061), (0.49713, -0.78946929, -0.36)),
    ("T4 STBD_AFT", (-0.36, 0.24, -0.10944061), (0.49713, 0.78946929, -0.36)),
    ("T5 PORT_VERT", (0.0, -0.24, 0.0), (0.0, 0.0, -1.0)),
    ("T6 STBD_VERT", (0.0, 0.24, 0.0), (0.0, 0.0, -1.0)),
)


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


VEHICLE_DEFINITIONS = {
    "rov01": VehicleDefinition("rov01", "ROV-01", "procedural://rov-01", {}, ROV01_THRUSTERS,
        ((-.25, 0., 0.), (0., 0., 0.), (.25, 0., 0.)), .22,
        (-.38, 0., -.06), (.39, 0., -.03), ((.36, -.12, .02), (.36, .12, .02)), (.27, 0., .16)),
    "rov02_heavy": VehicleDefinition("rov02_heavy", "ROV-02-HEAVY", "procedural://rov-02-heavy",
        dict(mass=13.5, net_buoyancy=1.5, gm=.055, added_mass=(7., 10., 13.),
             inertia=(.7, .9, 1.), thruster_max=50., motor_tau=.12,
             vmax=(1.5, 1.0, .8), wmax=(1.1, 1., 1.2), linear_drag=(7., 10., 12., 1., 1., 1.)),
        vectored(.18, .20) + tuple((f"T{i+5} VERTICAL", (x*.13, y*.24, -.11), (0., 0., -1.))
                                  for i, (x, y) in enumerate(((1, -1), (1, 1), (-1, -1), (-1, 1)))),
        ((-.17, 0., 0.), (.17, 0., 0.)), .24,
        (-.20, 0., -.15), (.245, 0., -.015), ((.24, -.18, -.09), (.24, .18, -.09)), (.18, 0., .15)),
    "rov01_pro": VehicleDefinition("rov01_pro", "ROV-01-PRO", "procedural://rov-01-pro",
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


def get_vehicle_definition(model_id="rov01"):
    if model_id in ("rov-01", "ROV-01"):
        model_id = "rov01"
    try:
        return VEHICLE_DEFINITIONS[model_id]
    except KeyError:
        raise ValueError(f"Unknown vehicle model: {model_id}") from None


def vehicle_catalogue():
    return [definition.public() for definition in VEHICLE_DEFINITIONS.values()]
