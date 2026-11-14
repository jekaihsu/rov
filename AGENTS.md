# 給程式代理（Codex / Cursor / Claude）的工作規範

本專案是 ROV 模擬器，同時服務兩個目標：

1. **公司內部**：操作員教育訓練；以及 ROV SDK／AI／系統整合的開發沙盒（`simulator/sdk_mock`）。
2. **Steam 發行**：要好看、好玩、手感絲滑，並支援市面上絕大多數手把。

兩者共用同一套物理與協定。遊戲化只能加在「控制輔助層」與「前端呈現層」，**不得為了好玩改動物理真實性或 SDK 語意**。

## 目錄

| 路徑 | 內容 |
|---|---|
| `simulator/qysim/` | Python 模擬後端（物理、纜線、洋流、房間、任務）。主機權威，固定 0.01 s 步長 |
| `simulator/viewer/` | 瀏覽器前端（three.js r160，原生 ES modules，無打包工具） |
| `simulator/desktop/` | Electron 桌面殼與 Steam 上傳範本 |
| `simulator/sdk_mock/` | 模擬廠商 SDK，供既有程式不改碼連到模擬器 |
| `simulator/tests/`、`simulator/tools/` | 單元測試；瀏覽器 smoke 與建置工具 |
| `docs/tasks/` | 任務書。每個 PR 對應一份 |
| `docs/design/ui-direction.md` | 前端視覺與互動方向。所有前端任務必讀 |
| `docs/showcase/` | **產生物**，由 `simulator/tools/build_showcase.py` 產生。功能 PR 不得修改 |

## 流程

- 基底分支 `main`。每份任務書開一個分支 `task/<編號>-<短名>`，一個 PR。PR 標題以任務編號開頭，例如 `T02: 輸入層`。
- PR 描述須包含：做了什麼、如何驗證（貼上實際執行的指令與結果）、未完成或有疑慮的部分。前端變更附前後截圖。
- 不要順手做任務書以外的事。發現別的問題，寫在 PR 描述的「後續」段落。
- 審查與合併由 Claude 負責。CI 未過不合併。

## 硬性規則

1. **相容性**：`simulator/PROTOCOL.md` 的既有欄位與 `sdk_mock` 的行為不得破壞。新增欄位一律選填，未提供時行為與現在完全相同。協定有變就同步更新 `PROTOCOL.md`。
2. **測試**：`cd simulator && python -m unittest discover -s tests` 必須全過。新增後端邏輯必須附測試。不得為了過 CI 跳過、刪除或放寬既有測試。
3. **`simulator/viewer/app.js` 是衝突熱點**：新功能寫在新模組，`app.js` 只留最小的 import 與呼叫。不要重新排版、不要改動無關行。動到的那段邏輯請搬進你的模組，而不是在原地加長。
4. **程式風格**：新程式一行一個敘述，行寬不超過 120 字元，具名函式，檔頭一段註解說明模組職責。不要模仿現有檔案裡把多個敘述擠在同一行的寫法。
5. **不加打包工具與框架**：前端維持原生 ES modules。要新增 npm 依賴或第三方資產，先在 PR 描述說明授權（僅接受 MIT／BSD／Apache／CC0），並更新 `simulator/viewer/models/CREDITS.md`。
6. **不提交產生物與大型二進位**：建置輸出、`node_modules`、錄影、超過 2 MB 的新資產都需要在 PR 描述中說明理由。
7. **文字**：使用者看得到的字串集中管理，不要散落硬編碼（見 T09）。在 T09 合併前，新字串放進你模組頂部的一個 `STRINGS` 物件。
8. **品牌**：新程式與新介面文字不得新增廠商名稱、機型商標或其設計外觀的引用。

## 共用契約：飛行輔助（T01 定義，其他任務依此實作）

RC 封包新增選填欄位：

```json
{"type":"rc","seq":12,"rc":{"right_ud":1600,"assist":2,"profile":"normal"}}
```

- `assist`：`0` 手動（現行行為，推桿即推力）；`1` 速度輔助（推桿為機體座標速度指令，鬆桿主動煞停）；`2` 定點輔助（同 1，且鬆桿後鎖定對地位置並抵抗洋流）。未提供視為 `0`。
- `profile`：`"cine"`、`"normal"`、`"sport"`。只影響速度上限、加速度、偏航角速度與搖桿曲線。未提供視為 `"normal"`。

`state` 新增：

```json
"assist": {"level":2,"profile":"normal","holding":true,"limited":false,
           "speed_limit":[1.2,0.8,0.5],"yaw_rate_limit":45}
```

`holding` 表示正在定點；`limited` 表示推力飽和、輔助無法維持指令（例如洋流過強）。SDK 取得遠端控制時輔助停用。

## 本機執行

```bash
cd simulator
pip install -r requirements.txt
python -m qysim.server            # http://127.0.0.1:8080/  加 ?nointro 跳過下水動畫
python -m unittest discover -s tests
```

瀏覽器驗證用 `simulator/tools/browser_*.py`（Playwright）。前端任務至少跑 `browser_smoke.py` 與 `browser_menu_smoke.py`。
