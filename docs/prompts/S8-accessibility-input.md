# S8：無障礙與按鍵重新設定（Codex）

> 先完整讀 `docs/prompts/R0-common.md`、`simulator/viewer/input/README.md`、`docs/reference/playstation-controller.md`。
> 分支 `task/S8-accessibility-input`。若 PR #107（P7 設定）尚未合併，先合併它的分支 `cursor/p7-settings-32a6` 再開始，
> 並在 PR 描述註明取代 #107。

Steam 玩家要求：完整重新設定按鍵、字幕可調、色弱可用。

1. **按鍵重新設定畫面**：鍵盤與手把都可重設每個動作（`input/bindings.js`、`input/actions.js`），偵測衝突、可重設預設；
   手把可完整操作此畫面；存檔有版本。提示圖示（`input/glyphs.js`）即時跟著新綁定。
2. **搖桿**：死區、反應曲線、Y 軸反轉，各搖桿獨立；真實模式下這些屬於偏好（`presetNeutral: true`）。
3. **字幕與無線電**：字級（小／中／大／特大）、背景不透明度、說話者名稱顏色、無線電字幕停留時間。
4. **色弱**：HUD 的警示（張力、深度、電量）不只靠顏色（加圖形或文字），提供三種色弱調色盤選項。
5. **動態舒適**：關閉鏡頭晃動、減少閃光（拍照閃光、撞擊雜訊），與 R7 的回饋開關整合（若 R7 已合併）。
6. 所有新項目進設定頁並四語化。

跑：node 測試（綁定衝突、存檔遷移）、`browser_menu_smoke browser_playstation_smoke browser_i18n_smoke`，
新增 `browser_rebind_smoke.py`（重設一個鍵後真的能用它飛）。
