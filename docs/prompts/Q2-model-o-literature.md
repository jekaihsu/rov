# Q2：Model O 依公開文獻校準（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。YX Model O 的內部 key 是 bluerov2_heavy，它對應的是一台公開資料很多的開源平台；它的參數可以、也應該用公開文獻校準（這不是 X1，X1 參數不准動）。
1. 蒐集公開來源：學術論文與學位論文中針對該平台（heavy 配置）辨識出的附加質量、線性與二次阻尼係數、浮心／重心；推進器在不同電壓下的推力—PWM 曲線（廠商公開的測試資料）；尺寸與重量。每一筆記錄出處（論文標題、作者、年份、DOI 或網址）、量測條件與不確定度，寫進 docs/reference/model-o-calibration.md（繁中）。
2. 把 simulator/qysim/vehicles.py 中 bluerov2_heavy 的參數更新為文獻值，來源等級標為 published；文獻之間不一致時說明取捨。推進器改用文獻的推力曲線（含電壓影響），若現有模型結構不足以表達，先在 PR 說明再擴充，並保持其他機型行為不變（附凍結參考測試）。
3. 驗證：重現文獻中的步階響應或自由衰減實驗（相同輸入），把模擬與文獻曲線畫在同一張圖（docs/design/model-o-calibration/），並寫單元測試把關鍵指標（極速、時間常數、偏航率）鎖在文獻容差內。
4. 不改協定與 SDK 行為；只影響 bluerov2_heavy。
瀏覽器檢查：browser_smoke browser_hud_smoke。

共同規則：
- 先完整讀 AGENTS.md（有約束力，特別是第 5、6、8 條與「X1 專屬參數目前都是暫定值」）、docs/prompts/README.md 最後的「所有場景的共同規則」。
- 不得改動 SDK 語意與協定既有欄位；任何參數都要標明來源等級（measured／published／estimated）與出處，不得把其他機型或廠商宣稱的數字當成 X1 的事實。
- 新素材只接受 MIT／BSD／Apache／zlib／CC0／公有領域，記入 simulator/viewer/models/CREDITS.md；不得新增廠商名稱、商標或其設計外觀。
- 本機測試必跑並把指令與結果貼進 PR：cd simulator && python -m unittest discover -s tests；node --test simulator/tests/*.mjs；python ../tools/test_check_matrix.py；以及任務列出的瀏覽器檢查（python tools/run_browser_checks.py ...）。
- 從最新 main 開分支 task/<編號>-<短名>，開 draft PR，完成後轉 ready for review。
```
