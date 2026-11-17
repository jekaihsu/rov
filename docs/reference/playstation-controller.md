# PlayStation 手把（DualShock 4／DualSense）使用說明與手動測試

適用：Windows 桌面版（Electron 44，內建 Chromium 152）與 Chrome／Edge 瀏覽器版。
自動檢查：`simulator/tools/browser_playstation_smoke.py`（假手把，四種回報方式各走一次完整流程）與
`node --test simulator/tests/test_playstation_pad.mjs`。真機手感、震動與藍牙穩定度仍要依本文最後的清單實測。

## 支援範圍

| 手把 | USB | 藍牙 | 瀏覽器回報 |
|---|---|---|---|
| PS4 DualShock 4（054c:05c4、09cc，USB 無線接收器 0ba0） | 可 | 可 | `mapping: "standard"`，17 顆標準鍵＋觸控板（索引 17） |
| PS5 DualSense（054c:0ce6）、DualSense Edge（0df2） | 可 | 可 | 同上 |

- Chromium 對這五個產品內建標準對應，USB 與藍牙相同（Windows 走 Raw Input／HID，不是 XInput）。手把的 `id`
  形如 `DualSense Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 0ce6)`；藍牙連線時名稱常只有
  `Wireless Controller`，靠 `054c` 判定為 PlayStation 圖示（×○□△）。
- 若瀏覽器或驅動不認得產品而回報 `mapping: ""`（原始順序），`viewer/input/playstation.js` 依 `id` 格式改用
  正確的原始配置：Windows／macOS 的 HID 順序（十字鍵在軸 9 的帽型開關）或 Linux evdev 順序（十字鍵在軸 6／7），
  不再沿用彼此矛盾的 SDL 資料庫紀錄。
- 瀏覽器規定：頁面開啟後要先**按一下手把任一鍵**，`navigator.getGamepads()` 才會出現手把；視窗需在前景。

## 預設按鍵（PS 標示）

| 按鍵 | 選單（主選單、暫停、結算、甲板檢查） | 飛行 |
|---|---|---|
| ✕ | 確認 | 拍照 |
| ○ | 返回／關閉 | 錄影（按住） |
| □ | — | 定深 |
| △ | — | 解鎖／上鎖 |
| L1／R1 | 上一／下一分頁 | 右滾輪：左移／右移等（依操作模式） |
| L2／R2（類比） | — | 左滾輪：下潛／上升等（依操作模式） |
| 左搖桿 | 移動焦點 | 左桿（依操作模式，ROV_USA 為俯仰／偏航） |
| 右搖桿 | 旋轉機庫展示 | 右桿（ROV_USA 為前進後退／橫滾） |
| 十字鍵 | 移動焦點、調整數值 | 上：任務、左：系統、右：地圖、下：鍵位速覽 |
| L3 | — | 切換視角 |
| R3 | — | 輕按：輔助等級；長按：飛行檔位 |
| Options | — | 輕按：燈光；長按：暫停選單 |
| Share（PS4）／Create（PS5） | — | 輕按：A/S/C 模式；長按：工程面板 |
| Share＋Options 同按 | — | 手把設定 |
| PS 鍵 | — | 手臂操作模式 |
| 觸控板按下 | — | 未使用 |

搖桿的實際意義（前進、偏航…）依操作模式而定，與真機遙控器相同；畫面上的說明以動作名稱標示。
遊戲內的提示：選單底部、標題畫面與暫停選單顯示 ×○□△ 與 L1／R1；飛行中的說明卡與設定頁的按鍵表目前仍用
通用名稱（A／B／LB…，位置相同：A＝✕、B＝○、X＝□、Y＝△、LB＝L1、View＝Share、Menu＝Options）。

## 已知限制

- **震動**：Chromium 只對 DualShock 4 送出震動（USB 與藍牙皆有實作）；DualSense 在 Chromium 沒有震動路徑，
  `vibrationActuator` 為空，遊戲會安靜略過，不會出錯。自適應扳機、燈條、喇叭、麥克風、陀螺儀與觸控板座標都未使用。
- **下水動畫**：放入水中後的下水動畫只能用鍵盤 Esc 或滑鼠跳過；用手把時請等它播完（約 12 秒）。
- **Steam**：Steam 開著且啟用「PlayStation 設定支援」時，Steam Input 可能把手把轉成虛擬 Xbox 手把（圖示會變成
  A／B／X／Y，功能不受影響）或在 Steam 視窗取得焦點時攔截輸入。DS4Windows 等轉換工具也一樣。目前尚非 Steam
  版，測試時建議先關掉 Steam 與 DS4Windows。
- **PS 鍵**：Windows 上若有其他程式（Steam、PS Remote Play）佔用 PS 鍵，手臂模式可能無法切換。
- 同時接兩支手把時，以最後有動作的那支為準。

## 五分鐘手動測試清單（真手把）

每一項打勾；有問題請記下手把型號、USB 或藍牙、瀏覽器或桌面版、哪一步。

1. 關閉 Steam 與 DS4Windows。用 USB 接上手把，開啟遊戲。
2. 標題畫面按 ✕：底部或按鈕上的確認圖示是「×」，進入主選單。
3. 十字鍵上下、左搖桿上下都能移動焦點；進「設定」後按 R1／L1 換分頁，按 ○ 返回主選單。
4. 「潛航」→ 選自由探索 → 機庫（右搖桿可轉動展示）→ 下一步 → 選地點 → 簡報頁，保持「下水動畫」開啟，按 ✕ 開始。
5. 甲板檢查：連按 ✕ 逐項確認；推進器短測那一步用 ✕ 逐顆測試（每顆約 2 秒），全部完成後再按 ✕。
   接著確認纜線手、緩放入水（等下水動畫播完）、入水確認。整個過程不碰鍵盤滑鼠。
6. 按 △ 解鎖；推左右搖桿、按 L2／R2、L1／R1，畫面與遙測都有反應，放開後停止。L2／R2 半按時推力也約一半。
7. 輕按 Options：燈光切換；按 L3：視角切換；按 ✕：拍照（有快門效果）；（DualShock 4）撞到東西時手把會震動。
8. 長按 Options：開啟暫停選單，模擬暫停；十字鍵上下移動，○ 或「繼續」✕ 回到遊戲。
9. 再開暫停選單 → 「回主選單」→ ✕，回到主選單。
10. 拔掉 USB，改用藍牙配對（PS 鍵＋Share／Create 長按至燈條快閃），重做第 2、6、8 步。

Chrome 網址列輸入 `about://gamepad`（或開啟 https://hardwaretester.com/gamepad）可看到手把回報的 `id`、
`mapping` 與每顆鍵的值；回報異常時請一併截圖。
