# G5 實機 GPU 效能量測

**目標**：目前所有渲染效能數字都只在雲端無 GPU 的軟體算圖（SwiftShader）與高負載機器上量過，不可信。為 Steam 版預設畫質與最低需求，需要真實 GPU 上的 frame time、draw calls、三角形與記憶體估計。

**範圍**：`simulator/tools/browser_gpu_bench.py`、`simulator/tools/_browser.py`（GPU 啟動模式）、`docs/perf/gpu-<機器代號>.md`、可選的 Electron 對照。**不修改** `simulator/viewer/` 渲染程式；要改的寫在 PR「後續」。

**要做**

1. 記錄機器規格（CPU、GPU 與驅動、RAM、OS、螢幕解析度／更新率）。
2. 以 `_browser.py` 啟動瀏覽器；實機設 `ROV_CHROMIUM`＋`ROV_BROWSER_GL=gpu`，確認硬體加速。
3. 對 performance／medium／high／ultra、各場址、onboard／第三人稱量測穩定 30 s 的 frame time（平均、p95、p99）、draw calls、三角形、GPU／JS 記憶體估計；`?nointro` 與固定姿態或回放。
4. 另量 `incident_silt` 揚沙全白與沉船開燈 2 檔。
5. 依 `simulator/desktop/` 建置／啟動 Electron，跑同樣取樣並比較。
6. 寫 `docs/perf/gpu-<機器代號>.md`：完整表、各畫質建議硬體、auto 門檻、超過 16.7 ms 的場景與原因。

**驗證**：工具在無 GPU 環境也能跑完（數字不同）；`python tools/run_browser_checks.py browser_gpu_bench` 為可選、不在預設清單。
