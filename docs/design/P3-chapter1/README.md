# P3 · 第一章工單與工具

Career 資料對齊故事聖經第一章（港口與船舶／交班窗口）。截圖與煙霧測試證據可放本目錄。

## 主線工單（C1-1～C1-4）

| 契約 id | 工單 | 情境變體 | 工具／閘門 |
|---|---|---|---|
| `c1_pier_level2` | YX-HB-024 Level II 抽樣 | `harbor_inspection_turbid`（vis ≈ 1.5 m） | 雷射比例尺；3 樁 × 3 高程；`truth_cm`／`growth` |
| `c1_hull_fouling` | YX-HL-008 船殼附著評級 | `hull_inspection_berth`（vis ≈ 3 m） | `lotoBeforeUnlock`；評級 0–4；niche＋平底航線 |
| `c1_dropped_object` | YX-SR-003 港內掉落物 | `sonar_search` | 成像聲納；標記／可選夾爪掛繩；30 分軟逾時敘事 |
| `c1_signoff_exam` | YX-HB-031 交班前趕工複查 | `harbor_inspection_signoff`（vis ≈ 4 m） | 同角度 `compare`＋`reference`；可選未列異常；發 `grade2` |

前置：`c1_pier_level1`（青嶼港務局 Level I）仍為第一章入口。支線 CP／UT 保留，客戶名改青嶼／北灣。

## 場景變體

`scenarios.py` 以 clone pattern 註冊：`harbor_inspection_turbid`、`harbor_inspection_signoff`、`hull_inspection_berth`。幾何與物理同基底場景，只改能見度與簡報。

## 對照腳本

- 故事：`docs/story/chapters/chapter1.md`
- Campaign 骨架：`simulator/campaign/harbor_signoff.json`（林岑／周楷／葉理／方晴／馬力）
