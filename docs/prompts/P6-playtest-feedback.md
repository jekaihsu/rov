# P6：試玩回報工具（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。同事要開始試玩，需要一鍵回報問題：
- 遊戲中按 F8（手把：Share＋△，加入 input/bindings.js 並可重綁）或暫停選單「回報問題」：擷取目前畫面、最近 60 秒的狀態摘要（情境、擬真設定、畫質、裝置與手把 id、幀率統計、伺服器日誌行、主控台錯誤）、玩家輸入一句描述與分類（畫面／手感／當機／文字／其他）。
- 桌面版存到使用者資料夾 reports/<時間>/（PNG＋JSON），瀏覽器版下載為 zip；選單提供「開啟回報資料夾」（桌面版）。
- 不收集任何個資；不自動上傳。
- 附一份 docs/playtest/README.md（繁中）：給同事的試玩說明——怎麼安裝、PS 手把五分鐘清單的連結、怎麼回報、回報檔案在哪。
瀏覽器檢查：browser_menu_smoke browser_hud_smoke browser_menu_gamepad_smoke，並新增 browser_feedback_smoke。

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
