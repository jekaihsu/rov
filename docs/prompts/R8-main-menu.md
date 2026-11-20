# R8：主選單重新設計（Codex）

> 先完整讀 `docs/prompts/R0-common.md` 與 `docs/design/ui-direction.md`、`docs/design/menu-redesign/`、
> `docs/design/big-picture/`。分支 `task/R8-main-menu`。

## 背景

擁有者：「主頁面的設計也缺點意思。」開場結束後玩家回到的就是主選單；它要和開場同一個質感：
紀錄片感、真實、俐落、橘色強調色（不是萊姆綠）、不圓潤、不像玩具。
相關草稿：PR #103（P1 難度三檔與開新遊戲畫面）、#81／#102（小艇選單舞台模型）。
選單的 3D 舞台模型是 #81／#102 的事；你做的是**舞台上的鏡頭、介面與流程**，模型沿用 main 上現有的。

## 先拍現況

主選單、劇情、訓練、設定、暫停、結算，各截 1600×900 與 1366×768，放 `docs/design/main-menu-r8/before/`。

## 要做的事

1. **活的背景**：主選單背景是小艇上或水下的即時場景（不是靜態圖），時間、天氣隨玩家進度變化（序章：港內清晨；
   第一章：港口；第二章：養殖場外海）；鏡頭緩慢移動，有作業人員或纜線等細節。效能低檔位時退成單張即時渲染畫面。
2. **層級**：第一層只有「繼續（顯示下一關名稱與進度）」「劇情」「訓練」「設定」「離開」。
   Steam 版（`window.rovDesktop?.edition === 'steam'`）隱藏內部功能：工程抽屜、SDK、AI、教官、多人／遠征、
   塗裝、範圍外舊章節、開發測試頁；內部版保留。寫一份清單在 PR 描述。
3. **劇情選單**：章節卡（照 `brand/chapter_card.js`）、每關獎牌、重玩開場；未解鎖的關卡顯示剪影與「完成前一關」。
4. **手把優先**：所有畫面可用 PS 手把完整操作（✕ 確認、○ 返回、L1/R1 切頁），焦點清楚；鍵盤 Space/Enter 確認。
   提示列用 `input/glyphs.js` 的實際圖示。
5. **轉場**：開場結束 → 主選單、主選單 → 下水，都要有淡入淡出與聲音，不要硬切。
6. 若 PR #103 尚未合併：不要做難度選擇畫面，留一個入口；已合併就整合它。

## 驗證

- 跑：`browser_menu_smoke browser_smoke browser_playstation_smoke browser_cold_open_smoke`，加 `browser_i18n_smoke`。
- 新增或更新一支 smoke：Steam 版與內部版各走一遍第一層，檢查隱藏清單。
- after 截圖同角度放 `docs/design/main-menu-r8/after/`，附前後聯絡表；四種語言各一張主選單。
