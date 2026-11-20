# R6：貨輪船殼與養殖網箱場景重建（Codex）

> 先完整讀 `docs/prompts/R0-common.md` 與 `docs/prompts/README.md`「所有場景的共同規則」。
> 可與 R5 同時進行。分支 `task/R6-hull-pen-scenes`。

## 先拍現況

`hull_inspection` 與 `aquaculture_pen` 各在水下截 6 張（1600×900），放 `docs/design/hull-pen-r6/before/`。

## 貨輪船殼（`hull_inspection`）

- 真實的散貨船或貨櫃船水線下：平底、舭龍骨、海底門（sea chest）格柵、陰極保護陽極、船殼漆分界、水尺標記
  （數字可以，不得有真實船名或公司）、焊道與板縫、生物附著由水線往下變化、局部鏽蝕與塗層剝落。
- 船尾：舵、螺槳（R0 的「刀狀弧度葉片」要求同風機葉片：葉片有扭轉與弧度，不是平板）、艉軸。
- 比例照公開的船舶資料（例如 180 m 級散貨船吃水約 10 m）；ROV 只會看到局部，所以近看細節優先。

## 養殖網箱（`aquaculture_pen`）

- 真實的圓形 HDPE 浮框網箱：雙浮管、扶手、網衣（看得出網目，遠處退成半透明）、沉子環或配重、繫泊纜與浮球、
  網衣上的附著與破洞（任務要用）。網衣會隨洋流鼓起（只做呈現；若伺服器幾何也要動，另開說明）。
- 魚群用既有 `fish_kit.js`／`pen_life.js`，密度與游法像養殖鮭魚（繞圈、成群）。

## 共同

- 程式產生幾何＋CC0 掃描材質（`scan_materials.js`），或 Blender 產生並真的載入。
- 碰撞與伺服器障礙物要和畫面一致，必要時更新 `qysim` 並加單元測試。
- 效能預算同 R0。after 截圖同角度放 `docs/design/hull-pen-r6/after/`，附前後聯絡表。
- 跑：`browser_smoke browser_campaign_smoke` 與 `--list` 中涉及這兩個情境的檢查。
