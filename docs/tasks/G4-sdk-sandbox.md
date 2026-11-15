# G4：SDK 沙盒文件與範例

**目標**：感測器層改為估計值後，更新 `sdk_mock` 文件與可直接跑的整合範例，讓既有 SDK／AI／系統整合程式不改碼就能在模擬器上開發，並理解讀值來源與失效行為。

**範圍**：`simulator/sdk_mock/README.md`、`simulator/sdk_mock/examples/`、`simulator/tests/`。不改 `sdk_mock` 既有行為與既有欄位，不改物理。

**要做**

1. **文件**（繁體中文）：標明每個 SDK 讀值在模擬器裡的來源（感測器估計或真值）、更新頻率、與真機可能差異；說明 `QYSIM_SENSORS=ideal`；標明依真機資料與假設。
2. **範例**（`python examples/xxx.py --host …`）：
   - 定深＋定向巡航，DVL 失鎖時退回只定深。
   - 沿結構物定距巡檢，處理前向測距無回波與盲區。
   - 外部 AI 偵測：讀相機、簡單 OpenCV 偵測、送 `vision_results`、示範遠端控制取得與釋放。
3. **測試**：每支範例的無頭整合測試（啟動模擬器、跑約 30 秒模擬時間、斷言行為）；執行時間短、不依賴外網。
4. 發現 SDK 與 `PROTOCOL.md` 不一致只回報於 PR「後續」，不擅改。

**驗證**：`cd simulator && python -m unittest discover -s tests` 全過；PR 描述貼上每支範例實際執行輸出。
