# P5：序章改寫與角色台詞接入（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。完整讀 docs/story/bible.md、docs/story/chapters/prologue.md、docs/story/lines.csv。
- 把序章（simulator/campaign/prologue.json 與職涯序章工單）改為故事聖經的版本：舊角色名（阿禾等）全部汰換為林岑、周楷、方晴、馬力；台詞照 lines.csv（含觸發時機），進無線電字幕；語音系統已存在（simulator/viewer/audio/voice.js），以台詞文字對應語音，無語音檔時只有字幕。
- 故事聖經寫的是 24 m 工作船，但擁有者已決定作業與選單都在小艇上（見 bible.md 開頭的審查註記）：涉及吊鉤、甲板吊、控制室貨櫃的台詞改為小艇的實際做法。
- 序章結業頒發見習駕駛員執照，用 simulator/viewer/brand/licence_card.js 顯示執照卡，用 brand/chapter_card.js 的章節開場卡。
- 每關 15–25 分鐘；中止可推進但低分。
瀏覽器檢查：browser_campaign_smoke browser_results_smoke browser_career_smoke browser_brand_smoke。

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
