# ROV-01 × NVIDIA Omniverse SimReady OpenUSD 水下工業物理資產與「深海連線 (Operation: Deep Link)」海底電纜搶修連貫戰役技術總表

## 1. 整合架構總覽 (Executive Summary)
- **Web 端 OpenUSD 引擎**：本地 Vendored 整合 [`@huggingface/usd-web-viewer@0.2.0`](https://www.npmjs.com/package/@huggingface/usd-web-viewer)（含 `dist/esm/index.js` 與 OpenUSD WebAssembly 執行核心 `dist/wasm/usd_wasm_bg.wasm`），於 `viewer/index.html` 與獨立檢視器 `viewer/simready_preview.html` 透過原生 `importmap` 載入，支援離線與 Steam 單機封裝。
- **NVIDIA Omniverse SimReady 物理資產庫 (`nvidia/simready-assets`)**：自 Hugging Face Hub [`datasets/nvidia/simready-assets`](https://huggingface.co/datasets/nvidia/simready-assets) 嚴選 8 件通用工業設備 (`CC-BY-4.0`)，轉換為具完整 `UsdPhysics.RigidBodyAPI`、`UsdPhysics.CollisionAPI`、`UsdPhysics.MassAPI` 與 `UsdPhysics.MaterialAPI` 標註之 ASCII OpenUSD (`.usda`) 檔案，存放於 `viewer/simready_usd/`。
- **連貫四階段海纜搶修戰役 (`Operation: Deep Link — 海底主幹電纜緊急搶修連貫戰役`)**：
  依 JK 最新產品指示 (`t949u`, `t950u`)，以「海底主幹複合電纜尋纜、機械手臂夾取與懸鏈拖曳、強流下接頭盒三段式搶修鎖固、全線 400kV/100Gbps 通電脈衝與 TMS 吊籠回收」打造單一無縫海床地圖的四階段連貫遊戲體驗 (`rov01sim/cable_campaign.py` + `viewer/cable_campaign.js`)。
- **100% IP 與品牌合規 (`CORR-ROV-01`)**：
  100% 原創 `ROV-01` 開放式工業抗壓框架（深海科技青 `#06B6D4` / `#22D3EE` 與深海鈦灰 `#1E293B` 塗裝，非橘色外觀），0 外部客戶或風場名稱、0 第三方商業 ROV 品牌字樣，且零二進位 `.glb/.gltf/.obj/.fbx` 網格殘留。

---

## 2. 8 件 SimReady OpenUSD (`.usda`) 工業物理資產清單與 `UsdPhysics` 規格

| 資產編號 | 關卡 / 戰役階段 | 中文名稱 | Hugging Face `nvidia/simready-assets` 來源套件 | OpenUSD `.usda` 檔案 | 乾重 `mass` (kg) | 海水浮力修正後水中淨重 (N) | 摩擦係數 `μ_s / μ_d` | 恢復係數 `restitution` | B2B UT 測厚點 (標稱 / 實測 mm) |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`SR-IND-01`** | M1 / Stage 1 & 2 | 水下聲納校準鋼架與壓纜障礙架 | `industrial_racking_a01` | `SR-IND-01_calibration_rack.usda` | 185.0 | 1580.40 N | 0.62 / 0.48 | 0.18 | 12.0 / 11.8 mm |
| **`SR-IND-02`** | M1 / Stage 1 | 水下防撞保護籠與定位導引樁 | `bollard_ steel_a01` | `SR-IND-02_bollard_cage_post.usda` | 140.0 | 1196.05 N | 0.58 / 0.44 | 0.22 | 14.0 / 13.7 mm |
| **`SR-IND-03`** | M2 / Stage 3 | 高壓工業閘閥與海纜保護管夾總成 | `drainage_pumpSystem_a01` | `SR-IND-03_gate_valve_manifold.usda` | 310.0 | 2617.88 N | 0.68 / 0.55 | 0.14 | **`UT-SR-01`** (16.0 / 15.6 mm) |
| **`SR-IND-04`** | M2 / Stage 3 | 海底沉箱鋼構排水箱體與法蘭基座 | `steel_box_a01` | `SR-IND-04_caisson_drainage_box.usda` | 520.0 | 4388.99 N | 0.70 / 0.58 | 0.12 | 18.0 / 16.4 mm (`WARN`) |
| **`SR-IND-05`** | M3 / Stage 2 | 水下作業關節機械手臂與夾爪模組 | `robot_arm_industrial_a01` | `SR-IND-05_salvage_robot_arm.usda` | 95.0 | 797.55 N | 0.54 / 0.42 | 0.20 | 10.0 / 9.8 mm |
| **`SR-IND-06`** | M3 / Stage 2 & 3 | 海底主幹複合電纜接頭盒與搶修鞍座 | `electrical_enclosure_a01` | `SR-IND-06_power_junction_skid.usda` | 410.0 | 3456.65 N | 0.66 / 0.52 | 0.15 | 15.0 / 14.6 mm |
| **`SR-IND-07`** | M4 / Stage 4 | 海底高壓管線鞍座與 TMS 回收導引座 | `pipe_support_saddle_a01` | `SR-IND-07_pipeline_saddle_manifold.usda` | 640.0 | 5405.31 N | 0.72 / 0.60 | 0.10 | **`UT-SR-02`** (20.0 / 18.2 mm) |
| **`SR-IND-08`** | M4 / Stage 4 | 離岸重型繫纜柱與海底穩壓儲槽 | `storage_tank_industrial_a01` | `SR-IND-08_offshore_pier_bollard_tank.usda` | 890.0 | 7516.76 N | 0.74 / 0.62 | 0.09 | 22.0 / 21.5 mm |

---

## 3. 「深海連線 (Operation: Deep Link)」四階段無縫海纜搶修戰役流程

1. **Stage 1【下潛與聲納尋纜 (`STAGE_1_LOCATE`)】**：
   - 母船指揮官 (`CH-16 BRIDGE`) 發出緊急通報：B 區海底主幹光電複合電纜訊號中斷。
   - 玩家操控 `ROV-01` 依循 3 座 3D 發光聲納導引光圈 (`#22D3EE` / `#10B981`) 與聲納脈衝下潛至水深 `5.2m` 斷纜座標，全數通過後自動無縫推進至 Stage 2。
2. **Stage 2【障礙清除與機械手臂撿電纜 (`STAGE_2_RETRIEVE`)】**：
   - 斷落海纜受落石與工業鋼架 (`SR-IND-01`) 壓住。當 `ROV-01` 靠近至 `3.0m` 內，畫面中央浮現 `[TARGET LOCKED]` 鎖定準星與 `[E] / [Space] 機械手臂夾取斷落海纜` 提示。
   - 夾爪咬合海纜後，即時渲染連結海底錨點與 `ROV-01` 機械手臂前端的 **3D 動態懸鏈線海纜 (`TubeGeometry` Catenary Curve)** 與張力計 (`128.5 N ~ 240.0 N`)，拖曳至接頭盒鞍座 (`SR-IND-06`) 入座後自動進入 Stage 3。
3. **Stage 3【強流下接頭盒維修與管夾鎖固 (`STAGE_3_REPAIR`)】**：
   - 側向海流增強至 `1.2 kn`。玩家啟動定深/定艏向 PID 維持姿態，對準接頭盒 (`SR-IND-06`) 與保護管夾 (`SR-IND-03`) 執行三段式水下搶修：
     1. **Step 1/3**：高壓水刀海生物與除鏽清理 (`Bio-fouling & Rust Cavitation Jet Cleaning`)
     2. **Step 2/3**：光電接頭盒對接與 SimReady 保護管夾 `240 N·m` 扭力鎖固 (`Splice Box & Clamp Torque Lock`)
     3. **Step 3/3**：`400kV / 100Gbps` 高壓絕緣與光纖導通檢測 (`Insulation & Continuity Test`)
   - 搶修期間即時渲染水下電焊火花與空化氣泡粒子特效。
4. **Stage 4【海纜全線通電脈衝與母船吊籠回收 (`STAGE_4_EXTRACT`)】**：
   - 搶修達 `100%` 後，海底主幹電纜觸發翠綠高能光脈衝 (`SIGNAL RESTORED: 100% — 400kV / 100Gbps ONLINE`)。
   - 玩家循回收信標返航進入水下 TMS 吊籠 (`[0, 0, 2.2]`)，彈出戰役完成結算畫面（`S` 級評等、總分、懸鏈張力效率與 `DEEP_LINK_CABLE_MASTER` Steam 成就解鎖）。

---

## 4. 實機渲染驗證截圖 (`1920×1080`)
- `/workspace/rov_sim/steam_assets/deeplink_stage1_locate_sonar_rings.png`：Stage 1 聲納導引光圈下潛與母船無線電通訊 HUD
- `/workspace/rov_sim/steam_assets/deeplink_stage2_grab_and_tow_cable.png`：Stage 2 機械手臂鎖定夾取斷落海纜與 3D 懸鏈線拖曳
- `/workspace/rov_sim/steam_assets/deeplink_stage3_splice_box_repair_sparks.png`：Stage 3 強流定深下 SimReady 接頭盒與管夾三段式火花搶修
- `/workspace/rov_sim/steam_assets/deeplink_stage4_energized_pulse_and_victory.png`：Stage 4 海纜 400kV/100Gbps 全線通電脈衝與 S 級戰役通關結算
- `/workspace/rov_sim/steam_assets/simready_01_subsea_usd_scene.png`：主模擬器內建 `[F4]` SimReady OpenUSD 物理資產檢視器與 3D 場景疊加
- `/workspace/rov_sim/steam_assets/simready_02_usd_web_viewer_inspector.png`：獨立 `@huggingface/usd-web-viewer` 檢視器展示 `ROV-01` 與 `SR-IND-03` 碰撞網格、質心與 `.usda` 原始碼
