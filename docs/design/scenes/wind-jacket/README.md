# M1 離岸風電導管架

`jacket_inspection` 的原創通用四腿基礎。比例是訓練用途的假設，並非照片場址的工程測繪。
照片僅供目視對照，專案沒有存放照片、照片裁切或投影貼圖，也沒有真實公司標誌、場址編號或文字告示。
基底 `138c242` 的 `game-plan.md` 只有 §1–10，無需求提及的 §11；依本次使用者指示採遊戲即時畫面作背景。

## 結構與物理

斜腿延伸到水上 12 m，五層水平撐及完整交叉斜撐；方形平台、底面樑格、雙折返樓梯、中間平台、欄杆、
灰白塔底及吊桿。靠船柱、橡膠帶、爬梯與通用三角警示；水下陽極、鋼芯、J 管及固定件、灌漿樁套、
防沉板及拋石。所有硬質附件都是伺服器的既有 cylinder / box；水下薄層貝類與接頭在一致性容差內。
高畫質增加中空藤壺錐，中畫質使用較稀疏版本；依深度的附著、剝漆與鏽蝕沿用程序材質。

巡檢點與陽極隨斜腿插值，目標深度仍為 6、12、16、10 m。事故與隨機場景不變。
沖刷採 1.5 m 格網，凹部位於 32 m 原始安全底床、周圍沉積緣最高 0.45 m；物理、聲納與畫面共享高度資料。
新增水上附件保留碰撞，透過既有 `NO_WAKE_KINDS` 排除水中尾流；未改動其他場景的洋流模型。
最近表面查詢以包圍盒的距離下界排除不可能更近的方塊（近似的船殼／距離場不套用此下界），不改變回傳距離、法向或物件索引。
在本場景四個固定射線樣點上，500 次 CPU 量測由 2.00 ms/查詢降至 0.11 ms/查詢；
`query-cost.json` 記錄樣點，這不是完整模擬 tick 或 FPS 的測量。

`viewer/wind_jacket.js` 提供 NED 相機錨點 `boatApproach`、`boatLanding`、`underwaterBraces`、`intertidal`。
標題畫面採小艇仰視，主選單採水下斜撐；海面程序反光與風機遠景都由遊戲繪製。
水下使用原有透光水面，讓水線附近構件仍有輪廓。

## 重建與預算

```bash
python cad/build_wind_jacket.py
node simulator/tools/wind_jacket_report.mjs
python simulator/tools/build_menu_previews.py
cd simulator
python tools/run_browser_checks.py browser_wind_jacket_review browser_wind_jacket_onboard
```

固定 seed=1101，無頭 Blender；無 `.blend`。中間檔僅寫入忽略追蹤的 `simulator/output/wind-jacket/`。
需 Python 專案依賴、Blender、Node/npx，首次 npx 需網路。glTF Transform CLI 固定 4.2.1。
提交的兩個小型 GLB 是可供美術交換的 meshopt＋WebP 輸出；**遊戲仍使用碰撞資料生成網格，不載入這兩個 GLB**。
兩者不是相同的細節層：GLB 不包含遊戲著色器附著、生物實例及海面，不能以 GLB 數字替代遊戲預算。

| 遊戲結構 | 水下三角形 | 水上三角形 | 視錐裁切前 draw calls |
|---|---:|---:|---:|
| 低 | 15,856 | 6,628 | 9 |
| 中 | 83,980 | 8,860 | 11 |
| 高 | 211,616 | 14,986 | 66 |

跨越水線的三角形保守計入兩側。結構五張 256² RGBA 程序貼圖含 mip 上限 1.67 MiB。
表格不包含載具、魚、海床、遠景和後製；完整幀的 draw calls 另見 `render-report.json`。
`live-asset-report.json` 為遊戲結構實測；`export-asset-report.json` 為 GLB 大小、幾何與貼圖報告。
單一 GLB < 0.4 MB；提交衍生資產是為了離線檢視及重建比對，沒有新增 >2 MB 資產。

## 遊戲截圖

- [main 修改前，同鏡位](before-surface.jpg)（`138c242`）
- [小艇仰視](surface-approach.jpg)、[靠船側](surface-landing.jpg)、[潮間帶](intertidal.jpg)
- [真實模式機載開燈](onboard-lit.jpg)、[關燈](onboard-dark.jpg)

水面照是遊戲內自由相機；機載照透過固定重播放置載具，使用實際機載相機、照明與 real fidelity，並非飛行到達的錄影。
機載截圖隱藏診斷用線框球（保留 HUD、目標標記及原有光學）；開燈採第 1 檔。
曝光、重播機位與檔案大小見 `onboard-report.json`。原場景比較可參照上層目錄的
`jacket_inspection-onboard-before.jpg` 與 `jacket_inspection-third-before.jpg`（不是同鏡位 A/B）。

## 驗證

- Node：`node --test simulator/tests/*.mjs`，211/211 通過。
- Blender：同一命令連續重建兩次，高、低 GLB SHA-256 完全相同。
- `cd simulator && python tools/run_browser_checks.py browser_smoke observation_smoke browser_tether_smoke browser_menu_smoke`
  最後一輪 4/4 通過（70.6、8.0、5.8、45.1 秒），未修改既有測試。
  前兩輪 smoke 曾在燈光同步逾時（60／120 秒）；單獨重跑曾通過，最後完整清單也通過。
- `browser_wind_jacket_review browser_wind_jacket_onboard`：2/2 通過，含 console shader 錯誤檢查。
- `python simulator/tools/check_changed_js.py origin/main`、`git diff --check`：通過。
- `cd simulator && python -m unittest discover -s tests`：475 項，640.610 秒，OK；含場景一致性測試。

## 審查限制

此版是程序建模的通用設施，不是實際風場的數位分身。附著生物以程序色帶、中空藤壺與既有軟體生物表現，
沒有掃描材質或物種級美術資產。報告中的完整幀時間是在共享 CPU／SwiftShader、1600×900 下量得，
不能當作實體 GPU 的 FPS 保證；尚需實機美術與效能審查。
