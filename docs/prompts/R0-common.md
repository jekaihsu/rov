# R0：R 系列共同規則與「開場標準」（每份 R 提示詞都要先讀）

擁有者 2026-11-20 的評語：「入場動畫很好，很讚，但後面的內容都沒有長這樣。場景建模不到位，遊戲體驗不夠好，
劇情、設計、設定缺點意思，主頁面也缺點意思。」R 系列的目標是把**開場之後的整個遊戲**拉到開場的水準。

## 先讀（有約束力）

1. `AGENTS.md`（全部）。
2. `docs/design/cold-open/README.md`：這是品質標竿，**照它的作法**，不是只看結果。
3. `docs/design/game-plan.md` §6、§9–§11；`docs/design/ui-direction.md`；`docs/story/bible.md`；`docs/story/mission-map.md`。
4. `docs/reference/real-rov-research.md`；`docs/prompts/README.md` 最後的「所有場景的共同規則」。

## 開場標準（每一關、每一個畫面都要過）

開場好玩，是因為下面八件事。R 系列做的每一關都要逐條對照，PR 描述裡附一張對照表（做到／沒做到／為什麼）：

1. **一進來就有事**：30 秒內玩家就在做有意義的事。沒有一進場就要讀的長段文字或清單。
2. **一次只給一個提示**：畫面上同時最多一個操作提示，用玩家實際的按鍵或手把圖示（`input/glyphs.js`）。
3. **人在說話**：任務指示由角色用無線電講（呼號、短句、先報狀態再給指示，見 bible §5），不是系統文字框。
4. **有一個真實的危機或轉折**：每關至少一個用**既有物理**做出來的事件（纜線勾纏、洋流、混濁、能見度、
   電量、羅經偏差、障礙物……）。靠場景資料讓它可靠地發生，不改物理，不靠腳本硬塞結果。
5. **不卡關**：玩家不動時角色會提醒；每個需要玩家的段落都有時限，超過就以合理的劇情往下走（可以低分，不能卡死）。
6. **有演出但不搶操控**：開場鏡頭、地點字卡、黑邊、淡入淡出、標題卡、配樂只出現在玩家**不在操控**的時候；
   玩家一接手就回到真實設定（作法見 `viewer/story/cold_open_presentation.js`，不寫 fidelity、不寫 localStorage）。
7. **乾淨 HUD**：只顯示這一段需要的讀數，需要時才淡入（開場的 `hud` 逐步出現）。
8. **有收尾**：照片／量測回報、角色的一句評語、結算或章節卡。玩家要知道自己做得好不好、為什麼。

## 共同工程規則

- 物理、SDK 語意、協定既有欄位不得為遊戲性而改；新增協定欄位一律選填並更新 `simulator/PROTOCOL.md`。
- 超出真機的輔助一律註冊擬真項目，`real` 預設關（`simulator/viewer/menu/fidelity_items.js`）。
- `app.js` 只加最小的 import 與呼叫；新程式一行一敘述、≤120 字元、具名函式、檔頭註解；
  玩家看得到的字串用 i18n（`localize(ns, STRINGS)`、`namespaces.json`），附繁中、英文、簡中、日文，
  並通過 `python simulator/tools/i18n_extract.py --check --integrated`。
- 節奏邏輯寫成**沒有 DOM 的純函式模組**（像 `cold_open_model.js`），用 `node --test` 以假遙測逐步測試。
- 新後端邏輯要有單元測試；不得刪除、跳過或放寬既有測試。
- 不得新增廠商名稱、機型商標。素材只用原創或 CC0，記錄在 `simulator/viewer/models/CREDITS.md`。
- 效能：不得讓 `python simulator/tools/browser_gpu_bench.py --check` 超出 `tools/perf_budgets.json`。
  目標機器是 Intel UHD 620 筆電 30 fps。

## 本機驗證（PR 描述必須貼上實際指令與結果）

```bash
cd simulator && python -m unittest discover -s tests
node --test simulator/tests/*.mjs
python tools/run_checks.py --changed --tier full
python simulator/tools/run_browser_checks.py browser_smoke browser_menu_smoke <任務列出的其他檢查>
```

瀏覽器跑在慢機器上時設 `ROV_BROWSER_TIMEOUT_SCALE=3`。新玩法要附新的瀏覽器 smoke（照 `browser_cold_open_smoke.py`：
腳本駕駛真的飛完一遍，並在每個段落截圖）。**smoke 要連續跑兩次都通過**才算完成。

## 交付

- 從最新 `main` 開分支 `task/<編號>-<短名>`，開 draft PR，完成後轉 ready for review。PR 標題以編號開頭。
- 截圖（1600×900 JPEG）放 `docs/design/<任務名>/`，附一張聯絡表（contact sheet），讓擁有者一眼看完整段流程。
- PR 描述：做了什麼、開場標準對照表、驗證指令與結果、還不夠好的地方。
- 做不到或有疑慮就寫在 PR 描述，不要偷偷縮小範圍。
- 不要停在「能動」。完成後自己用截圖從頭看一遍，問自己：「擁有者看到這一關會不會說無聊？」會的話繼續改。
