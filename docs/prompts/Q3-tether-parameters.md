# Q3：臍帶纜參數依公開規格校準（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。纜線是主動的力（AGENTS.md），它的參數要有出處。
1. 蒐集觀測級 ROV 常用中性浮力臍帶纜的公開規格：外徑、空氣中與水中每公尺重量、破斷強度、最小彎曲半徑；以及圓柱橫流阻力係數與切向阻力係數、渦激振動的文獻值。只用公開資料，記錄出處與不確定度，寫進 docs/reference/tether-parameters.md（繁中）。不得寫入品牌名稱。
2. 對照 simulator/qysim 中纜線求解器（tether 相關模組）現有參數，逐項標明 measured／published／estimated，更新可由公開資料決定的值；X1 實際用的纜線規格仍標暫定。
3. 驗證：做三組可重現的情境（無流放纜 50 m、0.5 kn 橫流放纜 50 m 與 100 m）比較纜線形狀與載具受力，對照文獻或解析近似（懸鏈線、均勻流中纜線的穩態形狀），結果圖放 docs/design/tether-calibration/；單元測試鎖住關鍵數值。
4. 不改協定與 SDK 行為；效能不得明顯變差（量 0.01 s 步長的 CPU 時間前後）。
瀏覽器檢查：browser_tether_smoke browser_smoke。

共同規則：
- 先完整讀 AGENTS.md（有約束力，特別是第 5、6、8 條與「X1 專屬參數目前都是暫定值」）、docs/prompts/README.md 最後的「所有場景的共同規則」。
- 不得改動 SDK 語意與協定既有欄位；任何參數都要標明來源等級（measured／published／estimated）與出處，不得把其他機型或廠商宣稱的數字當成 X1 的事實。
- 新素材只接受 MIT／BSD／Apache／zlib／CC0／公有領域，記入 simulator/viewer/models/CREDITS.md；不得新增廠商名稱、商標或其設計外觀。
- 本機測試必跑並把指令與結果貼進 PR：cd simulator && python -m unittest discover -s tests；node --test simulator/tests/*.mjs；python ../tools/test_check_matrix.py；以及任務列出的瀏覽器檢查（python tools/run_browser_checks.py ...）。
- 從最新 main 開分支 task/<編號>-<短名>，開 draft PR，完成後轉 ready for review。
```
