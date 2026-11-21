# S1：已知小問題一次清掉（Codex）

> 先完整讀 `docs/prompts/R0-common.md`。分支 `task/S1-small-fixes`。R8（主選單）若尚未合併，不要改 `viewer/menu/` 下的檔案，
> 該類問題列在 PR「後續」。

每一項都要：先寫能重現的測試（node 或瀏覽器），再修，再證明測試通過。逐項在 PR 描述列「重現方式／修法／測試」。

1. 潛前檢查（`procedure/deck_flow.js`）進行中按 Esc 打不開暫停選單。
2. `browser_overlay_smoke` 在 main 上 z-index 失敗：查出是哪個圖層蓋住，修掉。
3. HUD 解鎖提示寫死「按 T / 手把 Y 解鎖」：PS 手把要顯示 △，鍵盤要顯示玩家實際綁定的鍵（`input/glyphs.js`、`input/hints.js`）。
   全專案搜尋其他寫死的鍵名或手把字母，一併改成依裝置顯示。
4. 第一次下潛出現兩份重複的檢查清單：只留一份。
5. 日文版看板標題換行斷在詞中間：用 `word-break: keep-all` 或手動斷點，四語都檢查。
6. 剩下未接 i18n 的玩家可見字串（`vision/overlay.js` 等）：跑 `python simulator/tools/i18n_extract.py --check --integrated`
   與全專案搜尋中文硬編碼，全部接進 `localize`，附英文、簡中、日文。
7. Pages 發布失敗不是程式問題（環境保護規則），不用處理。

跑：`browser_smoke browser_menu_smoke browser_overlay_smoke browser_playstation_smoke browser_i18n_smoke browser_onboarding_smoke`。
