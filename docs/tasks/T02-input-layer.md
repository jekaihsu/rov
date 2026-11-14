# T02 輸入層：支援市面上大多數手把

**目標**：任何常見手把插上就能飛，可改鍵、可調手感、有震動、有正確的按鍵圖示。

**範圍**：新增 `simulator/viewer/input/`；`simulator/viewer/app.js` 中 `readPad()`、鍵盤、觸控搖桿的輸入彙整段落搬進新模組，`app.js` 只保留呼叫；`controller-check.html`／`.js` 可重用新模組。不改後端。

**背景**：目前只有 `app.js` 的 `readPad()`：按鍵索引寫死為標準配置、每軸獨立 8% 死區、線性、不能改鍵、沒有震動。`gamepad.mapping !== "standard"` 的裝置會錯位。

**要做**

1. **裝置抽象**：`input/devices.js` 每幀輸出統一的「實體輸入快照」。支援多支手把同時連接、熱插拔、選定使用中裝置；最後有動作的裝置成為使用中裝置。
2. **對應表**：`mapping === "standard"` 直接使用。非標準裝置以 `id` 中的 vendor／product 比對內建資料表；資料表從 SDL_GameControllerDB（zlib 授權，需寫入 CREDITS）轉成精簡 JSON，建置腳本放 `simulator/tools/`。查不到時進入**對應精靈**：依序請使用者推每個軸、按每個鍵，存成自訂設定檔。
3. **動作層**：`input/actions.js` 定義語意動作（六個操控通道、解鎖、定深、模式、燈光、拍照、錄影、切鏡頭、輔助等級、飛行檔位、選單導航、機械臂）。實體輸入到動作的綁定可由使用者改，存 `localStorage`（桌面版存使用者設定目錄，沿用現有偏好機制），可重設為預設。提供至少兩組預設：現行配置、以及「空拍機式」配置（左搖桿升降＋偏航、右搖桿前後＋橫移）。
4. **手感**：徑向死區（不是每軸獨立）、外圈死區、每通道 expo 與靈敏度、反向、扳機當軸或當鍵。曲線在輸出端套用，送出的 PWM 語意不變。
5. **震動**：`input/haptics.js` 封裝 `vibrationActuator`（雙馬達 `dual-rumble`，有 `trigger-rumble` 時也用），提供 `pulse(name)`：解鎖、拍照、輕碰、重撞、纜線張力警告。可在設定關閉與調強度。不支援時靜默略過。
6. **圖示**：`input/glyphs.js` 依裝置類型回傳按鍵圖示（Xbox、PlayStation、Switch、通用、鍵盤），自繪 SVG，不使用廠商商標圖形。`pilot_guide.js` 的鍵位提示改用它。
7. **設定頁**：手把分頁含：裝置清單、即時軸／鍵顯示、曲線圖（推桿時圓點沿曲線移動）、死區與 expo 滑桿、改鍵清單、對應精靈、震動測試。頁面本身可用手把操作。視覺依 `docs/design/ui-direction.md`。
8. RC 封包加入 `assist` 與 `profile`（見 `AGENTS.md` 契約），預設 `assist: 2`、`profile: "normal"`，提供動作切換。後端尚未支援時多送這兩個欄位不會出錯。
9. 飛行搖桿／HOTAS 類裝置：至少能透過對應精靈完成綁定（軸數多於 4、按鍵多於 17 不可崩潰）。

**測試**：`input/` 的純函式（死區、曲線、對應表解析、綁定解析）用 `node --test` 寫在 `simulator/tests/*.mjs`。另附一支 Playwright 腳本，以注入假的 `navigator.getGamepads` 驗證：標準手把、非標準手把走資料表、未知手把走精靈。

**不做**：Steam Input API 整合（T10）、後端輔助（T01）。
