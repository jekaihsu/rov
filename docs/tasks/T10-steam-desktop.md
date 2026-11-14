# T10 桌面版與 Steam 整合

**目標**：桌面版達到可上傳 Steam 測試分支的狀態：Steamworks 接上、手把由 Steam Input 兜底、建置可重現。

**範圍**：`simulator/desktop/`、`.github/workflows/`（建置 job）。前端僅透過 `preload.cjs` 暴露的介面互動，不直接改 `simulator/viewer/` 的遊戲邏輯。

**要做**

1. **Steamworks**：以 `steamworks.js`（MIT）在主行程初始化；App ID 由環境變數或 `steam_appid.txt` 提供，開發時用測試 ID 480。Steam 未執行時程式仍可正常啟動（內部訓練版不依賴 Steam）。透過 `preload.cjs` 暴露最小介面：是否在 Steam 下、玩家名稱、語言、成就解鎖、統計上報、雲端存檔路徑、覆蓋層狀態。
2. **成就與統計**：定義首批約 15 個成就（第一次下潛、各任務類型首次完成、零碰撞完成、圖鑑五類集滿、三人協作完成、解開纏繞等），放在一份 JSON 清單，前端以事件通知主行程。附 Steamworks 後台設定用的對照表。
3. **雲端存檔**：偏好設定與收藏（`collection_store.cjs`，注意照片體積）放在 Steam Auto-Cloud 可同步的路徑；寫出建議的 Auto-Cloud 規則與配額估算。離線可用，衝突時不遺失本機資料。
4. **Steam Input**：確認 Electron 的 Gamepad API 在 Steam Input 啟用下收到的是 XInput 標準配置；提供預設的 Steam Input 控制器設定檔（至少 Xbox、PlayStation、Switch Pro、Steam Deck），寫明後台應勾選的支援類型。Steam 覆蓋層開啟時遊戲輸入回中。
5. **Steam Deck**：1280×800 啟動全螢幕、預設畫質等級、介面縮放；列出尚未達到 Deck Verified 的項目。
6. **視窗**：全螢幕／無邊框／視窗切換、解析度與更新率、垂直同步、多螢幕選擇、Alt+Enter；設定持久化。失去焦點時操控回中。
7. **建置**：GitHub Actions 的 Windows job 完成 `npm ci` → 後端 PyInstaller → `electron-forge make`，上傳成品為 artifact；`steam/*.vdf.example` 改為可由 CI 產生實際 vdf（App ID 與 depot ID 來自 secrets，檔案本身不含機密）。另評估並回報 Linux（含 Proton 與原生）與 macOS 建置的可行性與缺口，不必實作。
8. **啟動體驗**：後端啟動期間顯示啟動畫面與進度；後端崩潰時給出可讀錯誤與日誌位置並可重試；單一實例鎖。
9. **安全**：`contextIsolation` 開啟、`nodeIntegration` 關閉、導航與新視窗白名單、CSP。列出目前設定與調整。
10. **發行內容**：Steam 建置不包含 `simulator/sdk_mock`、Q-iRC 轉接與廠商相關文件；以建置旗標區分「內部訓練版」與「Steam 版」。

**驗證**：Windows 上實際啟動的紀錄（Steam 執行與未執行各一次）、成就在測試 App 下解鎖的截圖或日誌、CI 建置成功連結。無法在實機驗證的項目請明確列為「未驗證」，不要寫成已完成。
