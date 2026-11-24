# S5：預告片錄製工具（Codex）

> 先完整讀 `docs/prompts/R0-common.md`、`docs/store/steam/trailer.md`（80 秒商店預告分鏡）。分支 `task/S5-trailer-capture`。

擁有者要兩支預告：商店 80 秒（照 trailer.md）與一支 demo 剪輯。這個任務做**能重複產生預告素材的工具**，不是剪片本身。

1. `simulator/tools/trailer/`：用 Playwright 驅動遊戲，依 JSON 分鏡（場景、時間、攝影機路徑、ROV 腳本駕駛輸入、
   HUD 開關、天候）逐幀錄製 1920×1080、60 fps 的 PNG 序列或無損影片（固定時間步：暫停即時時鐘、每幀推進 1/60 s，
   確保畫面不卡）。呈現層要支援「錄影模式」：隱藏除錯資訊、固定隨機種子、最高畫質。
2. 攝影機路徑：關鍵影格＋平滑插值（Catmull-Rom），可指定跟隨 ROV、環繞、固定。
3. 依 trailer.md 寫好每個鏡頭的 JSON；開場那段可直接重用倒敘開場。
4. 用 ffmpeg 把序列組成影片（不提交影片與 PNG，只提交工具與分鏡 JSON）；輸出到 `output/trailer/`。
5. 每個鏡頭輸出一張代表畫面（壓縮 ≤ 300 KB）放 `docs/design/trailer/`，讓擁有者先審分鏡。
6. 使用說明 `simulator/tools/trailer/README.md`：在一般電腦上怎麼跑、要多久、需要什麼。

跑：工具的單元測試（插值、分鏡解析）、錄一個 5 秒的測試鏡頭證明可用、`browser_smoke`。
