# P3：第一章：港口與船殼的工單與工具（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。完整讀 docs/story/bible.md、docs/story/chapters/chapter1.md、docs/story/mission-map.md、research_notes/遊戲設計/real_rov_jobs_missions.md，把第一章 C1-1～C1-4 做成可完整遊玩的工單（simulator/viewer/career/contracts.json 與 simulator/campaign/*.json），台詞照劇本接上無線電字幕（角色：林岑、周楷、方晴、馬力、葉理）。
需要的新工具（呈現層，資料由伺服器既有狀態而來；超出真機者註冊擬真項目）：
- 雷射比例尺量測：兩點雷射在畫面上的距離換算尺寸，可量附著物厚度與裂縫長度；載具需裝備雷射比例尺（商城已有裝備概念）。
- 船殼附著評級 0–4：拍照後選評級，交付時與場景實際值比對計分。
- LOTO 確認步驟：船殼工單下水前須無線電確認主機與推進器上鎖掛牌，未確認不得解鎖。
- C1-1 低能見度 1.5 m 變體；C1-4「交班前趕工複查」同角度重拍比對（以站點與視角容差判定），以及本章的大事件演出（有鏡頭與配樂，玩家仍用既有操作完成關鍵目標）。
- 每關 15–25 分鐘；評分以交付品質為主。
瀏覽器檢查：browser_career_smoke browser_campaign_smoke browser_results_smoke browser_procedure_smoke，並新增一支 browser_chapter1_smoke 走完 C1-1 的關鍵流程。

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
