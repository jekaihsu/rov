# N2：在你的電腦上產生序章無線電語音（需要你的 OpenAI 金鑰）

> 整段貼給你本機的代理。金鑰只放在你電腦的環境變數，**不得寫進任何檔案、不得提交、不得貼到對話裡**。

## 先決條件

- 已照先前的說明 clone 了 `jekaihsu/rov`，並在 `simulator/` 建好 Python 虛擬環境。
- 已安裝 `ffmpeg`（語音後製要用；沒有就先裝：macOS `brew install ffmpeg`，Windows `winget install ffmpeg`）。
- 我（擁有者）會自己在終端機設定 `OPENAI_API_KEY`；若沒設定，請停下來提醒我，**不要**要我把金鑰貼給你。

## 步驟

```bash
cd rov
git checkout main && git pull
git checkout -b task/N2-prologue-voice
source simulator/.venv/bin/activate          # Windows：simulator\.venv\Scripts\activate
python simulator/tools/voice/extract_lines.py --chapter prologue --language zh-TW
python simulator/tools/voice/synthesize.py --chapter prologue --language zh-TW
```

（`synthesize.py` 只從環境變數讀金鑰；已存在的語音會跳過，可重跑。）

## 完成後回報

1. 產生了幾個檔案、總大小、最大的一個多大（每個不得超過 2 MB）。
2. 隨機挑 5 句，列出檔名、角色、台詞，讓我自己聽。
3. 啟動遊戲（`cd simulator && python -m qysim.server`，開 `http://127.0.0.1:8080/`），進「劇情與教學」的序章，
   確認無線電有聲音、字幕和聲音對得上；有問題就貼 Console 的錯誤。
4. **先不要開 PR。** 等我聽過、說可以，再 `git add simulator/viewer/audio/voice/` 提交並開 draft PR，
   PR 描述要寫：使用的語音服務與模型、該服務對商用輸出的條款連結、每句台詞都是 AI 合成。

## 我聽的時候要注意

- 每個角色的聲音是否符合 `docs/story/bible.md` 的設定（年齡感、語速、語氣）。
- 無線電失真會不會太重或太輕（目前是合成時烘進檔案的；若要調整，告訴我，我們再決定要不要改成即時處理）。
- 有沒有讀錯字、斷句怪、或不自然的停頓。
