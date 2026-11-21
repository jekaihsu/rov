# S7：法律文件、第三方授權與製作名單（Codex，主要寫文件）

> 先完整讀 `AGENTS.md`、`simulator/viewer/models/CREDITS.md`、`simulator/desktop/`、`docs/store/`。分支 `task/S7-legal-credits`。

1. **第三方授權清單**：自動產生（寫工具 `simulator/tools/third_party_notices.py`）列出所有 npm 套件、Python 套件（打包進
   桌面版的）、three.js、字型、音效、模型、貼圖、掃描材質的名稱、版本、授權、來源連結；輸出
   `simulator/desktop/THIRD_PARTY_NOTICES.txt`，打包時附上。發現授權不在允許清單（MIT／BSD／Apache／zlib／CC0／公有領域）
   的項目，列在 PR 描述，不要自己移除。
2. **遊戲內製作名單與授權畫面**：設定或關於頁中可捲動的名單與授權全文，手把可操作；字串四語。
3. **EULA 與隱私權政策草稿**（`docs/store/legal/`，繁中與英文）：遊戲不收集個資、不連網（除 Steam 本身）、存檔在本機與
   Steam 雲端；AI 生成內容的揭露（魚貼圖等，見 CREDITS.md）；模擬器不是真實操作認證的聲明。標明「草稿，需法務審閱」。
4. Steam 商店需要的「AI 生成內容揭露」問卷答案草稿（`docs/store/steam/ai-disclosure.md`），依 CREDITS.md 實際內容填寫。

跑：工具的單元測試、`browser_menu_smoke`（若改了設定頁）、`browser_i18n_smoke`。
