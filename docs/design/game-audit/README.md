# 遊戲化稽核：新 Steam 玩家今天看到什麼（2026-11-15）

研究文件，不改產品程式。目的：在「物理與 SDK 不動、`real` 預設等同真機」的前提下，列出要讓它像一款完整、
精緻的 Steam 遊戲還缺什麼、哪裡壞了。遊戲化只能落在控制輔助層與前端呈現層（見 `AGENTS.md`）。

## 方法

- `main` @ `c17e7fd`。`python -m qysim.server` 起在空閒埠，Playwright（`tools/_browser.py`，
  `ROV_CHROMIUM=/opt/pw-browsers/chromium`，SwiftShader 軟體繪圖）以 1600×900、乾淨 localStorage（等同首次啟動）
  逐步點選。Steam 預設以 `?fidelity=assisted` 模擬，另跑一次 `?fidelity=real`。
- 走過：載入、標題、主選單、玩法／載具／海域／簡報、訓練三個分頁、設定五個分頁、圖鑑、多人、暫停與暫停設定、
  有下水動畫的輔助模式潛航、真實模式潛航、序章（以腳本輸入一路打到完成）、場景訓練「開放水域熟悉」、
  海洋探索與工程（接一張巡檢委託）、速覽卡、視角切換、拍照、講評回放（`debrief/fixtures/debrief_smoke.json`）。
- 所有階段 0 個 `pageerror`；console 只有 SwiftShader 的 `GPU stall due to ReadPixels` 警告。
- 走查腳本未提交（一次性工具，放在本機暫存區）；截圖為 1600×900 JPEG，每張 ≤ 300 KB。

### 載入時間（本機、軟體繪圖；GPU 機器應更快，比例可參考）

| 量測 | 秒 |
|---|---|
| 開網址 → 選單可操作（冷啟動，第一次） | 3.7 |
| 開網址 → 選單可操作（之後每次） | 0.8–1.0 |
| 按「下水」→ 載具可操作，下水動畫關 | 3.0–8.5 |
| 按「下水」→ 載具可操作，真實模式（含潛前流程） | 12.8 |
| 按「下水」→ 載具可操作，輔助模式＋下水動畫（預設開） | 35.9 |
| 序章從開始到完成（腳本輸入，零猶豫） | 101.5 |

選單本身很快；`00-loading` 進度畫面在本機根本看不到（約 0.2 s 就過去）。

## 痛點（依對 Steam 玩家的嚴重度排序）

標記：**壞**＝現有功能行為錯誤或互相矛盾；**缺**＝沒有做。

### S1：會直接導致退款或負評

1. **只有繁體中文，且 OSD 夾雜英文與內部代號**（缺＋壞）。沒有語言選項，T09 未開始（無 `viewer/i18n/`）。
   畫面上同時出現 `MOTORS LOCKED — SPACE TO ARM`、`fish_school 100%`、`T1 HORIZONTAL`、`ROV_USA`、
   `Oracle · 模擬真值 · 636.0 ms · 10 Hz`，以及簡體用語「手柄」混在繁體介面中（`story/campaign.js`、速覽卡）。
   截圖：`24-real-first-frame.jpg`、`28-story-first-task.jpg`、`44-peek-keys.jpg`。
2. **第一分鐘是一片空藍，沒有目標、也沒有東西看**（缺）。自由探索「珊瑚礁」生成在離底 11 m、場景訓練離底 23 m，
   機載畫面看不到海床或任何生物；輔助模式右上角寫「定點輔助・未生效」（DVL 對底距離超出範圍，行為正確但玩家看不懂），
   定深預設關，ROV 正浮力，放手就慢慢浮向水面（2.9 → 0.1 m）。真正好看的東西（船、吊放、礁區）都在畫面外。
   截圖：`14-assisted-first-frame.jpg`、`15-assisted-flying.jpg`、`31-scenario-hud.jpg`。
3. **預設鍵位對一般玩家是錯的**（壞／缺）。預設配置 ROV_USA（`control_layout.js:5`）下「前進」是 ↑/↓，
   W/S 是俯仰（`qysim/rc.py:21` `pitch: left_ud`），A/D 是轉向、E/Q 升降、C/Z 橫移；照 FPS 習慣按住 W 4 秒，
   只有 0.3 kn 漂移並一路上浮。鍵位表列的是通道名（「左桿上下 W S」）而不是動作（前進、上浮）。
   沒有鍵盤改鍵；手把改鍵是在文字框輸入 `b3`、`a1~` 這種原始代碼（`input/settings.js:154`）。
   截圖：`10-settings-controls.jpg`、`44-peek-keys.jpg`。
4. **沒有獎勵迴圈**（缺＋壞）。無貨幣、無經驗、無星等、無最佳成績、無商店。劇情 `reward` 節點會存
   `first_dive`、`harbor_badge` 等（`qysim/campaign/__init__.py:221`），但前端從不顯示；「解鎖」形同虛設——
   Falcon 與「潛水旗」貼紙一開始就能在機庫選（`05-hangar.jpg`、`33-hangar-falcon-sticker.jpg`），
   劇情卻說要完成章節才解鎖。Steam 成就目錄有 15 項（`desktop/steam/achievements.json`），
   `preload.cjs` 也有 `steamEvent()`，但整個 viewer 沒有任何呼叫者，成就永遠不會解開。
5. **任務結束沒有結算畫面，是死路**（缺）。序章完成只剩一句無線電「任務完成。回到章節選單，準備下一次下潛。」
   沒有按鈕、沒有成績、沒有「下一章」；玩家得自己 Esc → 返回主選單 → 劇情與教學（`50-story-complete.jpg`）。
   場景訓練完成是 `app.js:965` 的一條橫幅（分數＋扣分）。後端其實有完整資料（用時、碰撞、峰值張力、扣分明細）。
6. **開發者畫面外露**（壞）。按「下水」後約 1.5 s 會閃出「未連線到模擬器……`python -m qysim.server --scenario
   jacket_inspection`」面板（`index.html:152`，`13-intro-1.jpg`）；多人畫面要玩家填 `ws://127.0.0.1:…`；
   簡報顯示隨機房間碼；輔助模式預設開著 AI 疊圖的除錯列（Oracle、延遲毫秒）；
   真實模式與序章第一句台詞寫著「暫定，待實測」（`24-real-first-frame.jpg`、`campaign/prologue.json` 第一則 `predive_brief`）。

### S2：明顯的粗糙與困惑

7. **HUD 元件互相重疊**（壞）。右上角模式膠囊與「鏈路／功率／溫度」膠囊在「馬達鎖定」時疊字
   （`27-story-radio.jpg`、`31-scenario-hud.jpg`）；劇情無線電壓住航向帶與 AI 列；檢查點圓環壓住下緣讀數
   （`31-scenario-hud.jpg`）；AI 方框壓住深度尺（`15-assisted-flying.jpg`）；追蹤視角仍畫機載的十字與俯仰梯
   （`46-camera-v.jpg`）；任務提示的鍵帽與文字重疊（`28-story-first-task.jpg`）。
8. **簡報與玩法矛盾**（壞）。「自由探索：不計時、不扣分」，簡報卻寫時限 15 分與三個任務目標，
   進場後 HUD 是「目標 0/0」（`07-briefing.jpg` 對照 `15-assisted-flying.jpg`）。
9. **新手教學藏在工程抽屜裡**（壞）。`pilot_guide.js` 的「操作提示 0/4」掛在 `.mission-tools`，
   而它在預設關閉的工程抽屜裡；海洋探索的委託也在同一抽屜，排在擬真設定之後（`19-engineering-drawer.jpg`、
   `37-expedition-contract.jpg`）。不按 Tab 的玩家永遠不知道有委託可接。
10. **回饋（juice）不足**（缺）。拍照（P）沒有快門、閃白或提示（`47-photo-feedback.jpg`）；
    沒有任何音樂；音效全為合成，`real` 預設下水下聲音關閉（`audio/fidelity.js`）；
    觸覺只有 5 種事件（解鎖、拍照、碰撞兩級、張力，`input/index.js:82-344`）；檢查點、委託完成沒有慶祝。
11. **真實模式的開場邏輯不通**（壞）。已經在水下 2.9 m，卻跳出「潛前檢查與回收」要玩家先勾「外觀、密封已檢查」；
    鎖定狀態下等 45 s 畫面完全不變（`24-real-first-frame.jpg`）。
12. **章節與訓練清單只有文字**（缺）。沒有章節簡介、預覽圖、預估時間、獎章或最佳成績；8 章中 7 章顯示
    「先完成前一章」（`08-story-chapters.jpg`、`09-training-scenarios.jpg`）。
13. **玩家期待的設定缺很多**（缺）。有：擬真、輔助等級、飛行檔位、死區／曲線／靈敏度／反向、音量 5 軌、
    4 段畫質、HUD 密度。沒有：語言、FOV（寫死 70°/55°，`camera_rig.js:132`）、遊戲內顯示模式與解析度
    （只有桌面殼的 `window_settings.cjs`）、亮度／Gamma、字級／UI 縮放、字幕大小與背景、色盲模式、
    單位（kn/m 寫死）、鍵盤改鍵、鏡頭晃動等防暈選項、FPS 上限。
14. **選單視覺不一致**（壞）。選單背景是過曝的灰白平沙、懸空的低多邊形石頭與一顆灰色橢球
    （`02-title.jpg`、`03-main-menu.jpg`）；玩法卡片對比過低（`04-modes.jpg`）；海域卡片被裁切且無捲動提示，
    背景整片棕色船殼（`06-sites.jpg`）；Falcon 在機庫被裁出畫面（`33-hangar-falcon-sticker.jpg`）；
    圖鑑是另一套樣式（黃色底線、× 鈕、沒有手把提示，`11-collection.jpg`）；標題畫面「Enter 開始」出現兩次。
15. **品牌與真實名稱**（壞，上架風險）。介面直接顯示「BlueROV2 Heavy」、「Korean Castle 沉船調查」
    （`05-hangar.jpg`、`06-sites.jpg`），違反 `AGENTS.md` 品牌規則，也是商店審核與商標風險。

### S3：值得記下

16. 輔助模式＋下水動畫從按「下水」到能操作 36 s；動畫本身是全作最好看的畫面（`13-intro-3.jpg`），
    但沒有「首次以後預設略過」。可按 Esc 跳過。
17. 暫停選單只有繼續／設定／返回主選單：沒有「重新開始任務」、「目前目標」、「鍵位」（`20-pause.jpg`）。
18. 講評回放功能完整（時間軸 10 種事件、上帝視角、匯出 HTML），但只有載入任務檔才進得去，玩家完成任務後
    不會被帶到這裡（`40-debrief.jpg`）。
19. 圖鑑只有 5 個分類（珊瑚、海星、海草、海藻、魚群），沒有物種層級、稀有度或完成度百分比（`11-collection.jpg`）。

## 系統盤點

評級：absent（沒有）／stub（有骨架或資料，玩家碰不到或不完整）／works（能用但陽春）／polished（可上架品質）。

| 系統 | 位置 | 評級 | 一句證據 |
|---|---|---|---|
| 劇情／戰役 | `simulator/campaign/*.json`（8 章＋5 事故）、`qysim/campaign/__init__.py`、`viewer/story/campaign.js` | works | 序章 17 節點可完整打完並存檔解鎖下一章；無結算、獎勵不顯示、只有文字無線電。 |
| 新手教學 | 序章、`viewer/pilot_guide.js` | stub | 序章教解鎖／移動／定深／燈／拍照；`pilot_guide` 的 4 步清單藏在預設關閉的工程抽屜。 |
| 速覽卡（1–4／十字鍵） | `viewer/hud/flight_hud.js` | works | 任務、系統、地圖、鍵位四張卡可叫出；鍵位卡是一整段文字（`44-peek-keys.jpg`）。 |
| 場景訓練／計分 | `qysim/scenarios.py:557 Scorer`、`app.js:946-965` | works | 檢查點、扣分、時限、失敗條件完整；結果只是一條橫幅，不存最佳成績。 |
| 事故演練 | `campaign/incident_*.json` | works | 5 個獨立演練，可重複；無評等呈現。 |
| 協作巡檢 | `qysim/mission_modes.py`、`viewer/mission_panel.js` | works | 12 分鐘、三站、全隊進度；面板文字為主。 |
| 探索委託／經濟 | `qysim/expedition.py`、`viewer/expedition_panel.js` | stub | 三種委託（巡檢／回收／部署）可接可取消；無報酬、無貨幣、無商店，入口在工程抽屜。 |
| 貨幣／商店／升級 | — | absent | 全庫搜尋無 currency／shop／credits 概念。 |
| 解鎖與進度 | `qysim/campaign` `unlocks`、`rov.campaign.v1` | stub | 只有 Falcon 與「潛水旗」兩項解鎖，且兩者一開始就能選。 |
| 存檔 | localStorage：`rov.campaign.v1`、`rov.fidelity.v1`、`rov.input.v1`、`rov.audio`、`rov.menu.last.v1`、`rov.menuSettings`、`rov.vehicle`、`rov.sticker`、`rov.mission`、`rov.quality`、`rov.playerName`、`rov.controlLayout.v1`、`rov.pilotGuide.dismissed.v1`、`rov.operatorVisible`、`rov.hud.drawer`；桌面版 `desktop/collection_store.cjs` | works | 單一隱性存檔，無存檔槽、無雲端同步 UI；劇情進度另寫一份到收藏庫。 |
| 成就 | `desktop/steam/achievements.json`、`desktop/steam_service.cjs`、`preload.cjs steamEvent` | stub | 15 項成就與 IPC 都在，viewer 無任何呼叫；遊戲內也沒有成就頁。 |
| 圖鑑／收藏 | `viewer/collection_store.js`、`collection_panel.js` | works | 5 類圖鑑、照片、工程紀錄、匯出入備份；樣式與選單不一致。 |
| 拍照／照片模式 | `#savePhoto`、`observation_photo` | stub | 有截圖存檔與觀測照判定；無照片模式（自由鏡頭、濾鏡、隱藏 HUD）、無快門回饋。 |
| 錄影與回放 | `replay_store.js`、`#recordFlight`、`debrief/` | works | 錄任務檔、回放、講評時間軸都可用；入口在工程抽屜，面向教官。 |
| 塗裝／貼紙 | `vehicle_stickers.js`（4 款）、`surface_paint.js` | works | 機庫即時套貼紙、多人同步；噴漆標記在工程抽屜。 |
| 載具 | `vehicle_models.js`（X1、BlueROV2 Heavy、Falcon） | works | 三台、即時 3D 展示與能力條；X1 標「暫定」。 |
| 主選單 | `viewer/menu/*` | works | 手把可全程操作、步驟條、卡片；背景與對比需要美術。 |
| 暫停選單 | `viewer/menu/pause.js` | works | 單人真正暫停模擬；選項只有三項。 |
| 擬真設定 | `viewer/fidelity.js`、`fidelity_panel.js` | polished | 單一來源、預設組、超出真機標記、選單與抽屜共用。 |
| 飛行輔助 | `qysim` assist、`hud/assist_pill.js` | works | 定點中可用；離底過高時「未生效」，玩家看不懂原因。 |
| 下水動畫 | `deploy_intro.js`、`launch_rig.js`、`intro_effects.js` | polished | 船、人員、吊架、倒影，全作最好的畫面；可 Esc 跳過。 |
| 飛行 HUD | `viewer/hud/*` | works | 航向帶、深度尺、讀數、小地圖都有；多處重疊（見痛點 7）。 |
| 音效 | `viewer/audio/engine.js`、`mapping.js` | works | 合成推進器、纜盤、警告、環境；5 軌音量。 |
| 音樂 | — | absent | 無任何音樂或音訊資產。 |
| 觸覺 | `input/haptics.js`、`haptics_fidelity.js` | works | 5 種事件的 dual-rumble／trigger-rumble。 |
| 手把支援 | `input/devices.js`、`controller-db.json`、`glyphs.js` | polished | SDL 對應庫、Xbox/PS/Switch 字形、選單全程可用手把。 |
| 改鍵 | `input/settings.js`、`input/bindings.js` | stub | 只有手把，輸入原始代碼；鍵盤不可改。 |
| 無障礙 | `prefers-reduced-motion`（`menu.css`、`hud.css` 等） | stub | 只有減少動態；無色盲、字級、UI 縮放、字幕設定、高對比。 |
| 在地化 | 各模組 `STRINGS`、`docs/tasks/T09-i18n.md` | absent | 只有繁中，OSD 混英文；T09 未實作。 |
| Steam 整合 | `desktop/main.cjs`、`steam_service.cjs`、`steam_bridge.cjs`、`steam/*.vdf` | stub | 初始化、覆蓋層、Deck 偵測、輸入範本、上傳範本都有；成就未接、無 Rich Presence、無雲端存檔設定、無好友邀請。 |
| 多人 | `qysim/room.py`、`viewer/menu/multiplayer.js`、`fleet.js` | works | 最多三人同房、房主、委託共享；要手填伺服器網址與房間碼，無大廳、無 Steam 好友。 |
| 教官／講評 | `viewer/instructor/`、`viewer/debrief/`、`qysim/debrief.py` | works | 內部訓練用，功能完整；不屬於玩家流程。 |

## 截圖索引

| 檔案 | 內容 |
|---|---|
| `02-title.jpg` | 標題；「Enter 開始」兩次、背景懸空橢球 |
| `03-main-menu.jpg` | 主選單 |
| `04-modes.jpg` | 玩法卡片（低對比） |
| `05-hangar.jpg` | 機庫 X1；廠商機型名稱 |
| `06-sites.jpg` | 海域卡片被裁切、棕色船殼背景 |
| `07-briefing.jpg` | 自由探索簡報卻有時限與目標 |
| `08-story-chapters.jpg` | 劇情章節，7/8 鎖住、只有文字 |
| `09-training-scenarios.jpg` | 場景訓練清單 |
| `10-settings-fidelity.jpg` | 擬真設定（輔助預設） |
| `10-settings-controls.jpg` | 控制：通道名鍵位表 |
| `10-settings-quality.jpg` | 畫質只有 4 段 |
| `10-settings-interface.jpg` | 介面設定 5 項 |
| `11-collection.jpg` | 圖鑑（另一套樣式） |
| `12-multiplayer.jpg` | 多人：手填 ws:// |
| `13-intro-1.jpg` | 下水轉場閃出「未連線到模擬器」開發者面板 |
| `13-intro-3.jpg` | 下水動畫（最好的畫面） |
| `14-assisted-first-frame.jpg` | 入水後：空藍、AI 除錯列 |
| `15-assisted-flying.jpg` | 輔助「未生效」、往上漂、AI 框壓深度尺 |
| `19-engineering-drawer.jpg` | 工程抽屜 |
| `20-pause.jpg` | 暫停 |
| `24-real-first-frame.jpg` | 真實模式：水下卻要做潛前檢查、英文 OSD |
| `27-story-radio.jpg` | 序章無線電、右上疊字 |
| `28-story-first-task.jpg` | 任務提示鍵帽重疊、「手柄」 |
| `31-scenario-hud.jpg` | 場景訓練：檢查點圓環壓讀數 |
| `33-hangar-falcon-sticker.jpg` | Falcon 被裁切、貼紙 |
| `37-expedition-contract.jpg` | 接委託後的抽屜（教學清單與委託都在這） |
| `40-debrief.jpg` | 講評回放 |
| `44-peek-keys.jpg` | 鍵位速覽卡（文字牆、ROV_USA） |
| `46-camera-v.jpg` | 追蹤視角仍畫機載十字與俯仰梯 |
| `47-photo-feedback.jpg` | 拍照後沒有任何回饋 |
| `50-story-complete.jpg` | 序章完成：只有一句台詞 |
| `51-story-after-complete.jpg` | 回到章節：第一章解鎖，無獎勵呈現 |

## 後續建議的方向（不在本文件範圍，僅供排任務）

- 結算畫面＋最佳成績＋星等（呈現層，資料後端已有）；完成後「下一章／重試／講評回放」。
- 把現有 `reward`、成就事件接上（`steamEvent`），並讓解鎖真的鎖住（Steam 版）；內部訓練版可全開。
- 開場：輔助模式預設從離底 2–3 m、目標在視野內開始，定深預設開（輔助層，`real` 不變）。
- 預設鍵位改為 WASD 平移＋QE 升降＋方向鍵轉向的「遊戲」配置作為 Steam 預設；完整改鍵介面。
- T09 在地化、移除開發者字串與連線面板、HUD 重疊修正、選單美術。
