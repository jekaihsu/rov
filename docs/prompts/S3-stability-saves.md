# S3：穩定性與存檔（30 分鐘零當機、零卡關）（Codex）

> 先完整讀 `docs/prompts/R0-common.md`。分支 `task/S3-stability-saves`。

成功標準：10 次 30 分鐘遊玩零當機、零卡關，存檔保留。

1. 盤點所有存檔：localStorage 鍵（`rov.*`）、收藏資料、職涯進度、設定、學到的畫質。寫成表放 `docs/design/saves.md`：
   鍵名、版本、寫入時機、損毀時怎麼辦。
2. 每個存檔都要有版本號與遷移函式；讀到壞資料不得讓遊戲壞掉（退回預設並保留壞檔備份）。node 測試涵蓋：
   空、舊版、損毀 JSON、超大、欄位缺漏。
3. 桌面版（Electron）存檔寫到使用者資料夾的檔案（若現在只在 localStorage），寫入要原子化（先寫暫存再改名）；
   Steam 雲端存檔之後會同步這個資料夾，路徑寫進文件。
4. 長時間測試：新增 `simulator/tools/soak_test.py`，腳本駕駛連續 30 分鐘在多個場景間切換、開關選單、暫停、
   拍照、重試任務、切換語言、拔插手把（模擬 gamepad 斷線）、伺服器重啟一次；記錄記憶體（JS heap、GPU 資源數量）
   是否持續上升、錯誤、卡關。輸出報告，修掉找到的洩漏與錯誤。
5. 伺服器端：`qysim` 在客戶端斷線重連、送錯封包、長時間運行時不得崩潰；補單元測試。

跑：`python -m unittest discover -s tests`、node 測試、`soak_test.py --minutes 30`（貼報告）、`browser_smoke browser_campaign_smoke`。
