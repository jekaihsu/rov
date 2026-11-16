# 無線電 AI 配音

1. 抽出台詞（寫入 `simulator/viewer/audio/voice/voice_manifest.json`）：

```bash
python simulator/tools/voice/extract_lines.py
python simulator/tools/voice/extract_lines.py --chapter prologue --language zh-TW
```

2. 合成（需 `OPENAI_API_KEY`；已存在的 id 會跳過）：

```bash
export OPENAI_API_KEY=...   # 勿寫入檔案或 commit
python simulator/tools/voice/synthesize.py --chapter prologue --language zh-TW
```

角色聲音與風格：`characters.json`。輸出：`simulator/viewer/audio/voice/<lang>/<id>.opus` 與 `index.json`。
