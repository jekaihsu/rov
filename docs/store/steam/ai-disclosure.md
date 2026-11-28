# Steam「AI 生成內容揭露」問卷答案草稿

> **草稿，需法務／發行審閱。** 依 `simulator/viewer/models/CREDITS.md` 與商店文案（`page.md`）填寫。送審前請用候選 Steam build 再核對一次實際包內資產。

基準：CREDITS.md（魚類 Fish Kit、無線電語音、商店文案提及的 AI 協助翻譯／起草）。

## 建議勾選與說明

### 1. 本產品是否包含 AI 生成內容？

**是。**

### 2. 哪些類型？（依 Steam 問卷當時選項對應勾選）

| 類型 | 是否使用 | 依 CREDITS.md 的依據 |
|---|---|---|
| AI 生成的**語音／音訊** | 是 | 無線電語音：OpenAI text-to-speech（`gpt-4o-mini-tts` 等）預先合成為 Ogg Opus，隨包發行 |
| AI 生成的**圖像／貼圖** | 是（預製資產） | Fish Kit 側視貼圖：套件說明為 OpenAI 圖像生成後再於 Blender 建網；本專案以 CC0 導入，執行時不生成 |
| AI 生成的**文字** | 部分／發行素材 | 商店說明與部分翻譯曾以 AI 協助起草，**發布前須人工審核**；遊戲內任務文案以人工與專案字串為主（送審前再確認是否有殘留 AI 草稿） |
| AI 生成的**程式碼** | 否（不作為玩家可見內容揭露重點） | 開發工具可能使用 AI 輔助，但不構成玩家面對的生成內容 |
| AI 生成的**音樂** | 否 | 配樂為公有領域／CC0 錄音，非 AI 作曲 |

### 3. 是否在執行時（玩家遊玩時）即時生成？

**否。** 語音與魚類貼圖均為**預先製作並打包**；執行時不連線呼叫 AI API 產生這些內容。

### 4. 玩家能否區辨／關閉？

- 語音：可調音量／靜音（音訊設定）；內容為預錄無線電台詞。
- 魚類貼圖：為場景資產的一部分，無單獨「關閉 AI 貼圖」開關；來源已在 CREDITS 與本揭露說明。
- 擬真設定可關閉部分輔助與美化，但與上述預製 AI 資產無關。

### 5. 商店頁建議公開說明（可貼短版）

**繁中：**  
本作的無線電對話語音使用 AI 語音合成預先製作。水中魚類模型的部分貼圖取自第三方 CC0 素材包，該包貼圖為預先以 AI 圖像生成（非實拍），隨遊戲發行；執行時不再生成。另有以 AI 協助起草並經人工審核的商店文案／翻譯。

**English：**  
Radio dialogue is pre-made with AI text-to-speech. Some fish model textures come from a third-party CC0 kit whose textures were pre-generated with AI image tools (not photographs) and ship with the game; nothing is generated at runtime. Store copy and translations may use AI drafting with human review before publication.

### 6. 送審前核對清單

- [ ] 候選 build 內 `audio/voice/` 與 `models/fish/` 確實存在且與 CREDITS 一致  
- [ ] 確認沒有執行時呼叫外部 AI API  
- [ ] 商店四語「AI 內容揭露」段落與本問卷一致  
- [ ] 法務確認揭露用語與所在地標示義務  

---

文件狀態：草稿 · 需法務／發行審閱 · 依 CREDITS.md 2026-11 內容
