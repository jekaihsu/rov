# S2：擁有者筆電自測步驟（Intel UHD 620）

目標：開場、序章、港口、網箱、開放水域都穩定 **≥ 30 fps**，載入場景／第一次開燈／第一次魚群／拍照時沒有明顯超過 **0.2 秒** 的卡住。

## 1. 準備

1. 接上筆電電源，關閉其他佔滿 CPU 的程式。
2. 螢幕解析度用平常玩的（例如 1366×768）。
3. 用 **Chrome**（或 Steam／Electron 桌面版）開遊戲。
4. 第一次請用無痕或先清掉本機畫質記憶，避免舊的學習值干擾：
   - 開發者工具 → Application → Local Storage → 刪除 `rov.quality.learned.v1`（可選：也刪 `rov.quality`）。

## 2. 開哪個網址

本機伺服器（倉庫根目錄）：

```bash
cd simulator
python3 -m qysim.server
```

然後用 Chrome 開（把主機改成你的）：

| 要測什麼 | 網址 |
|---|---|
| 自動畫質（UHD 應直接低檔） | `http://127.0.0.1:8080/?play=1&nointro&scenario=open_water&seed=1` |
| 港口 | 同上，`scenario=harbor_inspection` |
| 網箱 | 同上，`scenario=aquaculture_pen` |
| 開場（含黑畫面預熱） | `http://127.0.0.1:8080/?play=1&scenario=cold_open_jacket&seed=1`（**不要**加 `nointro`；若已看過開場，先刪 `rov.coldOpen.v1`） |
| 強制低檔對照 | 任一網址加 `&quality=performance` |
| 強制光學（不建議在 UHD） | `&quality=medium` |

桌面版：用一般「開始」進關即可；畫質選「自動」。

## 3. 看哪個數字

畫面上右下角（或工程資訊列）的 **`NN FPS`**：

- 自動模式會顯示類似 `42 FPS · 自動 75%`——後面的百分比是目前渲染解析度比例。
- **合格**：潛航中機載視角持續 ≥ 30（最好多數時間 40–60）；第三人稱短暫掉到 28 可接受，不要長期 < 25。
- 把滑鼠移到該文字上，title 應顯示 GPU 字串含 `UHD Graphics 620`（確認 Chrome 沒走獨顯或軟體 GL）。

選配（工程抽屜開著時）：

- 畫質選單目前檔位、是否已關水下光學（低階機自動應已關）。
- `localStorage.rov.quality.learned.v1`：潛航一陣子後應寫入 `ratio`、`effectsSuppressed`；下次開同一 GPU 應直接從該檔起步。

## 4. 建議操作順序（約 10 分鐘）

1. **開放水域**自動檔：解鎖、前後左右各飛 20 秒，看 FPS 是否穩定 ≥ 30；解析度百分比若掉到 50–60% 仍 ≥ 30 就算過。
2. **開燈**：按燈光鍵到 1、再到 2。畫面不應卡死超過約 0.2 秒（第一次可能極短一頓，不應連續卡）。
3. **港口**：靠近樁群繞一圈，同樣看 FPS。
4. **網箱**：進入網箱附近，確認魚群出現時沒有長卡；FPS 仍 ≥ 30。
5. **拍照**：對準任一結構按拍照，不應明顯卡住。
6. **開場**：從頭跑一次黑畫面 → 建立鏡頭 → 接手；黑畫面期間可開工作管理員看 CPU，不應在接手瞬間大卡。

## 5. 進階（給開發／對照）

在實體 GPU 上重跑計數與幀時間（可選）：

```bash
export ROV_CHROMIUM="/path/to/chrome"
export ROV_BROWSER_GL=gpu
cd simulator
python3 tools/browser_gpu_bench.py --check
python3 tools/browser_gpu_bench.py --profile --sites open_water,harbor_inspection,aquaculture_pen,cold_open_jacket \
  --tiers performance --views onboard --machine uhd620 --attribute
```

`--check` 只看計數預算（與軟體 GL 相同）；幀時間請看本機 `NN FPS` 與 `--profile` 報告。

## 6. 回報時請附

- GPU 字串（FPS 文字的 title 或 `chrome://gpu` 的 GL_RENDERER）
- 各場景大致 FPS 範圍（機載／第三人稱）
- 是否感覺到 >0.2 s 的卡頓，發生在哪一步（載入／開燈／魚／拍照）
