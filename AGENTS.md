# 給程式代理（Codex / Cursor / Claude）的工作規範

本專案是 ROV 模擬器，同時服務兩個目標：

1. **公司內部**：操作員教育訓練；以及 ROV SDK／AI／系統整合的開發沙盒（`simulator/sdk_mock`）。
2. **Steam 發行**：要好看、好玩、手感絲滑，並支援市面上絕大多數手把。

**最高目標：體驗與真實 ROV 一致。** 依據是 `docs/reference/real-rov-research.md`（研究報告）與 `docs/reference/own/`（自有 X1 實測）。任何畫面、手感、流程的決定，先查這兩處；查不到就在 PR 描述中寫明是假設，不要憑印象。

- **真實模式是預設，也是驗收基準**：控制語意照真機（水平方向推桿是推力；定深、定向為閉迴路；定點只在 DVL 有效時可用）；駕駛以機載第一人稱為主，第三人稱是訓練輔助；纜線是主動的力；影像有延遲。
- **輔助與美化是可關的另一層**：超出真機能力的輔助、第三人稱運鏡、畫面美化都必須能關，且關掉後等同真實模式。Steam 版可以預設開部分輔助，內部訓練版預設全關。
- **X1 專屬參數目前都是暫定值**：公開資料不足，待 `docs/reference/x1-measurement-checklist.md` 的實測補齊。不得把其他機型或廠商宣稱的數字當成 X1 的事實寫死。

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
| `docs/reference/` | 真實 ROV 研究報告、X1 實測清單與自有實測資料。所有任務必讀 |
| `docs/showcase/` | **產生物**，由 `simulator/tools/build_showcase.py` 產生。功能 PR 不得修改 |

## 流程

- 基底分支 `main`。每份任務書開一個分支 `task/<編號>-<短名>`，一個 PR。PR 標題以任務編號開頭，例如 `T02: 輸入層`。
- PR 描述須包含：做了什麼、如何驗證（貼上實際執行的指令與結果）、未完成或有疑慮的部分。前端變更附前後截圖。
- 不要順手做任務書以外的事。發現別的問題，寫在 PR 描述的「後續」段落。
- 審查與合併由 Claude 負責。CI 未過不合併；CI 額度用完時，由審查者在本機重跑測試代替。

## CI 額度（GitHub Free，每月內含額度有限）

- 開發中請開 **draft PR**，draft 不跑 CI。完成後再轉為 ready for review。
- 不要為了觸發 CI 一直推小提交。在本機跑完測試、一次推上去。PR 描述裡貼上本機測試的指令與結果，這是必要的，不能只依賴 CI。
- **禁止**在 `pull_request` 或 `push` 觸發 Windows／macOS runner（計費是 Linux 的數倍）。這類工作只能用 `workflow_dispatch` 手動觸發，或在推送版本 tag 時觸發。
- 瀏覽器（Playwright）類的 CI 工作，必須用 `paths` 限定只在 `simulator/viewer/**` 變更時執行。
- 新增 workflow 必須設 `timeout-minutes` 與 `concurrency: cancel-in-progress: true`。

## 硬性規則

1. **相容性**：`simulator/PROTOCOL.md` 的既有欄位與 `sdk_mock` 的行為不得破壞。新增欄位一律選填，未提供時行為與現在完全相同。協定有變就同步更新 `PROTOCOL.md`。
2. **測試**：`cd simulator && python -m unittest discover -s tests` 必須全過。新增後端邏輯必須附測試。不得為了過 CI 跳過、刪除或放寬既有測試。
3. **`simulator/viewer/app.js` 是衝突熱點**：新功能寫在新模組，`app.js` 只留最小的 import 與呼叫。不要重新排版、不要改動無關行。動到的那段邏輯請搬進你的模組，而不是在原地加長。
4. **程式風格**：新程式一行一個敘述，行寬不超過 120 字元，具名函式，檔頭一段註解說明模組職責。不要模仿現有檔案裡把多個敘述擠在同一行的寫法。
5. **不加打包工具與框架**：前端維持原生 ES modules。要新增 npm 依賴或第三方資產，先在 PR 描述說明授權（僅接受 MIT／BSD／Apache／zlib／CC0，或公有領域（Public Domain Mark）的錄音與素材），並更新 `simulator/viewer/models/CREDITS.md`。
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

**前端送出條件（重要）**：尚未支援輔助的伺服器會因 `profile` 是字串而拒絕整個 RC 封包（`invalid_command`），導致解鎖與操控全部失效。前端**只有在收到的 `state` 含有 `assist` 物件時**，才可以在 RC 封包中加入 `assist`／`profile`；否則一律不送。

`state` 新增：

```json
"assist": {"level":2,"profile":"normal","holding":true,"limited":false,
           "speed_limit":[1.2,0.8,0.5],"yaw_rate_limit":45}
```

`holding` 表示正在定點；`limited` 表示推力飽和、輔助無法維持指令（例如洋流過強）。SDK 取得遠端控制時輔助停用。

## 共用契約：擬真設定（fidelity profile）

「真實模式／輔助模式」只有一個來源：`simulator/viewer/fidelity.js`。不要再各自發明開關、URL 參數或 localStorage 鍵。

- 預設組：`real`（與真機一致，內部訓練版預設）、`assisted`（Steam 版預設，僅在 `window.rovDesktop?.edition === 'steam'` 時）、
  `custom`（使用者改了任何一項非偏好項目時自動顯示）。
- 優先順序：項目自己的 URL 參數（`cam`、`gimbal`、`videoDelayMs`、`presentation=assisted`、`thirdPerson`）＞
  `?fidelity=real|assisted`＞localStorage（`rov.fidelity.v1`）＞版本預設。
- 讀取與訂閱：`getFidelity().get(id)`、`.set(id, value)`、`.setPreset(name)`、`.subscribe(listener)`、`.preset`。
  設定可在飛行中變更，使用端必須訂閱變更，不要只在啟動時讀一次。
- **任何超出真機能力的功能（畫面美化、AI 疊圖、聲納輔助、額外視角、控制輔助…）都必須註冊一個項目，且在 `real` 預設為關**：

```js
import {registerFidelityItem, getFidelity} from './fidelity.js';
registerFidelityItem({
  id: 'aiOverlay', labelKey: 'aiOverlay', descriptionKey: 'aiOverlayHelp', type: 'toggle',  // 或 'choice'、'range'
  defaults: {real: false, assisted: true}, exceedsReal: true
}, {aiOverlay: 'AI 疊圖', aiOverlayHelp: '在畫面上標示辨識結果。'});
```

- `exceedsReal: true` 的項目在 `real` 的預設值若仍超出真機，註冊時會直接丟出錯誤。設定面板（`fidelity_panel.js`，
  主選單與工程抽屜各一份）會自動列出新項目並標上「超出真機」，不需要另外做 UI。
- 純偏好、不影響擬真程度的項目（例如 HUD 密度）設 `presetNeutral: true`，改動後不會變成「自訂」。
- `camera_rig.js` 與 `state_buffer.js` 會被單元測試以 data URL 載入，不能有相對路徑 import；fidelity 由 `app.js` 以參數傳入。
- 測試：`node --test simulator/tests/test_fidelity.mjs`。

## 本機執行

H4 共用選測入口（在儲存庫根目錄執行，審查者與代理皆使用）：

```bash
python tools/run_checks.py --changed                 # main 分歧點到工作樹，含未追蹤檔；快速層
python tools/run_checks.py --changed --tier full     # 相同變更路徑的完整層
python tools/run_checks.py --tier full              # 全部單元、Node 與標準瀏覽器檢查
python simulator/tools/run_browser_checks.py --tier quick
python simulator/tools/run_browser_checks.py --tier full
```

先安裝 `simulator/requirements.txt`、`numba`、`playwright` 與 Node 22，並執行
`python -m playwright install chromium`。使用 `--base <ref>` 可指定比較基底。
選測規則在 `tools/check_matrix.py`；`--changed` 不取代下列完整單元測試規則。
時間與分層範圍見 `docs/ci/timings.md`。完整瀏覽器層需要先執行
`node simulator/desktop/test_collection_store.cjs` 產生測試用收藏資料。

```bash
cd simulator
pip install -r requirements.txt
python -m qysim.server            # http://127.0.0.1:8080/  加 ?nointro 跳過下水動畫
python -m unittest discover -s tests
```

瀏覽器驗證用 `simulator/tools/browser_*.py`（Playwright）。前端任務至少跑 `browser_smoke.py` 與 `browser_menu_smoke.py`。

```bash
cd simulator
python tools/run_browser_checks.py browser_smoke browser_menu_smoke   # 自動在空閒埠啟動伺服器，結束後列出通過／失敗表
python tools/run_browser_checks.py                                    # 預設的完整檢查清單；--list 列出所有腳本
```

- 所有瀏覽器腳本一律透過 `simulator/tools/_browser.py` 啟動瀏覽器與取得網址，不要在腳本裡直接呼叫 `chromium.launch(...)` 或寫死埠號。
- 環境變數：`ROV_CHROMIUM`（瀏覽器執行檔絕對路徑）、`ROV_HOST`／`ROV_HTTP_PORT`／`ROV_WS_PORT`（伺服器位址與埠）、`ROV_BROWSER_TIMEOUT_SCALE`（慢機器上放大等待時間）。

## 輸入心跳與失聯保護

RC 封包由 Web Worker 中的連線送出（`simulator/viewer/input/rc_worker.js`），畫面卡頓時仍會補送心跳：

- 頁面每 33 ms 取樣一次，有變化或每 100 ms 轉交 Worker；Worker 在線路靜默約 150 ms 時重送最後一個封包。
- 頁面停止回應時，Worker 最多代為重送 2 秒（`RC_TIMING.holdMs`），之後伺服器的 0.6 秒失聯保護才生效。也就是頁面卡死但分頁仍開著時，約 2.6 秒後上鎖；關閉分頁、當機、斷網仍是 0.6 秒。這是經使用者同意的取捨。
- 分頁隱藏、收藏面板開啟、回放、控制器橋接、`input_latched` 重新同步時一律停止重送。不得移除這些條件。
