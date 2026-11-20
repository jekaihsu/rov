# R1：序章拉到開場水準＋共用劇情導演（Codex）

> 先完整讀 `docs/prompts/R0-common.md`。分支 `task/R1-prologue-director`。

## 背景

開場（`viewer/story/cold_open*.js`）是目前最好的一段：純函式節拍機＋呈現層＋無線電＋真實事故。
開場最後一張卡是「三個月前」，接著進序章；擁有者說「後面的內容都沒有長這樣」。
序章另有一份未完成的草稿 PR #101（分支 `task/p5-prologue`，P5：角色改名、台詞、見習執照卡），停在 11/17。

## 要做的事

### 1. 共用劇情導演（先做）

把開場導演的通用部分抽成 `viewer/story/beat_director.js`（純函式、無 DOM）與 `viewer/story/beat_stage.js`（呈現層）：

- 節拍以資料描述：進入條件（遙測路徑＋比較，與 campaign 的 `condition` 同語法）、時限、閒置提醒、
  逾時去向、無線電台詞 key、唯一提示、HUD 顯露清單、演出（黑畫面、黑邊、開場鏡頭、地點字卡、標題卡、配樂 cue）。
- 呈現層沿用開場既有的黑邊、字卡、HUD 漸顯、`cold_open_presentation.js` 的演出覆寫（推廣成 `story/cutscene_look.js`，
  開場改用它）、`audio/music.js` 的過場曲。
- 開場改成用這個導演跑，**行為不變**：`node --test simulator/tests/test_cold_open*.mjs` 與 `browser_cold_open_smoke` 照過。
- campaign JSON 加選填欄位 `beats`（有就用導演，沒有就照舊的 nodes 流程），更新 `simulator/campaign/schema.json`。

### 2. 序章重做

- 先把 PR #101 的分支合進你的分支（`git fetch origin task/p5-prologue && git merge FETCH_HEAD`），讀它的 PR 描述與審查評論，
  吸收角色、台詞、執照卡的成果；有衝突以 `docs/story/bible.md` 為準。完成後在 PR 描述註明「取代 #101」。
- 序章（`simulator/campaign/prologue.json`，`tutorial_pool`）用導演重寫，對照開場標準八條。建議節奏（可調，理由寫在 PR）：
  1. 黑畫面＋字卡「三個月前 · 公司訓練池」→ 開場鏡頭：小艇／池邊、ROV 入水。
  2. 馬力帶飛：一次教一個動作（前進、轉向、上升下降），每個動作都有一個**要飛去看的東西**（池底標記、牆上編號），
     不是空飛。
  3. 一個小轉折：例如定深關掉時往上飄、纜線被自己壓到、燈照到池壁過曝要調；用既有物理與設定，不改物理。
  4. 結業：拍三個指定標記 → 林岑一句評語 → 見習執照卡（`brand/licence_card.js`）→ 第一章章節卡。
- 每段都有閒置提醒與時限。整關 10–15 分鐘。
- 潛前檢查（`procedure/deck_flow.js`）若出現在序章，改成**有意義**的 1–2 個檢查（擁有者嫌「一直點」），其餘交給角色口述；
  詳細檢查留在訓練模式。

## 驗證

- 新增 `simulator/tools/browser_prologue_smoke.py`：腳本駕駛飛完整個序章，每段截圖，連跑兩次通過。
- 加跑：`browser_cold_open_smoke browser_campaign_smoke browser_career_smoke browser_onboarding_smoke browser_results_smoke`。
- 截圖放 `docs/design/prologue-r1/`，附聯絡表。

## 不要做

- 不改第一、二章（R2、R3 做）。不改主選單（R8 做）。
