# S2 基準量測（低階筆電順暢）

量測日期：2026-11-21（機器本地 UTC；使用者時區 Asia/Taipei = UTC+8）。
機器：雲端軟體 GL（SwiftShader），**幀率不可代表 UHD 620**；計數（draw calls、三角形、貼圖 MB、pass）在軟體與實體 GPU 上意義相同。

指令：

```bash
cd simulator
python3 tools/browser_gpu_bench.py --profile --attribute \
  --sites cold_open_jacket,harbor_inspection,aquaculture_pen,open_water \
  --tiers performance,medium --views onboard,third --duration 3 \
  --machine s2-baseline
```

完整 JSON：`simulator/output/gpu-bench/s2-baseline/profile.json`。

## 前五大成本（改動前，performance 機載／潛航）

依主執行緒 JS 分組與函式取樣（不含 SwiftShader 的 `(program)` GL 時間）：

| # | 成本 | 證據（代表場景） | S2 處理 |
|---|---|---|---|
| 1 | **HUD 儀表 canvas 每幀重畫** | `drawHeadingTape` 常為第一名（0.3–0.7 ms）；HUD/DOM 合計 1–2 ms／幀 | 羅經／深度／姿態改 20 Hz（小地圖已 15 Hz） |
| 2 | **網箱網片逐頂點更新** | `updatePenNet` + `sampleGrid`：aquaculture_pen 環境組 2.3–2.5 ms／幀 | 網片改 12 Hz |
| 3 | **纜線 Tube 每幀重建** | `cable.update` 0.2–0.4 ms；240×8 頂點 + `computeBoundingSphere` | 低檔 96×5、便宜 AABB、管體 20 Hz |
| 4 | **魚群／遠距卡片每幀運動** | `updateSchoolMotion` / `writeSchool`；pen 還有 GC（placer 每幀配置） | 遠距 12 Hz、placers 重用、去掉 `subarray` |
| 5 | **場景同步建置 + 著色器首次編譯** | `buildWorld` 一次做完；aquaculture third 視窗內 `compilesInWindow: 2` | `Environment` 分幀 `finishHeavy`；黑畫面／標題卡強制預熱燈光與魚 |

其餘：medium 光學後製在 UHD 上本就應關（`startsLow` → performance 外觀）；本輪把自動檔的目標改成穩定 ≥30 fps（`slowFps=28`），避免 35 fps 仍被當「太慢」一直降。

## 計數表（改動前）

| 場景 | draws | 三角形 | pass | 全螢幕 | 貼圖 MB | programs | JS ms | script ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| menu:performance | 53 | 93954 | 1 | 0 | 3.2 | 16 | 1.3 | 1.47 |
| menu:medium | 53 | 97986 | 1 | 0 | 16.8 | 16 | 1.4 | 1.89 |
| intro:cold_open_jacket:performance | 136 | 201815 | 1 | 0 | 43.5 | 41 | 7.0 | 6.03 |
| dive:cold_open_jacket:performance:onboard | 45 | 35522 | 1 | 0 | 23.2 | 28 | 5.4 | 5.22 |
| dive:cold_open_jacket:performance:third | 80 | 115776 | 1 | 0 | 26.5 | 32 | 6.6 | 6.72 |
| dive:harbor_inspection:performance:onboard | 58 | 35082 | 1 | 0 | 14.5 | 26 | 4.6 | 4.35 |
| dive:harbor_inspection:medium:onboard | 63 | 82654 | 5 | 4 | 59.6 | 39 | 7.9 | 7.27 |
| dive:aquaculture_pen:performance:onboard | 44 | 104232 | 1 | 0 | 16.5 | 25 | 9.5 | 9.28 |
| dive:aquaculture_pen:performance:third | 87 | 185658 | 1 | 0 | 16.5 | 30 | 15.1 | 13.68 |
| dive:open_water:performance:onboard | 48 | 50582 | 1 | 0 | 14.5 | 27 | 5.3 | 4.93 |
| dive:open_water:performance:third | 84 | 131604 | 1 | 0 | 16.5 | 32 | 6.4 | 6.44 |
| dive:open_water:medium:onboard | 53 | 56666 | 5 | 4 | 46.3 | 35 | 8.5 | 7.39 |

## CPU 分項（改動前，ms／幀，取樣 profiler）

| 場景 | HUD/DOM | 纜線 | 魚 | 環境 | 後製 | app 幀迴圈 |
|---|---:|---:|---:|---:|---:|---:|
| cold_open_jacket performance onboard | 1.45 | 0.27 | 0.30 | 0.31 | — | 0.49 |
| harbor performance onboard | 1.07 | 0.31 | 0.18 | 0.23 | 0.09 | 0.51 |
| aquaculture_pen performance onboard | 1.81 | 0.20 | 0.13 | **2.53** | 0.19 | 1.34 |
| open_water performance onboard | 0.95 | 0.15 | 0.28 | 0.16 | 0.04 | 0.48 |

## 自動畫質（UHD 620／`startsLow`）

| 項目 | 改動前 | S2 |
|---|---|---|
| 起始外觀 | performance（光學關） | 同左 |
| 起始解析度比 | 0.85 | **0.75** |
| floor / ceiling | 0.6 / 0.9 | **0.5 / 0.85** |
| 判定慢／快 | 50 / 58 fps | **28 / 36 fps**（目標穩定 ≥30） |
| 回升穩定時間 | 8 s | **10 s**（更謹慎） |
| 學習鍵 | `rov.quality.learned.v1` | 同左，另記 `slowFps` |

## 真實性判讀

關閉／降頻的都是**呈現層**：儀表重畫率、網片擺動取樣、纜線管體細緻度、遠距魚剪影更新率、場景美化物件分幀載入。物理、RC 語意、SDK、協定欄位未改。

## 前後對照（同機 `--check` 場景，SwiftShader）

| 場景 | draws 前→後 | 三角形 前→後 | 貼圖 MB 前→後 | JS ms 前→後 |
|---|---:|---:|---:|---:|
| menu:medium | 53 → 53 | 97986 → 97986 | 16.8 → 16.8 | 1.4 → 1.5 |
| open_water performance onboard | 48 → 48 | 50582 → **47702** | 14.5 → 14.5 | 5.3 → **4.1** |
| open_water performance third | 84 → 84 | 131604 → **128724** | 16.5 → 16.5 | 6.4 → **5.8** |
| open_water medium onboard | 53 → 53 | 56666 → **54746** | 46.3 → 46.3 | 8.5 → **7.8** |
| harbor medium onboard | 63 → 63 | 82654 → **80734** | 59.6 → 59.6 | 7.9 → 6.9 |
| cold_open performance onboard | 45 → 45 | 35522 → **32642** | 23.2 → **17.9** | 5.4 → **4.0** |
| cold_open performance third | 80 → 80 | 115776 → **112896** | 26.5 → **21.2** | 6.6 → **5.1** |

三角形下降主要來自纜線管體分段（240×8 → 96×5／160×6）；JS ms 下降來自 HUD／網片／魚群／纜線降頻。SwiftShader 的 fps 仍遠低於真機，僅作同機對照。

`browser_gpu_bench.py --check`（收緊後的 `simulator/tools/perf_budgets.json`）：**PASS**。
