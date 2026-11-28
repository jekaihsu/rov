# X1 暫定參數

參數及來源集中於 `simulator/qysim/vehicles.py`。
實測後只改該表，再執行 `python docs/reference/export_x1_parameters.py`。
目前沒有 measured。official 是廠商宣稱，reseller 是單一經銷商，published 是公開文獻採為模型預設（不是 X1 實測），estimated 是假設。

| 參數 | 值（SI） | 等級 | 依據 |
|---|---|---|---|
| mass | `30.0` | official | real-rov-research.md: X1 官方 ≤30 kg（此處取上限） |
| net_buoyancy | `2.943` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| gm | `0.03` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| added_mass | `(15.0, 25.0, 30.0)` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| inertia | `(1.1, 1.6, 1.8)` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| thruster_max | `148.0` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| motor_tau | `0.05047196008277468` | estimated | 暫定：沿用原繫樁推力上升時間 0.08 s，以 T ∝ n² 換算槳軸時間常數；待同步記錄轉速／推力 |
| vmax | `(2.314998, 1.28611, 0.771666)` | reseller | real-rov-research.md: 經銷商分軸速度；前進亦有官網宣稱 |
| wmax | `(2.0943951023931953, 1.5707963267948966, 1.5707963267948966)` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| quadratic_drag | `None` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
| reverse_ratio | `0.9` | estimated | 暫定工程估算；非 X1 實測，見 real-rov-research.md 對齊清單 |
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
| tether.segments | `40` | estimated | 初始分段數；數值求解設定，非物理量；見 tether_solver.py |
| tether.max_segments | `64` | estimated | 放纜後的分段上限，超過時合併纜盤側分段；數值求解設定，非物理量；見 tether_solver.py |
| tether.fine_segments | `8` | estimated | ROV 端保持原長、不合併的分段數；數值求解設定，非物理量；見 tether_solver.py |
| tether.min_segment_m | `0.5` | estimated | 初始分段最短長度；數值求解設定，非物理量；見 tether_solver.py |
| tether.contact_sample_m | `0.35` | estimated | 長分段接觸取樣間距，小於最細斜撐直徑（0.4 m）避免穿樁；數值求解設定，非物理量；見 tether_solver.py |
| tether.diameter | `0.0095` | reseller | real-rov-research.md: 經銷商頁 350 m × 9.5 mm × 300 kgf。X1 實纜暫定，非實測 |
| tether.density | `1000.0` | estimated | tether-parameters.md：公開「中性」多指淡水中性、海水微浮。X1 浮力等級未公開，暫定 |
| tether.added_mass_normal | `1.0` | published | tether-parameters.md：圓柱位勢流法向 Ca=1、切向 0（Palm & Eskilsson 2020）。非 X1 實測 |
| tether.ea | `120000.0` | estimated | tether-parameters.md：300 kgf ÷ 芳綸紗斷裂應變 2.4% ≈ 1.2e5 N。含結構伸長會更軟。X1 暫定 |
| tether.damping_ratio | `1.0` | estimated | CD §2/§6: MoorDyn troubleshooting 建議分段阻尼接近臨界 ζ≈1，BA = ζ(L/N)√(EA·w) |
| tether.cd_normal | `1.25` | published | tether-parameters.md：Buckham 2003 小型纜擬合 1.25（d·l）。光滑圓柱約 1.2；渦振可到 2–3。非 X1 實測 |
| tether.cd_tangent | `0.02` | published | tether-parameters.md：Driscoll 1999、Palm & Eskilsson 2020，d·l 定義下 0.02（濕面積約 0.0064）。非 X1 實測 |
| tether.max_length | `350.0` | reseller | real-rov-research.md: 經銷商頁 350 m × 9.5 mm × 300 kgf。X1 實纜暫定，非實測 |
| tether.breaking_n | `2943.0` | reseller | real-rov-research.md: 經銷商頁 350 m × 9.5 mm × 300 kgf。X1 實纜暫定，非實測 |
| tether.termination_ratio | `0.3022222222222222` | estimated | TP §2: VideoRay 應力釋放 136 kg ÷ 纜 450 kg；X1 接頭強度未公開 |
| tether.working_load_ratio | `0.5` | estimated | TP §2: VideoRay「工作負載不得超過斷裂強度一半」；Fathom 為 23% |
| tether.float_area | `0.0` | estimated | 暫定：均布浮套每米增加的排水體積，預設裸纜 (m²) |
| tether.float_density | `300.0` | estimated | 暫定：浮套材料模型假設 (kg/m³)，待量測 |
| tether.ei | `0.004` | estimated | 暫定：柔性纜等效 EI；假設 10 MPa × πd⁴/64，待 X1 三點彎曲試驗 |
| tether.deck_drag_n | `1.0` | estimated | 暫定：甲板平放段的滑動阻力；待 X1 導纜路線拉力量測 |
| tether.reel_drum_mass_kg | `5.0` | estimated | SH §1：無公開纜盤慣量；空盤等效線慣量假設，捲上纜線另以 ρA×未放出長度計 |
| tether.reel_free_drag_n | `20.0` | estimated | SH §1 Gaps：無公開纜盤阻力；自由轉動軸承與滑環阻力假設 |
| tether.reel_brake_hold_n | `1471.5` | estimated | SH §2/§3：Imenco 離合器防過拉；取纜線工作負載，煞住的纜盤在纜線過載前打滑 |
| tether.reel_feed_rate | `0.5` | estimated | SH §5：手放纜速率無公開值；VideoRay「慢慢放」 |
| tether.reel_feed_force_n | `50.0` | estimated | SH §5：助手手拉纜力假設 |
| tether.reel_haul_rate | `0.42` | reseller | SH §1: QYSEA 電動纜盤（W6）300 m／12 min 慢檔 ≈ 0.42 m/s（快檔 0.63）；非 X1 纜盤 |
| tether.reel_pull_cap_n | `300.0` | estimated | SH §3: 收纜拉力須低於纜線強度（IMCA SF 13/14、Imenco 150 kgf 先例）；低於接頭強度 |
| tether.reel_servo_tau | `0.3` | estimated | 收放纜速度響應時間常數假設 |
| tether.auto_setpoint_n | `20.0` | estimated | TP §4: Zand 模擬傳統纜線管理保持水面張力約 20 N |
| tether.auto_deadband_n | `10.0` | estimated | SH §3 推論的恆張力控制器（綜合，非廠商演算法） |
| tether.auto_gain | `0.05` | estimated | SH §3 推論的恆張力控制器（綜合，非廠商演算法）：放纜速率 = 增益 × 超出張力 |
| tether.auto_slack_rate | `0.15` | estimated | SH §3 推論：鬆弛時慢速收纜 |
| tether.stall_speed | `0.02` | estimated | SH §1: Deep Trekker PoweredReel stalled 旗標；門檻假設 |
| tether.stall_time | `1.5` | estimated | SH §1: Deep Trekker PoweredReel stalled 旗標；門檻假設 |
| tether.gj | `0.1` | estimated | CD §2 / TP §2: Buckham 19 mm 纜 GJ 0.11、Zand 14 mm 纜 0.5 N·m² 按 d⁴ 縮至 9.5 mm ≈ 0.1 |
| tether.node_radius | `0.03` | estimated | 接觸半徑；數值求解設定，非物理量；見 tether_solver.py |
| tether.mu_static | `0.6` | estimated | CD §5: 無 ROV 纜摩擦實測；沿用舊值 0.6 |
| tether.mu_kinetic | `0.45` | estimated | CD §5: 靜/動摩擦比假設（MoorDyn StatDynFricScale 概念） |
| tether.stribeck_v | `0.05` | estimated | 靜摩擦衰減速度假設 |
| tether.friction_regular_v | `0.01` | estimated | CD §5: Palm & Eskilsson 2020 eq. 16 tanh 正則化 Coulomb；門檻速度未公開 |
| tether.chafe_limit_j | `20000.0` | estimated | TP §5: IMCA SF 02/23 纜線磨斷；無公開磨耗量，僅供訓練顯示 |
| tether.chafe_failure | `False` | estimated | 磨耗不致斷纜（無資料），只回報磨耗比例 |
| tether.snag_hook_tension_n | `8.0` | estimated | tether_snag.py：訓練用假設 |
| tether.snag_hook_speed | `0.05` | estimated | tether_snag.py：訓練用假設 |
| tether.snag_hook_angle_deg | `25.0` | estimated | tether_snag.py：訓練用假設 |
| tether.snag_release_angle_deg | `10.0` | estimated | tether_snag.py：訓練用假設 |
| tether.snag_release_s | `0.5` | estimated | tether_snag.py：訓練用假設 |
| tether.snag_tighten_fraction | `0.4` | estimated | operations_tether_sonar.md §7 B：拉扯使卡纏收緊；比例為假設 |
| tether.snag_tighten_rate | `0.3` | estimated | tether_snag.py：訓練用假設 |
| tether.snag_tighten_max | `3.0` | estimated | tether_snag.py：訓練用假設 |
| tether.snag_pin_stiffness | `3000.0` | estimated | 卡點約束彈簧；數值求解設定，非物理量；見 tether_solver.py |
| tether.snag_pin_damping | `30.0` | estimated | 卡點約束阻尼；數值求解設定，非物理量；見 tether_solver.py |
| tether.snag_cooldown_s | `3.0` | estimated | tether_snag.py：訓練用假設 |
| tether.substeps | `10` | estimated | 數值求解設定，非物理量；見 tether_solver.py |
| tether.contact_cache_m | `0.01` | estimated | 數值求解設定，非物理量；見 tether_solver.py |
| tether.accelerated | `True` | estimated | 數值求解設定，非物理量；見 tether_solver.py |
| hydro.added_centre_z | `-0.015` | estimated | 暫定：流體慣性中心取 CG 上方半個 GM |
| hydro.rotary_added | `(0.275, 0.4, 0.45)` | estimated | 暫定：原有效轉動慣量的四分之一歸於附加慣量 |
| hydro.diameter | `0.11` | estimated | 暫定：依重建導管外形估算槳徑，m |
| hydro.rated_rps | `65.0` | estimated | 暫定：設計工作點轉速假設，rev/s，待光學轉速計校正 |
| hydro.kt_slope | `0.3` | estimated | 暫定：以線性開水域近似，一單位前進比損失三成靜推力 |
| hydro.hull_loss | `0.015` | estimated | 暫定：機身裝機遮蔽造成的靜推力損失比例 |
| hydro.wake_loss | `0.12` | estimated | 暫定：同軸近距離雙槳損失比例上界，再依軸距與橫距衰減 |
| hydro.dry_depth_d | `-0.5` | estimated | 暫定：槳心高於水面半個槳徑時全槳離水 |
| hydro.wet_depth_d | `1.0` | estimated | 暫定：槳心在水面下一個槳徑時吸氣消失 |
