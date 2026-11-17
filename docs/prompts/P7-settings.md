# P7：設定補齊（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。依 game-plan §6 第 8 點，盤點並補齊設定：語言、視野 FOV、顯示模式與解析度（桌面版）、亮度、介面縮放、色盲模式、單位（公制／英制）、按鍵與手把重綁、動態舒適（鏡頭晃動、震動強度）、幀率上限、畫質預設與自動偵測。
- 先列出現況表（已有／缺／半完成）放進 PR 描述，再補缺的；純偏好項目設 presetNeutral。
- 設定介面維持大片感風格，可用手把完整操作。
- 桌面版（simulator/desktop）的顯示模式與解析度要真的生效並保存。
瀏覽器檢查：browser_menu_smoke browser_menu_gamepad_smoke browser_hud_smoke browser_i18n_smoke browser_overlay_smoke（若 overlay 在 main 上已失敗，先在 PR 說明，順手修好更好）。

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
