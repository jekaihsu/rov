# 試玩說明（給同事）

這份說明幫你在本機跑起 **ROV Solution**、用 PlayStation 手把快速確認手感，以及用一鍵工具回報問題。回報檔只存在你的電腦，**不會自動上傳**，也不會收集個資。

## 怎麼安裝／啟動

### 桌面可攜版（建議試玩用）

若你收到 Windows 可攜包（`ROV Simulator.exe` 之類）：

1. 解壓到任意資料夾（路徑避免過長、不要放雲端同步目錄）。
2. 雙擊執行檔；首次啟動會準備模擬後端，可能多等一會兒。
3. 進主選單後可直接「開始潛航」→ 自由探索。

打包流程若要自己重做，見 `simulator/desktop/README.md` 的 Rebuild，以及 `docs/prompts/N5-windows-build.md`。

### 從原始碼（開發／除錯）

```bash
cd simulator
pip install -r requirements.txt
python -m qysim.server
```

瀏覽器打開終端機印出的位址（通常是 `http://127.0.0.1:8080/`）。加 `?nointro` 可跳過下水動畫。

## PlayStation 手把：五分鐘清單

真機手把請照這份打勾：

→ [`docs/reference/playstation-controller.md`](../reference/playstation-controller.md) 的「五分鐘手動測試清單」

重點提醒：

- 測手把前先關掉 Steam 與 DS4Windows，避免被轉成虛擬 Xbox 手把。
- USB 與藍牙各走一輪（清單第 10 步）。
- 下水動畫用手把無法跳過，請等播完（約 12 秒），或開遊戲前關掉「下水動畫」。

## 怎麼回報問題

遊戲中任選一種方式：

| 方式 | 操作 |
|---|---|
| 鍵盤 | **F8** |
| 手把（DualSense／DualShock） | **長按觸控板**（約 0.65 秒；可在手把設定重綁） |
| 暫停選單 | 鍵盤 Esc，或手把長按 Options（☰）→ **回報問題** |

接著：

1. 選分類：畫面／手感／當機／文字／其他。
2. 用**一句話**描述（例如「解鎖後右搖桿無反應」）。
3. 按「儲存回報」。只用手把、不方便打字時，描述可以留空，截圖與狀態仍會存下來。系統會自動附上：
   - 當下畫面截圖（PNG）
   - 最近約 60 秒的狀態摘要（情境、擬真設定、畫質、裝置與手把 id、幀率、伺服器日誌、主控台錯誤）

手把設定（死區、曲線、按鍵綁定）改用鍵盤 **F9**，或手把同時按 Create（Share）＋Options；F8 專門留給回報。

## 回報檔案在哪

| 版本 | 位置 |
|---|---|
| **桌面版** | 暫停選單 →「開啟回報資料夾」會直接打開。實際位置：Windows 是 `%APPDATA%\ROV Simulator\reports\<時間>\`（可貼到檔案總管網址列），macOS 是 `~/Library/Application Support/ROV Simulator/reports/<時間>/`。每筆一個資料夾，內含 `screenshot.png` 與 `report.json`。 |
| **瀏覽器** | 自動下載到瀏覽器的「下載」資料夾，檔名 `rov-report-<時間>.zip`（內含同樣的 PNG＋JSON）。 |

把整個資料夾或 ZIP 傳給開發者即可。`report.json` 只有遊戲狀態、設定、幀率、日誌與裝置型號（顯示卡、手把型號、瀏覽器版本），沒有姓名、帳號或檔案路徑；請也不要在描述裡寫密碼、帳號或個資。

## 建議試玩路徑（約 15–25 分鐘）

1. 主選單 → 開始潛航 → 自由探索 → 選一台機（建議 YX Model R）→ 選海域。
2. 完成潛前檢查／下水（若有開啟）。
3. 解鎖後前後左右移動、定深、拍照各試一次。
4. 刻意製造一次「覺得怪」的情況，按 F8 回報練習一筆。
5. 暫停 → 回主選單，確認能再進一場。

有問題先看 `docs/reference/playstation-controller.md`；仍卡住就把回報 ZIP／資料夾連同你的系統（Windows 版本、手把型號、USB 或藍牙）一起寄出。
