# I1: X1 模型 LOD 與 draw call 優化

## 目標

降低訓練版 X1（`simulator/viewer/models/rov.glb`）的 draw call 與遠距三角形數。第三人稱相對機載多出的約 468 draw calls／486k 三角形即為此模型本身；多人房每台他人載具再畫一次。外觀品質不得低於既有 X1。

## 做法

1. `cad/pack_x1_rov.mjs`：保留 6 個 `role: rotor` 槳葉樞紐；其餘靜態網格依材質合併；輸出 LOD0／LOD1／LOD2。
2. `vehicle_models.js`：訓練版 X1 以 `THREE.LOD` 依距離切換；槳葉提到 LOD 外以免打亂 `rotorOf`；他人載具 `lod: 1` 起跳。
3. 不改 `vehicles.py`、物理或碰撞。

## 驗收

- LOD0 draw calls ≤ 40；外觀與合併前肉眼無差（差異圖）。
- LOD1 ≈ 80k、LOD2 ≈ 20k 三角形。
- 單元／Node／指定瀏覽器檢查全過；PR 附前後量測。
