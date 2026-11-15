# I4：韓國城沉船重做

在三角形與貼圖預算內重做 `korean_castle` 場址沉船外觀（回應已關閉的 A2／PR #40）。

- LOD0 ≤ 300k 三角形（不得高於現況）、LOD1 ≤ 100k、LOD2 ≤ 20k。
- 貼圖預設層 GPU 記憶體 ≤ 32 MiB，高畫質層 ≤ 96 MiB；1K 合併圖集、meshopt＋WebP。
- 不提交大型 `.blend`；由無頭 Blender 建置腳本產生模型。
- 距離場、碰撞、勾纏特徵沿用既有格式；任務目標保持可達。
- 外觀：鏽蝕、依深度的生物附著、斷口與坍塌細節；以模擬器 real 模式機載截圖驗收。
- 授權：自製；更新 `simulator/viewer/models/CREDITS.md`。
- 可單獨帶上 `cKDTree(compact_nodes=False)` 建置加速。

分支 `task/I4-korean-castle`；draft PR「I4: 韓國城沉船重做」。
