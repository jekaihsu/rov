# K2 無線電 AI 配音

**目標**：為無線電對話建立可重跑的 AI 語音合成流程，並先產出序章繁中配音；播放時自動壓低音樂，沒有音檔時退回純文字。

**範圍**：`simulator/tools/voice/`（抽取與合成）、`simulator/viewer/audio/voice.js` 與音檔目錄、設定「語音」音量、`CREDITS.md` 揭露。不改物理／SDK；語音為呈現層。

**要做**

1. 從劇情與委託（campaign JSON）抽出無線電台詞 → `voice_manifest.json`（穩定內容雜湊 id、角色、語言、文字）。
2. OpenAI TTS 合成；金鑰只讀 `OPENAI_API_KEY`；角色聲音與風格在 JSON；後製無線電效果與 −18 LUFS，輸出單聲道 Ogg Opus ~32 kbps。
3. 先只產生序章 `zh-TW`；目錄依語言分開，架構可接 en／zh-CN／ja。
4. 對話出現時播放對應音檔；缺檔不報錯；音樂壓低；設定加語音音量。
5. 製作名單註明 AI 語音合成；PR 附 OpenAI 商用／揭露政策連結與角色聲音表。

**測試**：台詞抽取與 id 穩定性、缺檔退回的 node 單元測試；`python -m unittest discover -s tests`；`node --test simulator/tests/*.mjs`；`browser_audio_smoke`／`browser_music_smoke`／`browser_results_smoke`。
