# S4：Steam 整合（成就、雲端存檔、Rich Presence）先做好介面與假後端（Codex）

> 先完整讀 `docs/prompts/R0-common.md`、`simulator/desktop/README.md`、`docs/store/`。分支 `task/S4-steam-integration`。
> Steamworks 帳號還沒註冊，所以**沒有 App ID**：全部做成可替換的介面，加一個假後端讓遊戲與測試能跑。

1. `simulator/desktop/` 加 Steam 橋接（Electron 主行程）：有 App ID 與 Steam 執行時用真的 Steamworks（選一個 MIT 授權的
   Node 綁定，在 PR 描述寫授權）；沒有時用假後端（寫到本機 JSON，可在開發者頁看到）。前端透過 `window.rovDesktop` 呼叫。
2. **成就**：定義 15–25 個，與真實作業能力相關（例如：零接觸完成港口巡檢、照原路解開纜線勾纏、完成第一章金牌、
   低能見度下完成量測），不要刷數量型成就。清單、圖示規格（之後美術做）、觸發條件寫在 `docs/store/steam/achievements.md`；
   觸發邏輯寫成純函式並有 node 測試。內部訓練版不顯示成就。
3. **雲端存檔**：同步 S3 定義的存檔資料夾（若 S3 未合併，先寫路徑常數與文件，留 TODO 指向 S3）。寫 Steam Auto-Cloud 的
   設定建議（路徑、檔名樣式、配額）到 `docs/store/steam/cloud.md`。
4. **Rich Presence**：顯示目前章節與關卡（四語）。
5. **Steam 版建置**：`ROV_BUILD_EDITION=steam` 時打包進 Steam 版設定；不要在 `pull_request` 觸發 Windows／macOS runner（AGENTS.md）。

跑：`node simulator/desktop/test_steam.cjs` 與新增的測試、`browser_smoke`。
