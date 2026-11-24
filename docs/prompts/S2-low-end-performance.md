# S2：低階筆電順暢（Intel UHD 620 穩定 30 fps）（Codex）

> 先完整讀 `docs/prompts/R0-common.md`、`docs/design/performance/`、`docs/ci/timings.md`、`tools/perf_budgets.json`、
> `simulator/viewer/render_quality.js`。分支 `task/S2-low-end-performance`。

擁有者：「我覺得不錯但是太卡了。」目標機器：Intel UHD 620 筆電，Chrome／Electron。成功標準：開場、序章、港口、網箱、
開放水域都 ≥ 30 fps 穩定，沒有 > 0.2 s 的卡頓（含載入場景、第一次開燈、第一次魚群出現、拍照）。

1. 量測：用 `browser_gpu_bench.py --profile` 在 SwiftShader 與（若有）真 GPU 跑每個場景，記錄 draw calls、三角形、
   貼圖記憶體、著色器編譯次數、每幀 CPU 時間分項（物理狀態合併、魚群、纜線、HUD、後處理）。寫在
   `docs/design/performance/s2-baseline.md`。
2. 找出前五大成本並處理，例如：魚群 instancing 與遠距降頻、纜線幾何每幀重建、後處理在低檔關閉、陰影、
   透明排序、HUD canvas 每幀重畫、第一次出現的著色器（`shader_warmup.js` 補齊）、GC 尖峰（每幀配置物件）。
3. 低檔位（`render_quality.js` 的最低檔）要能在不影響真實性判讀的前提下，自動降到 30 fps 以上；
   學習到的檔位存檔（`rov.quality.learned.v1`）要能在變慢時再降、變快時謹慎回升。
4. 卡頓：場景載入改成分幀、資源預熱放在黑畫面或標題卡期間。
5. 更新 `tools/perf_budgets.json`（只能變嚴，不能放寬）並讓 `browser_gpu_bench.py --check` 通過。
6. 給擁有者一份在自己筆電上量測的步驟（Chrome 開哪個網址、看哪個數字），放 `docs/design/performance/s2-owner-check.md`。

跑：`browser_smoke browser_cold_open_smoke browser_campaign_smoke`、`browser_gpu_bench.py --check`，貼前後數字表。
