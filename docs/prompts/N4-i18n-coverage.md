# N4：新畫面接入四語（Codex／Cursor）

```
你負責把 ROV 模擬器「ROV Solution」（GitHub：jekaihsu/rov）新加的畫面接上既有的多語機制。
從最新的 main 開分支 task/N4-i18n-coverage。完整讀 AGENTS.md、simulator/viewer/i18n/README.md、docs/i18n/follow-up.md。

範圍（依序）：
1. simulator/viewer/career/（含 contracts.json、licences.json、equipment.json，需要先設計鍵值方案，比照 PROTOCOL.md 對劇情文字的提議）
2. simulator/viewer/brand/
3. simulator/viewer/procedure/（含 deck_steps.js、crew_radio.js 的台詞）
4. simulator/viewer/menu/big_picture.js、simulator/viewer/play/ 尚未覆蓋的字串
5. docs/i18n/follow-up.md 列出的其餘模組

規則：
- 用 localize(ns, STRINGS) 包裝，每個命名空間加進 namespaces.json；繁中是原文，翻譯英文、簡體中文、日文。
- 簡體中文要照中國大陸用語重寫，不是逐字轉換（例：簡報→简报不能變成演示文稿；離線→离线；模擬器→模拟器）。
- 術語與既有翻譯一致（tether／テザー、DVL、定深 depth hold／深度保持）；機型名「YX Model R/O/V」與船名不翻。
- 英文要處理單複數（1 site／2 sites）。
- 不得改動遊戲邏輯；camera_rig.js 與 state_buffer.js 不得加相對路徑 import。

驗收（PR 描述要貼指令與結果）：
python simulator/tools/i18n_extract.py --check --integrated
cd simulator && python -m unittest discover -s tests
node --test simulator/tests/*.mjs
python tools/run_browser_checks.py browser_i18n_smoke browser_i18n_runtime browser_career_smoke browser_procedure_smoke browser_menu_smoke
並附四種語言的主選單、委託看板、潛前檢查、結算截圖（1600×900）。開 draft PR，完成後轉為 ready for review。
```
