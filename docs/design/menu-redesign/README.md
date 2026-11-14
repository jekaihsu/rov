# 主選單重做（T06）截圖

1600×900、deviceScaleFactor 2，以 `simulator/tools/browser_menu_screens.py` 在軟體 WebGL（SwiftShader）下擷取；
超過 1.5 MB 的圖以 256 色調色盤重新編碼。重新產生：

```bash
cd simulator
ROV_CHROMIUM=/opt/pw-browsers/chromium python tools/run_browser_checks.py browser_menu_screens
```

視覺語言沿用飛行 HUD 方向稿 A（`docs/design/mockups/hud-a-line-instrument.png`）：細線、半透明層、大型等寬數字，
每個畫面最多一顆實心強調按鈕（簡報頁的「下水」）。背景一律是即時 3D 場景，換步驟時鏡頭平滑移動。

| 檔案 | 畫面 |
|---|---|
| `00-loading.png` | 載入進度（靜態 HTML，模組載入前就可見，不會出現空白畫面） |
| `01-title.png` | 標題畫面 |
| `02-main-gamepad-focus.png` | 主選單；以手把十字鍵移到第二項，焦點框與底部按鍵提示（Xbox 系字形） |
| `03-modes.png` | 玩法卡片：一句話說明與人數 |
| `04-hangar-x1-provisional.png` | 載具機庫：X1 標「暫定」；大數字與固定刻度能力條 |
| `05-hangar-falcon-sticker.png` | 換成 Falcon、貼上警示斜紋貼紙（即時套用在模型上） |
| `06-sites.png` | 海域卡片：預覽圖、海床深度、能見度、最大洋流、可進行的活動；背景切到焦點海域 |
| `07-briefing.png` | 下水簡報：五個大數字、任務目標、下水動畫開關、「下水」 |
| `08-training-story.png` | 訓練：劇情章節（依 `order`，依本機存檔解鎖） |
| `09-training-drills.png` | 訓練：事故演練（`category: incident`） |
| `10-training-scenarios.png` | 訓練：場景訓練，依洋流與能見度推得的難度 |
| `11-settings-fidelity.png` | 設定：擬真設定（掛載既有 `fidelity_panel.js`） |
| `12-settings-controls.png` | 設定：控制（輸入裝置、控制配置、進階手把設定、由綁定表產生的鍵位表） |
| `13-settings-audio.png` | 設定：音訊（既有音訊設定） |
| `14-settings-quality.png` | 設定：畫質（`render_quality.js`） |
| `15-settings-interface.png` | 設定：介面 |
| `16-collection.png` | 圖鑑與收藏（既有收藏面板） |
| `17-multiplayer.png` | 多人：名稱、房間碼、伺服器、房內玩家（以唯讀 `room_query` 查詢） |
| `18-pause.png` | 遊戲中暫停選單（單人：模擬暫停） |
| `19-pause-settings.png` | 暫停選單內的設定分頁 |

海域卡片的預覽圖（`simulator/viewer/menu/previews/*.jpg`，480×270，共約 100 KB）以
`simulator/tools/capture_site_previews.py` 由選單自己的 3D 場景產生。
