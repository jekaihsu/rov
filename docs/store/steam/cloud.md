# Steam Auto-Cloud 設定建議（S4）

程式常數：[`simulator/desktop/steam/cloud_paths.cjs`](../../../simulator/desktop/steam/cloud_paths.cjs)。
桌面殼透過 `steamStatus().cloud` 回傳實際路徑；`steamStatus().cloudPath` 仍是 Electron `userData` 根目錄。

## 版本化存檔（S3）

職涯、戰役、擬真設定等版本化存檔由 `desktop/save_files.cjs` 原子寫入 `saves/*.json`（見
`docs/design/saves.md`），已列入 `cloud_paths.cjs` 的 `INCLUDE`；損毀副本 `saves/corrupt/**` 只留本機。

## 建議的 Partner 設定

| 項目 | 建議 |
|---|---|
| Root | Windows：`WinAppData`；子目錄為 Electron productName（內訓 `ROV Simulator`，Steam 版 `ROV Solution`）。以執行中 `steamStatus().cloudPath` 核對，不要只因改名就改雲端規則。 |
| Include | `preferences.json`、`window.json`、`saves/**`、`collection/**`、`steam-mock/**` |
| Exclude | `backend.log`、`numba-cache/**`、`saves/corrupt/**`、`local-backups/**`、`reports/**` |
| 帳號隔離 | 開啟 per-user root override，避免同機多 Steam 帳號互蓋 |
| `window.json` | 跨機可能造成視窗落在無效螢幕；可考慮排除或啟動時校正 |

## 檔名樣式

| 路徑 | 內容 |
|---|---|
| `preferences.json` | 載具、畫質、輸入偏好 |
| `window.json` | 視窗模式／解析度／顯示器 |
| `collection/` | 照片、圖鑑、工程紀錄（見 collection_store） |
| `steam-mock/state.json` | 無 App ID 時的成就／Rich Presence 假後端（僅開發與未接 Steam 時） |
| `saves/*.json` | 版本化職涯、戰役與設定存檔（`saves/corrupt/` 為本機損毀副本，不同步） |

## 配額

初始預算：**1 GiB／10,000 檔／使用者**（與 RELEASE 一致）。照片佔大宗；送審前用真實收藏量測。
本行程不實作刪除／壓縮／配額警示；衝突依 Steam 啟動前對話與本機匯出備份處理。

## 驗收

- 雙機、雙帳號往返後進度與收藏一致。
- 離線分歧、覆寫、刪除、配額滿、重裝路徑有紀錄。
- Steam 版與內訓版 productName 不同時，各自的 Auto-Cloud 規則已分開設定。
