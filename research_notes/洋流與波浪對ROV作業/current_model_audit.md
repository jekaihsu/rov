# 洋流與波浪模型稽核：本專案 vs 其他模擬器

日期：2026-11-14。只做研究，沒有修改程式碼。
實驗腳本放在 `/tmp/claude-0/-home-user-rov/c18300da-7030-5b94-b1a0-14632023d865/scratchpad/`
（`gust_stats.py`、`spatial.py`、`drift.py`、`waves_fk.py`）。行號以本次讀到的 `main` 工作樹為準。

---

## A. 本專案現況

### A1. 流場本體：`CurrentProfile`（`simulator/qysim/world.py`）

| 機制 | 位置 | 行為 |
|---|---|---|
| 三層剖面 | `world.py:243-259` | 表層、中層、底層各給一組節數與流向（流去的方向）。`turbulence` 預設 0.15，`gust_tau` 預設 6 s |
| 深度內插 | `world.py:261-269` | 0 → 水深/2 線性內插表層到中層，水深/2 → 海床內插中層到底層 |
| 「邊界層」 | `world.py:270-273`、`world.py:287` | 只有離海床最後 1 m 內線性降到 0。用的是**名目** `seabed_depth`，不是地形高度 |
| 陣風 | `world.py:276-278` | 單一個 3 維 Ornstein-Uhlenbeck 狀態 `_gust`，`k=dt/τ`，水平兩軸權重相同（1, 1），垂直 0.3。**整個世界共用同一個陣風向量** |
| 陣風疊加 | `world.py:288-289`、`world.py:292-293` | `v + gust·turbulence·max(0.05, |v_mean|)`。平均流為 0 時仍有 0.05 m/s 的下限乘上 turbulence |
| 「局部流」 | `world.py:295-308` | `sample_many`：加上振幅 18% 平均流速的正弦剪切，相位 `0.035x + 0.027y + 0.045t`。註解寫明「不是解障礙物的 CFD」 |
| 共用者 | `engine.py:187`（載具）、`tether.py:161`（纜線各節點）、`world.py:542`（泥沙雲）、`ecology.py:101`（魚群，×0.35）、`operations.py:69`（工作物件） | 全部透過 `sample`／`sample_many` |
| 陣風步進 | `engine.py:186`（單機）、`room.py:196`（多人房，每 tick 一次，`engine.step(update_world=False)`） | 由 `test_multiplayer.py:36-39` 保證一個 tick 只步進一次 |
| 狀態輸出 | `engine.py:760`、`engine.py:784-785` | `current_here`（含陣風與剪切）、`current_kn` 送到前端與 HUD |

### A2. 洋流怎麼作用在載具上（`simulator/qysim/physics.py`）

- 相對速度：`physics.py:233-234`，`v_rel = vel − R^T·v_c`。`vel` 是對地速度（`physics.py:266-269`）。
- 阻力：`physics.py:236`，作用在 `v_rel` 上的線性加二次項。
- 附加質量科氏力：`physics.py:130-143` 與 `physics.py:247`，用 `v_rel`（依 Fossen 的寫法）。
- 洋流在機體座標中的旋轉：`physics.py:249-252`，`−M_A·(ω × v_c,body)`。程式碼註解明說：「Spatial/time derivatives of the flow field are not supplied here.」
- **缺的部分**：`M_A·dv_c/dt` 與 Froude-Krylov 項 `ρ∇·Dv_c/Dt` 都沒有。運動方程用的是 `(m + m_A)·v̇ = F`（`physics.py:178`、`physics.py:253`）。所以陣風或空間梯度造成的流體加速度，不會產生慣性力，只會經由阻力慢慢傳到載具。
- 流速只在重心取樣一次（`engine.py:187`），船體上沒有剪切力矩。
- 水面處理：`physics.py:272-275` 直接把 z 夾在 0。沒有波浪、自由液面效應，也沒有穿越水面時浮力的變化。

### A3. 纜線（`simulator/qysim/tether.py`）

- 每一步都在每個節點用 `sample_many` 取樣洋流（`tether.py:161`），所以有深度剖面。陣風是共用的，所有節點同相位。
- Morison 型阻力分成法向與切向（`tether.py:231-242`），`cd_normal=1.2`、`cd_tangent=0.02`，都是假設值（`vehicles.py:86-87`）。
- 節點質量包含附加質量（`tether.py:148-151`）。和載具一樣，沒有流體加速度項。
- 初始鬆弛的「彎弧」順著中點深度的平均流擺放（`tether.py:96-104`），起跑前再 settle 2 s（`engine.py:102-103`）。

### A4. 情境數值（`simulator/qysim/scenarios.py`）

`CurrentProfile(表層 kn, 向, 中層 kn, 向, 底層 kn, 向, turbulence)`：

| 情境 | 位置 | 剖面（kn） | turbulence |
|---|---|---|---|
| open_water | `:124` | 0.3/0.3/0.1 @45° | 0.2 |
| jacket_inspection | `:137` | 1.5/1.0/0.4，向 80→110° | 0.25 |
| monopile_current | `:148` | 1.8/1.6/0.8，向 180→190° | 0.3 |
| tether_untangle | `:159` | 0.8/0.8/0.3 | 0.2 |
| hull_inspection | `:172` | 0.6/0.5/0.2 | 0.2 |
| wreck_survey | `:187` | 0.8/0.6/0.3 | 0.25 |
| korean_castle | `:215` | 0.9/0.6/0.3 | 0.25 |
| coral_reef | `:274` | 0.55/0.35/0.12 | 0.12 |
| seagrass_meadow | `:284` | 0.4/0.3/0.10 | 0.15 |
| harbor_inspection | `:298` | 0.8/0.55/0.15 | 0.2 |
| tutorial_pool | `:310` | 0 | 0 |
| incident_jacket | `:335` | 2/1.8/1 | 0.2 |
| incident_current | `:380` | 3/3/2 | 0.2 |
| incident_wreck/silt/compass | `:342-372` | 預設 0（turbulence 仍是 0.15，所以有 ≈0.01 m/s 殘餘擾動） | 0.15 |
| random | `:260-263` | 表層 U(0,3) kn，中層 ×U(0.5,1)，底層 ×U(0.1,0.5)，流向各自 ±40/±60° | U(0.1,0.4) |

上述剖面在整個任務期間都不隨時間改變。沒有漲退潮，也沒有平潮窗口。

### A5. 教官與伺服器注入

- `instructor.py:76-77, 98-102, 118-119`：以 `strength∈[0,1]` 把三層**都**設成 `strength×4 kn`。流向不變，瞬間跳變沒有漸變，到期後瞬間還原。結果是一路到海床都均勻 4 kn，不符合剖面物理。
- `server.py:590-602`：主機可以直接設定各層流速（上限 10 kn）與 turbulence（上限 3.0，也就是 300% 擾動強度）。

### A6. 前端呈現（`simulator/viewer/app.js` 等）

- 流速箭頭：`app.js:407-408`、`app.js:563-566`，顯示 `current_here`，含陣風。
- 漂流粒子：`app.js:406-449`。在相機附近 18×10×18 m 的盒子裡放 900 顆粒子，用 `currentAt(depth)` 推動。`currentAt` 複製的是 `mean_at`（`app.js:410-418`），**沒有陣風，也沒有空間剪切**，所以畫面上的流和物理上的流不一致。可在 `index.html:86` 的 `optFlow` 關掉，預設開。
- 剖面圖：`app.js:836-867`，畫平均剖面加上 ROV 深度與當地流速。
- 海帶擺動：`environment.js:134-146`，`uFlow×1.2` 再加上和流無關的固定正弦。
- 泥沙雲會隨流漂（`world.py:542`），魚群受流影響 ×0.35（`ecology.py:101`）。這兩者是物理一致的視覺線索。
- 沒有水面波浪。只有下水動畫裡船的「gentle swell」（`deploy_intro.js:246`）。

### A7. 涵蓋洋流的測試

- `test_core.py:50-60`：浮在水面時隨流漂移（回歸測試）。
- `test_core.py:120-125`：`mean_at` 在 0、15、29.9 m 的數值。
- `test_ecology.py:108-115`：`sample_many` 連續，且批次與單點取樣結果一致。
- `test_flight_assist.py:74-97, 283-`：0.5 kn 定點、2.5 kn 推力飽和、偏航時定點。
- `test_inertial_dynamics.py:51-59`：均勻洋流中的共動一致性。
- `test_instructor.py:31-49`：洋流注入與還原。
- `test_multiplayer.py:36-39`：每 tick 只步進一次陣風。
- **沒有測試的項目**：陣風統計、擾動強度與各向異性、空間相關、近海床剖面與地形的關係、時間變化（潮汐），以及波浪（目前不存在）。

### A8. 實驗結果

**陣風時間序列**（`gust_stats.py`，單點，3600 s，dt=0.01）

| | open_water @10 m | monopile_current @12 m |
|---|---|---|
| 平均流 | 0.154 m/s（0.30 kn） | 0.837 m/s（1.63 kn） |
| 順流 σ（含剪切） | 0.033（TI 21%） | 0.267（TI 32%）；只看陣風（`at()`）是 0.241，TI 29% |
| 橫流 σ | 0.035（≈ 順流） | 0.252（≈ 順流） |
| 垂直 σ | 0.009 | 0.073 |
| 自相關 1/3/6/12/30 s | 0.86/0.65/0.42/0.21/≈0 | 0.86/0.64/0.43/0.18/≈0 |
| 順流極值 | 0.03 … 0.28 | **−0.16 … 1.96 m/s**（瞬間逆流，也會衝到 2.3 倍平均） |
| dU/dt 的 σ | 0.18 m/s²（dt=0.01） | **1.46 m/s²（dt=0.01）**、0.46（0.1 s）、0.14（1 s） |

這是單一時間尺度的 OU 過程（指數自相關，τ=6 s，頻譜 f⁻²）。它的導數是白雜訊，dt 越小 dU/dt 越大。如果直接把它拿去餵 Froude-Krylov 項，會產生假的大力：(30+15 kg)×1.46 ≈ 65 N 的雜訊。

**空間結構**（`spatial.py`，monopile，深 12 m，t=0）

- 200×200 m 範圍內流速 0.69–1.00 m/s。1 m 內的差異只有 0.005 m/s，所以在 ROV 的尺度上等於均勻。
- 剪切圖樣以固定的 1.02 m/s 往 37.6° 方向傳播，和實際流向（180°）、流速都無關。固定點上的週期是 140 s，振幅 ±18%。這是人工產物。
- 單樁周圍（D=6 m）：上游 1.5r 處 0.74 m/s，側肩 0.77，下游 1.5r（尾流區）0.78，下游 5r 0.84，**樁體內部 0.76 m/s**。沒有停滯點、沒有側肩加速、沒有尾流遮蔽，也沒有渦旋脫落。
- 近海床剖面（水深 28 m）：表層 1.8 kn → 23 m 處 1.08 → 27 m 處 0.86 → 27.5 m 處 0.41 → 27.8 m 處 0.16 → 0。距海床 1 m 以上只有線性內插，1 m 以下突然降為 0。
- 珊瑚礁地形（名目水深 14 m，地形 12.6–14 m）：在地形高點上方 0.3 m 處，邊界層不起作用，因為邊界層是對名目海床算的。

**無動力 X1 的 10 s 漂移**（`drift.py`；起始深度＝情境的 `start_pos`。「裸機」指固定平均流、無纜線、無陣風；「全模擬」指 `Simulator` 上鎖，有纜線、陣風、剪切）

| 情境 | 起始深度 m | 當地流 kn | 裸機 10 s 漂移 m | 63% 響應時間 s | 全模擬 10 s 漂移 m | ROV 端纜線拉力峰值 N |
|---|---|---|---|---|---|---|
| open_water | 2 | 0.30 | 1.08 | 3.0 | 1.30 | 2.9 |
| coral_reef | 3 | 0.46 | 1.86 | 1.9 | 2.03 | 9.3 |
| seagrass_meadow | 2 | 0.35 | 1.41 | 2.0 | 1.57 | 7.7 |
| hull_inspection | 3 | 0.57 | 2.11 | 2.6 | 2.64 | 6.1 |
| harbor_inspection | 3 | 0.72 | 3.13 | 1.1 | 3.26 | 10.3 |
| wreck_survey | 3 | 0.76 | 2.94 | 2.2 | 5.15 | 6.9 |
| tether_untangle | 10 | 0.80 | 3.53 | 1.0 | 1.13（被預纏的纜拉住） | 19.6 |
| korean_castle | 4 | 0.82 | 3.59 | 1.2 | 5.41 | 7.1 |
| jacket_inspection | 3 | 1.40 | 6.46 | 0.7 | 5.63 | 20.6 |
| random (seed 7) | 3 | 1.64 | 7.64 | 0.6 | 7.30 | 29.4 |
| monopile_current | 3 | 1.76 | 7.50 | 1.3 | 13.17 | 15.7 |
| incident_jacket | 12 | 1.85 | 8.70 | 0.5 | 9.59 | 17.2 |
| incident_current | 8 | 3.00 | 14.47 | 0.3 | 15.87 | 32.0 |
| tutorial / incident_wreck / silt / compass | — | 0 | 0 | — | ≤0.06 | ≤1.6 |

載具在 0.3–3 s 內就跟上流速，10 s 後已達流速的 93–99%。monopile 全模擬漂移幾乎是裸機的兩倍，原因是 TI 30% 的陣風把流速推到 1.5–2 倍。

**波浪量級**（`waves_fk.py`，線性波理論）

多數情境的起始深度是 2–3 m。H=1 m、T=6 s 的波浪在 3 m 深的水平軌道速度約 0.38–0.46 m/s，和整個情境的平均流同一量級。在 9 m 深的海草床，海床處仍有 0.34 m/s。流體加速度約 0.4 m/s²，對應 (ρV+m_A)·a ≈ 18 N 的週期力。本專案目前完全沒有這一項。

---

## B. 其他模擬器怎麼做

| 系統 | 洋流 | 波浪 | 作用到載具／纜線的方式 | 來源 |
|---|---|---|---|---|
| **UUV Simulator**（Gazebo） | 一個世界插件。流速大小、水平角、垂直角各有一個一階 Gauss-Markov 過程：`var = (1 − dt·mu)·var + noiseAmp·rand`，以 min/max 截斷。全域均勻，不隨深度變化 | 只有視覺 shader（`SimpleWaves.vert`，振幅 0.01） | `HMFossen` 使用 `velRel = v − v_flow`，計算阻力與 `C_A(ν_r)`；附加質量力為 `−M_A·filteredAcc`，其中 acc 是 `ν_r` 的有限差分（濾波係數 α=0.3），**所以有包含流的加速度** | `uuv_world_plugins/src/GaussMarkovProcess.cc:74-86`；`uuv_gazebo_plugins/src/HydrodynamicModel.cc:361-412`；[github.com/uuvsimulator/uuv_simulator](https://github.com/uuvsimulator/uuv_simulator) |
| **DAVE**（UUV Simulator 的延伸） | 分層（stratified）資料庫，CSV 列出「北、東、深度」，每個深度各自有 GM 過程；**潮汐**可用 NOAA 時間序列內插，或用 M2/S2/N2 調和常數，配合漲潮與退潮方向；每台載具依自身深度取得當地流（transient current） | 世界檔用 ocean 模型與視覺波浪 shader | 同 UUV 的 Fossen 模型 | `dave_gazebo_world_plugins/src/tidal_oscillation.cc:121-176`、`ocean_current_world_plugin.cc:131-147, 376-411`、`models/dave_worlds/worlds/transientOceanCurrentDatabase.csv`；[github.com/Field-Robotics-Lab/dave](https://github.com/Field-Robotics-Lab/dave) |
| **Stonefish** | 速度場可疊加：Uniform、Jet（圓形噴流）、Pipe（虛擬管流），在 `Ocean::GetFluidVelocity` 中相加 | Tessendorf FFT 波浪（GPU），可選平面水面；波高用來判斷物體是否跨出水面並計算浮力，文件說波浪與物體互動「仍在開發」 | 逐網格面計算阻力，使用面中心的當地流速 `GetFluidVelocity(fc) − (v + ω×r)`（`SolidEntity.cpp:1662,1770`），所以空間不均的流會產生力矩；推進器與 DVL 也讀當地流 | [Stonefish 環境文件](https://stonefish.readthedocs.io/en/latest/environment.html)；[github.com/patrykcieslak/stonefish](https://github.com/patrykcieslak/stonefish) |
| **HoloOcean** | 每台載具一個全域座標的速度向量，或由使用者每 tick 依位置／時間餵向量場；有向量場除錯繪圖 | 無 | 文件明寫「洋流在 Fossen 動力學下無作用」 | [HoloOcean Ocean Currents](https://byu-holoocean.github.io/holoocean-docs/v2.2.0/agents/docs/currents.html)；[HoloOcean 2.0 preview](https://arxiv.org/abs/2510.06160) |
| **MoorDyn**（纜繩／繫泊） | MoorDyn-C 的 `Currents`：0 無、1 規則網格穩態、2 規則網格動態、5 四維網格；MoorDyn-F 的 `CurrentMod` 1 = 深度、x、y 剖面表 | `WaveKin`：1 外部驅動、2 FFT 網格、3 規則網格運動學、7 成分疊加；`UnifyCurrentGrid` 把流疊加到波浪網格 | 線段有 `Ca`／`CaAx` 附加質量，輸出橫向與切向流體慣性力（流體加速度項） | [MoorDyn inputs](https://moordyn.readthedocs.io/en/latest/inputs.html) |
| **MarineVerse** | 這是 VR **帆船**模擬（Quest／Steam），不是 ROV 模擬。有風場物理，波浪可開關（「Enable Waves Motion」），Globe 模式的波浪與實際浮標同步 | 有，針對水面艇 | 不適用 | [marineverse.com](https://www.marineverse.com/vr-sailing-simulator)；[MarineVerse 10 年回顧](https://blog.marineverse.com/marineverse/2026/01/22/marineverse-10-years-of-sailing-in-virtual-reality.html) |
| **Fugro DeepWorks**（商用） | 多組 3D 流向量，「從海面到海床」的複雜剖面，水平與垂直內插；可指定強度、航向與**仰角**；任務中可修改；作用在纜線上（2012 新聞稿） | 未公開 | 未公開 | [MarineLink 2012-01-31](https://www.marinelink.com/amp/news/currents-complex-models342322) |
| **Forum VMAX**（商用） | 行銷文字：動態纜線系統、真實物體水動力、情境中的船舶與吊機動態 | 有「船舶與吊機動態」，細節未公開 | 未公開 | [Forum VMAX](https://f-e-t.com/?p=2974) |
| **GRi VROV**（商用） | 教官控制台可即時改變洋流、濁度、纜線效應並注入故障；姊妹產品 EOD Workspace 可設定「surface conditions」 | 未公開 | 未公開 | [GRi VROV 概述](https://grisim.kayako.com/article/19-virtual-remotely-operated-vehicle-overview)；[Greensea/GRi EOD](https://www.marinetechnologynews.com/news/workspace-simulator-greensea-612745) |
| **ROVsim**（Marine Simulation） | 「changing currents and visibility」 | 未公開 | 未公開 | [MarineLink](https://www.marinelink.com/news/329363) |

觀察：

1. 開源的研究型模擬器都沒有結構物尾流。Stonefish 的 Jet／Pipe 場和使用者自訂的向量場，是最接近「局部流」的做法。
2. 有**時間變化**的只有 DAVE（潮汐調和常數，加上各深度的 GM）。DeepWorks 與 VROV 靠教官手動改變。
3. 波浪大多只是視覺效果。只有 Stonefish（浮力）與 MoorDyn（纜繩運動學）把波浪接到物理上。
4. 商用訓練機的共同賣點是「剖面可在任務中改變，而且作用在纜線上」。本專案已有剖面與纜線，缺的是時間演變。

實測背景（用於校正）：

- 潮流區在峰流時的擾動強度約 10% 以上（[Bouferrouk et al. 2016, Renewable Energy](https://researchportal.plymouth.ac.uk/en/publications/quantifying-turbulence-from-field-measurements-at-a-mixed-low-tid/)）。Orkney 的 ADCP 資料顯示有大型紊流結構，且量測對儀器很敏感（[Greenwood et al. 2019, Energies 12(4):672](https://econpapers.repec.org/RePEc:gam:jeners:v:12:y:2019:i:4:p:672-:d:207291)）。
- 明渠紊流的經典比例 σv/σu ≈ 0.7、σw/σu ≈ 0.55（Nezu & Nakagawa 1993，引自教科書，本次未線上核對）。
- 作業面：VideoRay 把 1.5 kn 以上定義為強流，建議在平潮作業，並指出平潮時刻會偏離潮汐表 30–60 分鐘；船殼、橋墩與沉船後方的渦流可以當作遮蔽。IMCA SF 02/23 的改正措施要求「在駕駛介面加上洋流讀數」。以上兩點均見 `docs/reference/real-rov-research.md:110-112`。

---

## C. 缺口清單（依訓練擬真度影響排序）

### 1. 陣風模型過強、各向同性，而且整個世界同相位（高）

**現況**：monopile 的 TI 是 29–32%，橫流 σ 等於順流 σ，瞬間會逆流（−0.16 m/s），也會衝到 1.96 m/s。所有纜線節點與載具共用同一個陣風向量。OU 過程的導數是白雜訊。

**影響**：抗流懸停時的難度主要來自隨機推擠，而不是穩定的流。纜線整條同步被甩動，高估了陣風造成的纜線拉力。

**建議**：
- 預設 TI 降到 8–12%，σ 比例設為 (1, 0.7, 0.5)。
- 改用二階（平滑）GM 過程，或多個 OU 過程疊加（以 von Kármán 型頻譜為目標），讓 dU/dt 有界。
- 積分時間尺度與流速連動：T ≈ L/U，L 取水深的 0.3–0.5 倍。
- 空間上去相關：用少量隨平均流平移的傅立葉模態（Taylor 凍結紊流假說）組成場，讓纜線節點的相干性隨距離衰減。
- 把伺服器的 turbulence 上限從 3.0 降到合理範圍。

**驗證**：新增單元測試，單點長序列的 TI、σ 比例、積分時間尺度落在目標 ±20%；兩點相關係數在 L 處 < 0.4；dt=0.01 與 0.001 下 dU/dt 的 σ 收斂。以 X1 抗流定點的位置誤差 RMS 對照實測（`x1-measurement-checklist.md`）。

### 2. 沒有結構物周圍的流場：尾流遮蔽、側肩加速、渦旋脫落（高）

**現況**：單樁上游、側肩、下游的流速都相同，樁體內部也有流。

**影響**：真實作業會利用樁、船殼、沉船後方的遮蔽區，也要提防側肩的加速流與週期性橫推（6 m 樁在 0.9 m/s 下脫落週期約 33 s，1.2 m 導管架腳約 9 s）。這正是 monopile、jacket、hull、wreck 情境的核心技能，目前完全練不到。

**建議**：
- 對 `Cylinder` 疊加解析模型：上游與側面用勢流 doublet（邊界速度 2U、前緣停滯）；下游用高斯速度虧損尾流，寬度隨 √x 成長，虧損隨 1/√x 衰減；加上 St≈0.2 的交替橫向分量（Kármán 渦街）。
- `Box`／船殼／沉船用簡化的「背流遮蔽盒」加衰減。
- 物體內部回傳 0。
- 以 `world.near()` 做 broad phase，只計算附近的結構物。

**驗證**：與文獻中圓柱尾流的速度虧損曲線比較（例如 Re 10⁵–10⁶ 的實驗資料）；單元測試確認停滯點 ≈0、側肩 ≈1.6–2U、下游 5D 處虧損 30–50%、脫落頻率 = 0.2U/D；在 monopile 情境以 A/B 比較樁後懸停所需推力。

### 3. 沒有潮汐時間變化與平潮窗口（中高）

**現況**：任務期間剖面固定。唯一的時間變化是 140 s 的人工剪切圖樣，傳播方向與流向無關。

**影響**：真實作業規劃以平潮為核心。M2 振幅 1 m/s 時，平潮附近 30 分鐘內流速可變化約 0.25 m/s，流向也會反轉。目前無法練習「等平潮下水」或「流越來越強，該撤離」的判斷。

**建議**：
- 在 `CurrentProfile` 新增選填欄位：`tide`（M2 振幅與相位、漲退潮方向、可加 S2），乘在三層剖面上，或改為「潮流 + 殘餘流」。
- 允許時間加速（教學用）。
- 移除或修正剪切圖樣，讓它隨平均流平移，速度等於平均流。
- 依 AGENTS.md，這是選填協定欄位，必須同步更新 `PROTOCOL.md`。

**驗證**：單元測試確認 12.42 h 週期、零交越時流向翻轉、未提供時行為不變；前端剖面圖顯示時間軸；以 DAVE 的 `tidal_oscillation.cc` 作為對照實作。

### 4. 載具與纜線缺少流體加速度項（M_A·v̇_c 與 Froude-Krylov）（中）

**現況**：`physics.py:249-253` 自承沒有提供流場的時間與空間導數；纜線節點也沒有。

**影響**：在陣風或波浪中，真實 ROV 會被流體加速度直接推動（X1 約 (30+15 kg)·a）；目前只靠阻力傳遞，反應過慢。波浪區是 18 N 等級的週期力。

**建議**：先做第 1 項，讓陣風平滑化；再以物質導數 `Dv_c/Dt = ∂v_c/∂t + (v_c·∇)v_c` 加入 `(ρV + M_A)·Dv_c/Dt`（ρV 用排水質量，約等於 m + net_buoyancy/g）。可參考 UUV Simulator 以濾波後的 ν_r 加速度計算附加質量力的做法。纜線節點加上 `(1 + Ca)·ρA·l·a_fluid`，與 MoorDyn 一致。

**驗證**：被動中性浮力物體在振盪流中應做「隨流」運動，振幅比約 1（解析解）；在均勻穩定流中與現行結果完全相同；保留 `test_inertial_dynamics.py` 的功守恆測試。

### 5. 沒有波浪：水面軌道速度、表層區、下水與回收（中）

**現況**：沒有任何波浪，水面是硬性的 z=0 夾限（`physics.py:272-275`）。

**影響**：多數情境起始於 2–3 m 深，那裡 1 m 波浪的軌道速度約 0.4 m/s，和平均流同級。淺水的海草床在海床上仍有 0.34 m/s 的湧浪。下水與回收時穿越水面的困難（水平推進器出水、被浪拍打）也無法呈現，雖然研究報告已提到 FAQ 中「水面解鎖後原地打轉」的現象。

**建議**：
- 以線性 Airy 波，或 3–5 個成分疊加的 JONSWAP 波，提供 `wave_velocity(p, t)` 與加速度，含 `cosh(k(h−z))/sinh(kh)` 的衰減，疊加到 `sample_many`。
- 水面高度 η(x, t) 取代 z=0 的夾限，並依淹沒比例調整浮力（類似 Stonefish 的 CROSSING_SURFACE）。
- 推進器露出水面時失去推力。
- 前端水面網格使用同一組參數，避免前端與後端兩套波浪。
- 情境新增選填欄位 `sea_state`，未提供時為 0，等同現況。

**驗證**：單元測試比對色散關係與深度衰減；中性浮力球在波浪中的軌道運動；在 9 m 深處，海床上的速度符合線性理論。

### 6. 教官與伺服器的洋流注入不符物理（中）

**現況**：`instructor.py:98-102` 把三層全部設成 strength×4 kn，流向不變，瞬間跳變，到期瞬間還原。

**影響**：均勻到海床的 4 kn 不存在於自然界，瞬間跳變會讓定點控制器出現不真實的暴衝。這也和真實流況「逐漸變強」的情境不同。

**建議**：注入改為對現有剖面乘上倍率（保留形狀與邊界層），並以 30–120 s 的漸變上升與還原；可選擇讓流向旋轉（模擬轉潮）；把伺服器上限改為合理值（例如每層 ≤5 kn、TI ≤0.3）。

**驗證**：`test_instructor.py` 增加剖面形狀保持與漸變時間的測試，並保留現有的注入與還原斷言。

### 7. 近海床剖面與地形脫鉤（中低）

**現況**：剖面在三點之間線性內插，邊界層只在名目水深的最後 1 m 起作用，礁石與地形高處沒有邊界層。

**影響**：近底作業（礁、沉船、管線）的流速與實際不符。實際潮流邊界層常佔大半水深，近底剖面接近 1/7 次方律或對數律；地形突起處會加速。

**建議**：
- 用 `world.seabed_at(p)`（現在只給 `World` 用）計算離底高度 h。
- 近底用對數律或 1/7 次方律：`u(h) = u_ref·(h/h_ref)^(1/7)`，粗糙度依 biome 決定。
- 在 `sample_many` 中使用當地高度，而不是 `world.seabed_depth`（`engine.py:187`、`tether.py:161`）。

**驗證**：剖面在 0.2、1、5 m 離底高度的比值測試；在珊瑚礁地形高點上方 0.3 m 的流速應低於中層。

### 8. 前端視覺線索與物理流場不一致（中低，對 Steam 體驗影響大）

**現況**：粒子用平均剖面（`app.js:410-418, 435`），沒有陣風與空間變化；箭頭顯示含陣風的 `current_here`。兩者會不一致。海帶擺動的週期性與流無關。

**影響**：駕駛無法從畫面「讀」出陣風，而判讀流況正是訓練目標之一。這也會在畫面上出現「物理在推、粒子沒動」的矛盾。

**建議**：
- 後端在 state 中提供選填的流場低階參數（陣風向量、潮汐相位、尾流參數），前端用同一份 JS 實作取樣，或由後端提供少量網格點。
- 粒子使用 `sample` 的同一組公式。
- 海帶擺動改為由陣風與波浪軌道速度驅動。
- 依 AGENTS.md，這屬於「前端呈現層」。粒子與箭頭是真實 ROV 沒有的輔助，但水中懸浮物本來就可見，所以粒子屬於真實線索；箭頭與剖面圖則應歸在可關的輔助層。

**驗證**：瀏覽器 smoke 測試中，後端 `current_here` 與前端在相同位置取樣的差應 < 1%；截圖比較。

### 9. 情境數值偏離常見實況（低）

**現況**：
- turbulence 0.2–0.3（TI 20–30%）偏高，見第 1 項。
- random 模式的流向在三層間最多差 ±60°，表層 0–3 kn 均勻分布，TI 最高 0.4。
- incident_wreck 在 138 m 深沒有任何流（深水常有 0.2–0.5 kn 的底流）。
- 流速本身（港口 0.8 kn、離岸風場 1.8 kn、礁區 0.5 kn）大致合理。

**建議**：
- 統一 turbulence 為 0.08–0.12。
- random 模式改為以「海域型態」抽樣（港區、潮流水道、外海），各自有分布。
- 深水情境給少量底流。
- 所有數值在 PR 中標示為假設，依 AGENTS.md 的實測流程補齊。

**驗證**：以 `x1-measurement-checklist.md` 的「已知流速處不同放纜長度下的可控性」實測對照；與台灣港口、離岸風場的 ADCP 公開資料比較（本次未找到具體來源，列為待查）。

### 10. 船體上的流速只在重心取樣一次（低）

**現況**：剪切流與尾流邊緣不會產生偏航或俯仰力矩。

**建議**：做完第 2 項之後，在 4–6 個船體採樣點（例如 `hull_centres`）取樣，分別計算阻力，類似 Stonefish 的逐面計算。

**驗證**：載具橫跨尾流邊緣時應產生偏航力矩；均勻流中結果與現在相同。

---

## 實作順序建議

1. 先做第 1、6 項：只改參數與注入邏輯，風險低、收益高。
2. 再做第 3 項潮汐（選填協定欄位）與第 2 項尾流。
3. 第 4 項流體加速度項依賴第 1 項的平滑陣風。
4. 第 5 項波浪會連動前端水面與下水流程，可以獨立成一份任務書。
5. 第 8 項跟著每一項同步修改前端取樣。

所有新欄位都必須是選填，未提供時行為不變（AGENTS.md 硬性規則 1）。
