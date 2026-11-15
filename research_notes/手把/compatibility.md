# 瀏覽器／Electron 下手把相容性

整理 Chrome／Chromium（含 Electron）Gamepad API 對常見手把的行為，以及本專案 `controller-db.json` 與校正精靈的角色。證據標記：〔規格〕〔原始碼〕〔推論〕〔未驗證〕。

## Standard Gamepad（`mapping === "standard"`）

W3C 定義唯一正規佈局：四軸（左／右搖桿）與 17 鍵（面鍵 0–3、肩鍵 4–5、扳機 6–7 為 0…1 類比、Select／Start 8–9、L3／R3 10–11、十字鍵 12–15、Guide 16）。索引依**實體位置**，不依印刷字母。〔規格〕[W3C Gamepad](https://w3c.github.io/gamepad/)

| 索引 | 位置 | 常見印刷（僅對照，介面不顯示廠牌商標圖） |
|---|---|---|
| b0–b3 | 右面鍵 下／右／左／上 | A/B/X/Y；×/○/□/△；B/A/Y/X（Switch 位置字母互換） |
| b6／b7 | 左／右下扳機 | LT／RT；L2／R2；ZL／ZR — **標準映射下為按鍵值 0…1，不是軸** |
| a0–a3 | 左 X/Y、右 X/Y | −1…1，0 為中立 |

## Chrome／Chromium 實際映射（Windows 原始碼）

Chromium 在 Windows 對多款裝置有專用 remapper（`device/gamepad/gamepad_standard_mappings_win.cc`）。〔原始碼〕[映射表](https://github.com/ronitmevada/Chromium/blob/main/device/gamepad/gamepad_standard_mappings_win.cc)

| 裝置 | Chrome 行為 | 扳機 | 狀態 |
|---|---|---|---|
| Xbox 360／One／Series（有線／多數藍牙） | 通常直接或經 remapper → `standard` | b6／b7 | 〔推論〕常見；本機未逐款實測 |
| DualShock 4 | `MapperDualshock4`：面鍵重排、扳機由軸轉按鍵、十字鍵由 hat 軸展開 | 軸→b6／b7 | 〔原始碼〕 |
| DualSense | `MapperDualSense`：同上 | 軸→b6／b7 | 〔原始碼〕 |
| Switch Pro／部分 HORI | 有 Switch 系 mapper | 數位扳機常為 0 或 1 | 〔原始碼〕／〔推論〕 |
| Logitech F310／F710 **XInput（X 檔）** | 走 Xbox 路徑 → `standard` | b6／b7 | 〔推論〕 |
| Logitech F310／F710 **DirectInput（D 檔）** | `MapperLogitechDInput`：面鍵重排、十字鍵由軸展開；原始碼註解寫 Meta 不可用 | 見 mapper；D 檔扳機行為依驅動 | 〔原始碼〕 |
| 平價 DirectInput／雜牌 | 可能 `mapping === ""` | 常為軸或合併 Z 軸 | 〔推論〕 |
| 飛行搖桿（如 T.16000M） | 多半非 standard；軸／鍵數多於 4／17 | 不適用遊戲手把佈局 | 〔推論〕；靠校正精靈 |

Linux／macOS／Steam Deck 的 remapper 集合與 Windows 不完全相同；同一 VID／PID 在不同 OS 的原始索引可能不同。〔推論〕

## `mapping === ""` 時

- 軸／鍵順序為驅動原始報告，**不可假設** standard 索引。〔規格〕〔說明〕[瀏覽器差異筆記](https://twinstickgaming.neocities.org/gamepad-api-browser-differences)
- 十字鍵可能是 hat 軸；扳機可能是軸或「LT−RT」合併軸。〔推論〕
- 本專案：以 vendor:product 查 `controller-db.json`；查不到則 `known: false`，需跑對應精靈，結果存 `rov.input.v1` 的 `custom[pad.id]`。

## 對應表授權

[SDL_GameControllerDB](https://github.com/mdqinc/SDL_GameControllerDB) 為 **zlib**。AGENTS.md 新資產原則列 MIT／BSD／Apache／CC0。T02 已納入精簡 Linux 列並在 `CREDITS.md`／`SDL-LICENSE.txt` 標註。**G2 維持此既有決策**，不擴大為完整 DB 原文；PR 請審查者確認繼續接受 zlib。建置：`python3 simulator/tools/build_input_db.py gamecontrollerdb.txt`。

DB 中的 `h0.*` hat 描述在瀏覽器快照無法直接解碼（見 input README）：此類裝置十字鍵需校正或依賴 Chrome 的 standard remapper。

## 死區

本專案在**輸出端**做徑向死區（預設內 0.08、外 0.02）與每通道 expo／靈敏度，不依賴瀏覽器。Steam Input 再開一層死區時可能疊加——見 `docs/steam/steam-input.md`。

## Steam Input 開／關（本專案未接 Steam Input API）

| 狀態 | 瀏覽器看到的 | 本專案路徑 |
|---|---|---|
| Steam Input **開**，官方 Gamepad 範本 | 多半為 XInput／standard 手把 | `mapping === "standard"`，不查 DB |
| Steam Input **關** | 原始 HID／驅動布局 | standard 或 DB 或校正 |
| Steam Deck | 通常經 Steam Input | 〔未驗證〕需實機 |

## 相容性狀態總表（給 PR）

| 手把 | 狀態 | 說明 |
|---|---|---|
| Xbox 360／One／Series | 〔推論〕 | Chromium／XInput 路徑成熟；本環境無實機 |
| DualShock 4／DualSense | 〔推論〕＋〔原始碼〕 | Windows remapper 明確 |
| Switch Pro | 〔推論〕＋〔原始碼〕 | 面鍵字母與位置：圖示用家族標籤 |
| 8BitDo（多 VID，常見 2dc8） | 〔推論〕 | 多模式；XInput／standard 或 DB／校正 |
| Logitech F310／F710 X 檔 | 〔推論〕 | 同 Xbox |
| Logitech F310／F710 D 檔 | 〔原始碼〕 | 有專用 mapper；仍建議實測 |
| 平價 DirectInput | 〔未驗證〕 | 依賴 DB 或校正 |
| Thrustmaster T.16000M 等 HOTAS | 〔未驗證〕 | 校正精靈；軸數＞4 不崩潰 |

「實測」列需審查者本機插真機後改狀態。
