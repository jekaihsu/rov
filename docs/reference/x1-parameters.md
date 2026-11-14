# X1 暫定參數

唯一數值來源：`simulator/qysim/vehicles.py:X1_PARAMETERS`。
實測後只改該表，再執行 `python docs/reference/export_x1_parameters.py`。
目前沒有 measured；official 是廠商宣稱，reseller 是單一經銷商，estimated 是假設。

| 參數 | 值（SI） | 等級 | 依據 |
|---|---|---|---|
| mass | `30.0` | official | real-rov-research.md: X1 官方 ≤30 kg（此處取上限） |
| net_buoyancy | `2.943` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| gm | `0.03` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| added_mass | `(15.0, 25.0, 30.0)` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| inertia | `(1.1, 1.6, 1.8)` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| thruster_max | `148.0` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| motor_tau | `0.08` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| vmax | `(2.314998, 1.28611, 0.771666)` | reseller | real-rov-research.md: 經銷商分軸速度；前進亦有官網宣稱 |
| wmax | `(2.0943951023931953, 1.5707963267948966, 1.5707963267948966)` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| quadratic_drag | `None` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| reverse_ratio | `1.0` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| thrust_asymmetry | `True` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| linear_drag | `(8.0, 12.0, 15.0, 1.0, 1.0, 1.0)` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| thrusters | `(('T1 PORT_FRONT', (0.25, -0.193, 0.032), (0.32, -0.54, -0.78)), ('T2 STBD_FRONT', (0.25, 0.193, 0.032), (0.32, 0.54, -0.78)), ('T3 PORT_AFT', (-0.251, -0.171, -0.035), (-0.28, -0.48, 0.83)), ('T4 STBD_AFT', (-0.251, 0.171, -0.035), (-0.28, 0.48, 0.83)), ('T5 PORT_LONG', (-0.061, -0.205, 0.068), (-1.0, 0.0, 0.0)), ('T6 STBD_LONG', (-0.061, 0.205, 0.068), (-1.0, 0.0, 0.0)))` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| hull_centres | `((-0.25, 0.0, 0.0), (0.0, 0.0, 0.0), (0.25, 0.0, 0.0))` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| hull_radius | `0.22` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| gland_body | `(-0.38, 0.0, -0.06)` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| camera_body | `(0.39, 0.0, -0.03)` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| lamp_body | `((0.36, -0.12, 0.02), (0.36, 0.12, 0.02))` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| arm_mount_body | `(0.27, 0.0, 0.16)` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| hull_extra | `()` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| capabilities | `('surge', 'sway', 'heave', 'roll', 'pitch', 'yaw')` | estimated | Blender 重建／工程假設，非實測；見 real-rov-research.md 幾何缺口 |
| tether.segments | `40` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.diameter | `0.0095` | reseller | real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf |
| tether.mass_per_m | `0.12` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.wet_weight_per_m | `0.004` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.ea | `20000.0` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.k_max | `9000.0` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.damping_ratio | `0.6` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.cd_normal | `1.2` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.cd_tangent | `0.02` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.max_length | `350.0` | reseller | real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf |
| tether.breaking_n | `2943.0` | reseller | real-rov-research.md: 經銷商纜線 350 m × 9.5 mm × 300 kgf |
| tether.warn_n | `250.0` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.payout_threshold_n | `45.0` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.payout_rate | `1.0` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.node_radius | `0.03` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.friction | `0.6` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.substeps | `10` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.contact_cache_m | `0.01` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
| tether.accelerated | `True` | estimated | 工程／數值求解假設；研究報告明列 X1 纜線質量浮力與阻力未實測 |
