# 預告片錄製工具（S5）

依 JSON 分鏡，用固定時間步把遊戲畫面錄成 1920×1080／60 fps 素材。  
這套工具**產生素材**，不負責剪成片；商店 80 秒分鏡見 `docs/store/steam/trailer.md`。

## 需要什麼

| 項目 | 說明 |
|---|---|
| Python 3.11+ | 與模擬器相同；已安裝 `simulator/requirements.txt` |
| Playwright + Chromium | `pip install playwright` 後 `python -m playwright install chromium` |
| ffmpeg | 組成 MP4；無損可用 `--lossless` |
| Pillow | 代表畫面壓成 ≤ 300 KB JPEG |
| 記憶體／磁碟 | 每秒約 60 張 PNG（約 5–15 MB/s 未壓）；建議預留數 GB |
| 時間（軟體 GL） | 5 秒測試鏡約 5–15 分鐘牆鐘；80 秒全部分鏡一次跑完可能要數小時 |

環境變數與其他瀏覽器腳本相同：`ROV_CHROMIUM`、`ROV_BROWSER_TIMEOUT_SCALE`、`ROV_BROWSER_GL`（預設 software）。

## 分鏡 JSON

路徑：`simulator/tools/trailer/storyboards/`

| 檔案 | 用途 |
|---|---|
| `test_5s.json` | 5 秒港灣 FPV，驗證管線 |
| `store_80s.json` | 商店 80 秒（對應 trailer.md；開場可重用 `cold_open_jacket`） |
| `demo.json` | 較短的 demo 剪輯素材 |

每個鏡頭可寫：`scenario`／`seed`、`duration`、`camera`（`onboard`／`follow`／`orbit`／`fixed` + Catmull-Rom 關鍵影格）、`drive`（推力腳本）、`hud`、`weather`。

### `hud`（逐鏡頭）

錄影模式預設藏標題卡、工具列、目標線框／標籤與除錯 UI。`hud` 只決定要留哪些飛行儀表：

| 值 | 效果 |
|---|---|
| `false`／`"off"` | 全關 |
| `"minimal"` 或 `["depth","heading"]` | 深度＋航向（開場建議） |
| `true`／`"full"` | 完整飛行儀表（仍無工具列／標題卡） |
| 字串陣列 | 自選：`depth` `heading` `attitude` `map` `status` `mission` `telemetry` `warning` |

## 怎麼跑

在儲存庫根目錄：

```bash
# 單元測試（插值、分鏡）
cd simulator && python3 -m unittest tests.test_trailer_catmull tests.test_trailer_storyboard
node --test tests/test_trailer_camera_path.mjs tests/test_trailer_recording.mjs

# 錄 5 秒測試鏡頭（會自己開伺服器；輸出在 output/trailer/）
python3 simulator/tools/trailer/run.py \
  --storyboard simulator/tools/trailer/storyboards/test_5s.json

# 只烤回放、不開瀏覽器
python3 simulator/tools/trailer/run.py \
  --storyboard simulator/tools/trailer/storyboards/store_80s.json --bake-only

# 每個鏡頭只出一張審核靜幀（給 docs/design/trailer/，比全序列快很多）
python3 simulator/tools/trailer/run.py \
  --storyboard simulator/tools/trailer/storyboards/store_80s.json --hero-only

# 指定鏡頭；保留 PNG；近無損
python3 simulator/tools/trailer/run.py \
  --storyboard simulator/tools/trailer/storyboards/demo.json \
  --shots demo-01-cold-open,demo-02-harbor-fpv \
  --keep-frames --lossless
```

若伺服器已在跑，可傳 `--http-port`／`--ws-port`（或設 `ROV_HTTP_PORT`／`ROV_WS_PORT`）。

## 輸出（皆不提交）

```
output/trailer/                 # 儲存庫根目錄（任務書路徑）
  <shot-id>/clip.json           # 烤好的回放
  <shot-id>/frames/             # PNG 序列（可刪）
  <shot-id>/<shot-id>.mp4
  <shot-id>/hero.png
  manifest.json
docs/design/trailer/<shot-id>.jpg   # ≤ 300 KB，給擁有者審分鏡（提交）
```

`simulator/viewer/_trailer_clips/` 是捕捉時暫存的回放副本，已在 `.gitignore`。

## 管線

1. **Bake**：後端 `Simulator` 固定 0.01 s 步長，依 `drive` 腳本採樣 60 Hz → `qysim-replay-2` 回放。不改物理。
2. **Capture**：Playwright（`_browser.py`）開 `?replay=…&capture&trailer=1&quality=ultra`；每幀 `__advance(1/60)` 後截 PNG。畫面不卡在牆鐘。
3. **錄影模式**（`viewer/trailer/recording.js`）：藏除錯／標題卡／目標輔助、URL 最高畫質（不寫 localStorage）、套用攝影機路徑與逐鏡 HUD。
4. **Encode**：ffmpeg 合成 MP4。
5. **Hero**：每鏡一張 JPEG ≤ 300 KB 到 `docs/design/trailer/`。

## 攝影機模式

- `onboard`：機載 FPV（真機預設視角）
- `follow`：相對機體的偏移（右／上／後），Catmull-Rom
- `orbit`：方位角／半徑／高度環繞
- `fixed`：世界座標機位與看點

## 注意

- 不提交影片與 PNG；只提交工具與分鏡 JSON、代表畫面。
- 字卡文字在分鏡的 `cards` 欄，給後製用；遊戲畫面不燒字。
- 預潛／講評等 UI 鏡若要實拍介面，另開鏡頭補；本工具以潛航畫面為主。
- `?trailer=0` 不會開啟錄影模式；必須 `trailer=1`（或 `true`／`on`）。

## K2 劇情過場

`python simulator/tools/trailer/cinematic.py` 使用遊戲的分鏡繪圖器與本工具的 ffmpeg 編碼器，
直接錄製港區與航圖兩支示範。參數與分鏡欄位見[過場審查頁](../../../docs/design/cinematics-k2/README.md)。
