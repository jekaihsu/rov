# P4：第二章：養殖箱網的工單與大事件（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。完整讀 docs/story/bible.md、docs/story/chapters/chapter2.md、docs/story/mission-map.md，把第二章 C2-1～C2-3 做成可完整遊玩的工單，台詞接上無線電字幕（角色：翁慈與 YX 隊員）。
- C2-1 網衣巡檢：沿網一圈覆蓋率計分；破洞要以時鐘方位與深度回報（新的回報介面），交付比對實際位置。
- C2-2 死魚回收：夾爪抓取（YX Model V；或在 R 上掛輕夾爪——擇一並在 PR 說明理由）、放進收集籃；死魚用現有真鯛模型。
- C2-3 破網逃魚（本章大事件）：動態出現的優先破洞、魚群往破洞外逃的呈現、無線電壓力與時間窗；不加奇幻元素。
- 修正：箱網的目標點目前與出生點重疊（qysim/scenarios.py 的 aquaculture_pen 目標座標），請移到合理位置並更新測試。
- 燈光不要太亮會驚擾魚群的台詞與行為可做為呈現（魚群避光已存在於 simulator/viewer/fish_schools.js）。
瀏覽器檢查：browser_career_smoke browser_results_smoke observation_smoke，並新增 browser_chapter2_smoke 走完 C2-1 的關鍵流程。

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
