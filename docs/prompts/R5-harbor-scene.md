# R5：港口場景重建（Codex）

> 先完整讀 `docs/prompts/R0-common.md` 與 `docs/prompts/README.md`「所有場景的共同規則」。分支 `task/R5-harbor-scene`。

## 背景

第一章大部分在 `harbor_inspection`（港口碼頭）。擁有者：「場景的建模建得不到位。」先看現況：
`python -m qysim.server` 後開 `http://127.0.0.1:8080/?scenario=harbor_inspection&nointro`，
在水下與水面各截 6 張（1600×900）放 `docs/design/harbor-r5/before/`。

## 目標

看起來像真的商港碼頭水下：**碼頭樁（鋼管樁或混凝土方樁）成排、橫梁、防舷材、岸壁、鏈條與繫泊纜、
海生物附著（藤壺、貽貝、海藻帶，隨水深變化）、底部淤泥與垃圾（輪胎、纜繩斷頭）、能見度低時的懸浮物**。
形狀利落、硬邊、真實比例（查公開的碼頭設計資料，例如樁徑 0.6–1.2 m、間距 4–6 m），寫在 README。
水面以上：碼頭面、繫船柱、車擋、遠處的岸吊與倉庫輪廓（不得有任何品牌與真實港口的辨識特徵）。

## 作法

- 程式產生幾何（three.js，照 `structures.js`、`wind_farm.js`、`structure_materials.js` 的寫法）＋
  `scan_materials.js` 的 CC0 掃描材質（Poly Haven、ambientCG；記錄在 `models/CREDITS.md`）。
  有 Blender 的話也可以用 `cad/*.py` 產 GLB，但 GLB 必須在執行時真的被載入。
- 碰撞與伺服器幾何要和畫面一致：若 `qysim` 的 `harbor_inspection` 障礙物需更新，同步改並加單元測試
  （纜線會不會掛樁、ROV 會不會穿模）。
- 海生物附著用貼花或頂點色帶，不要每根樁一樣；用固定種子，可重現。
- 效能：遠處樁用 instancing 與 LOD；`browser_gpu_bench.py --check` 不得超預算。

## 驗證

- after 截圖同角度 6+6 張放 `docs/design/harbor-r5/after/`，附前後對照聯絡表。
- 跑：`browser_smoke browser_campaign_smoke`，以及現有涉及 harbor 的瀏覽器檢查（`--list` 找）。
- PR 描述列出參考的公開資料（文字描述）與每項素材的授權。
