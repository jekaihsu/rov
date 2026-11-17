# P1：難度三檔與開新遊戲畫面（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。完整讀 docs/prompts/L3.md 並照做，以下為更新：
- 預設難度為「真實」，Steam 版也是（game-plan §11）；三檔：簡單／標準／真實，標準是新的一檔，介於 assisted 與 real 之間。
- 開新遊戲時是全螢幕大片感畫面（參考 simulator/viewer/menu/big_picture.css／.js 與 docs/design/big-picture/），每檔有實際遊戲畫面預覽與兩三行說明，不是卡片列表；之後可在設定更改。
- 考照一律強制真實（career 已有）。
- 新的潛前檢查（procedure 的 deck 流程）：簡單＝船員代做，標準與真實＝完整做；埋缺陷只在職涯／考照／劇情。
瀏覽器檢查：browser_menu_smoke browser_menu_gamepad_smoke browser_career_smoke browser_procedure_smoke browser_i18n_smoke。

共同規則（每份都適用）：
- 先完整讀 AGENTS.md（有約束力）、docs/design/game-plan.md §9–§11、docs/prompts/README.md 最後的「所有場景的共同規則」。
- 物理、SDK 語意、協定既有欄位不得為遊戲性而改；新增協定欄位一律選填並更新 simulator/PROTOCOL.md。
- 超出真機的輔助一律註冊擬真項目，real 預設關（simulator/viewer/menu/fidelity_items.js）。
- app.js 只加最小的 import 與呼叫；新程式一行一敘述、≤120 字元、具名函式、檔頭註解；玩家看得到的字串放 STRINGS 並用 i18n 的 localize 包裝，附英文、簡中、日文。
- 新後端邏輯要有單元測試；不得刪除或放寬既有測試。
- 本機測試必跑並把指令與結果貼進 PR：cd simulator && python -m unittest discover -s tests；node --test simulator/tests/*.mjs；python ../tools/test_check_matrix.py（在 simulator 外為 python tools/test_check_matrix.py）；以及任務列出的瀏覽器檢查（python tools/run_browser_checks.py ...）。
- 前端變更附前後截圖（1600×900），放 docs/design/<任務名>/。
- 從最新 main 開分支 task/<編號>-<短名>，開 draft PR，完成後轉 ready for review。PR 標題以編號開頭。
```
