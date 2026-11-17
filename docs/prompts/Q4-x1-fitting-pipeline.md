# Q4：X1 實測資料的自動擬合管線（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。擁有者之後會照 docs/reference/x1-measurement-checklist.md 帶回 X1 實測（影片、計時、App 截圖、可能的遙測紀錄）。現在就把管線準備好，資料一到就能出參數。
1. 讀 simulator/tools/sysid/（已有 core.py、import_data.py、synthetic.py），補齊：
   - 從計時表（CSV：軸向、檔位、通過兩標記的時間、距離）推極速；從鬆桿影片逐格標記點推滑行距離與時間常數；從原地旋轉計時推最大偏航率。
   - 從 App 錄影的 OSD（深度、航向）逐格讀值的輔助工具（半自動：人工確認框選區域即可）。
   - 擬合：用現有 sysid 的方法對 x1 的質量／附加質量／阻尼／推力上限做最小平方擬合，輸出參數、信賴區間與殘差圖。
2. 用 synthetic.py 產生「假實測」資料做端到端測試：已知參數 → 合成量測 → 擬合 → 回收參數在容差內。
3. 產出 docs/reference/own/README.md 的資料格式說明（繁中，給擁有者與同事照著記錄），以及一個 python -m tools.sysid fit-x1 <資料夾> 的指令，輸出 Markdown 報告與建議的 vehicles.py 修改（只產出建議，不自動改）。
4. 不改任何 X1 參數（資料還沒來）。

共同規則：
- 先完整讀 AGENTS.md（有約束力，特別是第 5、6、8 條與「X1 專屬參數目前都是暫定值」）、docs/prompts/README.md 最後的「所有場景的共同規則」。
- 不得改動 SDK 語意與協定既有欄位；任何參數都要標明來源等級（measured／published／estimated）與出處，不得把其他機型或廠商宣稱的數字當成 X1 的事實。
- 新素材只接受 MIT／BSD／Apache／zlib／CC0／公有領域，記入 simulator/viewer/models/CREDITS.md；不得新增廠商名稱、商標或其設計外觀。
- 本機測試必跑並把指令與結果貼進 PR：cd simulator && python -m unittest discover -s tests；node --test simulator/tests/*.mjs；python ../tools/test_check_matrix.py；以及任務列出的瀏覽器檢查（python tools/run_browser_checks.py ...）。
- 從最新 main 開分支 task/<編號>-<短名>，開 draft PR，完成後轉 ready for review。
```
