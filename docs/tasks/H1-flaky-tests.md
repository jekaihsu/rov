# H1：測試穩定性

基底 `main`。分支 `task/H1-flaky-tests`。已讀 `AGENTS.md`（硬性規則 2：不得為了過 CI 跳過、刪除或放寬既有測試）與本機選測入口說明。

## 目標

高負載機器上不穩定的單元／瀏覽器檢查改為量測正確的東西（模擬時間、狀態、事件），並修好會被軟體 GPU 渲染餓死的訊息處理與工程抽屜疊層。不靠放寬斷言過關。

## 變更摘要

1. **SDK 相機串流**：以假時鐘驗證節拍與幀契約；牆鐘 fps 下限在偵測到主機飽和時 skip（訊息寫明原因），覆蓋由契約測試保留。
2. **browser_smoke**：夾爪／燈光等待改依模擬時間與狀態，逾時走 `timeout()`。
3. **來賓 host_only／last_photo**：產品面新增 `link_inbox.js`，頁面端合併 state，控制回覆不再被 30 Hz 快照 backlog 堵住；測試仍斷言同一行為。
4. **controller metadata**：凍結 `monotonic`，在 fleet 快照未因 1/30 s 重刷時證明 controller 仍更新。
5. **paint / flightDrawer**：`#flightTools` 疊在工程抽屜之上，測試以 `elementFromPoint` 驗證可點。
6. **campaign 錄影**：無 ffmpeg 時跳過錄影並印原因，其餘步驟照跑。
