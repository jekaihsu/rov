# Steam Input 上架設定

本遊戲透過瀏覽器 Gamepad API 讀手把（Electron 內嵌 Chromium），**尚未呼叫 Steam Input API**。Partner 站仍應上傳動作集範本，讓 Steam 客戶端在「Steam Input 開啟」時把各家手把正規成標準手把佈局。

預設的傳統手把輸出設定與匯入步驟見 [Steam Input 配置](../../simulator/desktop/steam/input/README.md)。

## 檔案

| 檔案 | 用途 |
|---|---|
| `simulator/desktop/steam/game_actions_TEMPLATE.vdf` | 官方動作集（IGA）草稿。上架時複製為 `game_actions_<AppID>.vdf` |
| 動作名稱 | 對應 `simulator/viewer/input/bindings.js` 的 `flight`／`menu` 列 |

上傳前把檔名中的 `TEMPLATE` 換成 AppID，並在 Steamworks → Steam Input 發佈為建議設定。

## 建議的官方組態

對下列控制器類型各建一組「Gamepad」範本並設為建議設定：

- Xbox 家族
- PlayStation 家族
- Switch Pro
- Steam Deck

綁定原則（與 `bindings.js` 預設一致）：

- 左搖桿 → Move（前後／左右推力通道）
- 右搖桿 → Look（偏航／垂直）
- 扳機 → 左右滾輪（或肩鍵，依組態）
- 面鍵／Select／Start／L3／R3／十字鍵 → 見 bindings 預設

關閉 Nintendo「按鍵互換」類選項，讓 **位置** 對齊 Standard Gamepad（印刷字母由遊戲內圖示家族處理）。

## Steam Input 開與關時遊戲的行為

| Steam Input | Chromium 通常看到 | 本遊戲路徑 |
|---|---|---|
| **開啟**（官方 Gamepad 範本） | `mapping === "standard"` 的虛擬手把 | 直接用 standard 索引；不查 `controller-db.json` |
| **關閉** | 驅動原始布局；可能 `mapping === ""` | vendor:product 查 DB；未知先用標準位置，可在設定中啟動對應精靈，存 `rov.input.v1` → `custom` |
| Steam Deck | 多半經 Steam Input | 同「開啟」；實機仍需驗證 |

遊戲**不會**讀取 Steam Input 的 action set 名稱；VDF 是給 Steam 客戶端做重映射與建議組態用。若日後接 Steam Input API，可把 `Flight`／`Menu` 兩個 set 接到同一套語意動作，無需改 bindings 語意。

## 與本機校正的關係

- Steam Input 開：多數玩家不需校正。
- Steam Input 關或雜牌 DirectInput：沿用 DB 或手把設定裡的「對應精靈」。
- 死區：遊戲輸出端有徑向死區；Steam 組態若再加死區會疊加，建議官方組態死區偏小。

## 驗證清單

1. Partner 上傳 `game_actions_<AppID>.vdf` 與四家族建議組態。
2. 在 Steam 客戶端對每家族開關 Steam Input，用 Electron DevTools 看 `navigator.getGamepads()[0].mapping`。
3. 跑 `python tools/run_browser_checks.py browser_menu_gamepad_smoke browser_gamepad_matrix_smoke`（假手把；真機手感另測）。
