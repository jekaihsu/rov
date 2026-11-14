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


# Provisional X1 tether and reel values. Every entry names its evidence level and source; none is an
# X1 measurement (docs/reference/x1-measurement-checklist.md). Research notes cited here live in
# research_notes/臍帶纜物理與收放文獻/ (TP = tether_properties.md, CD = cable_dynamics_models.md,
# SH = shipboard_handling.md, SC = simulators_and_current_model.md).
_NUMERIC = '數值求解設定，非物理量；見 tether_solver.py'
X1_TETHER_PARAMETERS = {
 'segments': {'value': 40, 'level': 'estimated', 'source': '初始分段數；' + _NUMERIC},
 'max_segments': {'value': 64, 'level': 'estimated', 'source': '放纜後的分段上限，超過時合併纜盤側分段；' + _NUMERIC},
 'fine_segments': {'value': 8, 'level': 'estimated', 'source': 'ROV 端保持原長、不合併的分段數；' + _NUMERIC},
 'min_segment_m': {'value': 0.5, 'level': 'estimated', 'source': '初始分段最短長度；' + _NUMERIC},
 'contact_sample_m': {'value': 0.35, 'level': 'estimated',
                      'source': '長分段接觸取樣間距，小於最細斜撐直徑（0.4 m）避免穿樁；' + _NUMERIC},
 'diameter': {'value': 0.0095, 'level': 'reseller',
              'source': 'real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf'},
 'density': {'value': 1000.0, 'level': 'estimated',
             'source': 'TP §1 推論：小型 ROV「中性」纜多為淡水中性、海水微浮（Fathom、VideoRay）；X1 浮力等級未公開'},
 'added_mass_normal': {'value': 1.0, 'level': 'estimated',
                       'source': 'CD §3: Palm & Eskilsson 2020 Table 3 CMn = 1、CMt = 0；MoorDyn Can 1 / Cat 0'},
 'ea': {'value': 1.2e5, 'level': 'estimated',
        'source': 'TP §2 推論：300 kgf ÷ Kevlar 49 斷裂應變 2.4% ≈ 1.2e5 N；實際含結構伸長可能較軟（Falcon 4.3e4 N）'},
 'damping_ratio': {'value': 1.0, 'level': 'estimated',
                   'source': 'CD §2/§6: MoorDyn troubleshooting 建議分段阻尼接近臨界 ζ≈1，BA = ζ(L/N)√(EA·w)'},
 'cd_normal': {'value': 1.25, 'level': 'estimated',
               'source': 'CD §2/§3: Buckham 2003 Table 3.4 小型 ROV 纜擬合 1.25（文獻範圍 1.2–1.65）；投影面積 d·l'},
 'cd_tangent': {'value': 0.02, 'level': 'estimated',
                'source': 'CD §3: Driscoll 1999 / Palm & Eskilsson 2020 CDt 0.02，以 d·l 投影面積定義（濕面積 πd·l 下為 0.0064）'},
 'max_length': {'value': 350.0, 'level': 'reseller',
                'source': 'real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf'},
 'breaking_n': {'value': 2943.0, 'level': 'reseller',
                'source': 'real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf'},
 'termination_ratio': {'value': 136.0 / 450.0, 'level': 'estimated',
                       'source': 'TP §2: VideoRay 應力釋放 136 kg ÷ 纜 450 kg；X1 接頭強度未公開'},
 'working_load_ratio': {'value': 0.5, 'level': 'estimated',
                        'source': 'TP §2: VideoRay「工作負載不得超過斷裂強度一半」；Fathom 為 23%'},
 'reel_drum_mass_kg': {'value': 5.0, 'level': 'estimated',
                       'source': 'SH §1：無公開纜盤慣量；空盤等效線慣量假設，捲上纜線另以 ρA×未放出長度計'},
 'reel_free_drag_n': {'value': 20.0, 'level': 'estimated', 'source': 'SH §1 Gaps：無公開纜盤阻力；自由轉動軸承與滑環阻力假設'},
 'reel_brake_hold_n': {'value': 1471.5, 'level': 'estimated',
                       'source': 'SH §2/§3：Imenco 離合器防過拉；取纜線工作負載，煞住的纜盤在纜線過載前打滑'},
 'reel_feed_rate': {'value': 0.5, 'level': 'estimated', 'source': 'SH §5：手放纜速率無公開值；VideoRay「慢慢放」'},
 'reel_feed_force_n': {'value': 50.0, 'level': 'estimated', 'source': 'SH §5：助手手拉纜力假設'},
 'reel_haul_rate': {'value': 0.42, 'level': 'reseller',
                    'source': 'SH §1: QYSEA 電動纜盤（W6）300 m／12 min 慢檔 ≈ 0.42 m/s（快檔 0.63）；非 X1 纜盤'},
 'reel_pull_cap_n': {'value': 300.0, 'level': 'estimated',
                     'source': 'SH §3: 收纜拉力須低於纜線強度（IMCA SF 13/14、Imenco 150 kgf 先例）；低於接頭強度'},
 'reel_servo_tau': {'value': 0.3, 'level': 'estimated', 'source': '收放纜速度響應時間常數假設'},
 'auto_setpoint_n': {'value': 20.0, 'level': 'estimated',
                     'source': 'TP §4: Zand 模擬傳統纜線管理保持水面張力約 20 N'},
 'auto_deadband_n': {'value': 10.0, 'level': 'estimated', 'source': 'SH §3 推論的恆張力控制器（綜合，非廠商演算法）'},
 'auto_gain': {'value': 0.05, 'level': 'estimated', 'source': 'SH §3 推論的恆張力控制器（綜合，非廠商演算法）：放纜速率 = 增益 × 超出張力'},
 'auto_slack_rate': {'value': 0.15, 'level': 'estimated', 'source': 'SH §3 推論：鬆弛時慢速收纜'},
 'stall_speed': {'value': 0.02, 'level': 'estimated', 'source': 'SH §1: Deep Trekker PoweredReel stalled 旗標；門檻假設'},
 'stall_time': {'value': 1.5, 'level': 'estimated', 'source': 'SH §1: Deep Trekker PoweredReel stalled 旗標；門檻假設'},
 'gj': {'value': 0.1, 'level': 'estimated',
        'source': 'CD §2 / TP §2: Buckham 19 mm 纜 GJ 0.11、Zand 14 mm 纜 0.5 N·m² 按 d⁴ 縮至 9.5 mm ≈ 0.1'},
 'node_radius': {'value': 0.03, 'level': 'estimated', 'source': '接觸半徑；' + _NUMERIC},
 'mu_static': {'value': 0.6, 'level': 'estimated', 'source': 'CD §5: 無 ROV 纜摩擦實測；沿用舊值 0.6'},
 'mu_kinetic': {'value': 0.45, 'level': 'estimated', 'source': 'CD §5: 靜/動摩擦比假設（MoorDyn StatDynFricScale 概念）'},
 'stribeck_v': {'value': 0.05, 'level': 'estimated', 'source': '靜摩擦衰減速度假設'},
 'friction_regular_v': {'value': 0.01, 'level': 'estimated',
                        'source': 'CD §5: Palm & Eskilsson 2020 eq. 16 tanh 正則化 Coulomb；門檻速度未公開'},
 'chafe_limit_j': {'value': 20000.0, 'level': 'estimated',
                   'source': 'TP §5: IMCA SF 02/23 纜線磨斷；無公開磨耗量，僅供訓練顯示'},
 'chafe_failure': {'value': False, 'level': 'estimated', 'source': '磨耗不致斷纜（無資料），只回報磨耗比例'},
 'snag_hook_tension_n': {'value': 8.0, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'snag_hook_speed': {'value': 0.05, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'snag_hook_angle_deg': {'value': 25.0, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'snag_release_angle_deg': {'value': 10.0, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'snag_release_s': {'value': 0.5, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'snag_tighten_fraction': {'value': 0.4, 'level': 'estimated',
                           'source': 'operations_tether_sonar.md §7 B：拉扯使卡纏收緊；比例為假設'},
 'snag_tighten_rate': {'value': 0.3, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'snag_tighten_max': {'value': 3.0, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'snag_pin_stiffness': {'value': 3000.0, 'level': 'estimated', 'source': '卡點約束彈簧；' + _NUMERIC},
 'snag_pin_damping': {'value': 30.0, 'level': 'estimated', 'source': '卡點約束阻尼；' + _NUMERIC},
 'snag_cooldown_s': {'value': 3.0, 'level': 'estimated', 'source': 'tether_snag.py：訓練用假設'},
 'substeps': {'value': 10, 'level': 'estimated', 'source': _NUMERIC},
 'contact_cache_m': {'value': 0.01, 'level': 'estimated', 'source': _NUMERIC},
 'accelerated': {'value': True, 'level': 'estimated', 'source': _NUMERIC}}

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
