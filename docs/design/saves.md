# 存檔盤點與損毀處理（S3）

成功標準：連續遊玩時存檔都保留；讀到壞資料不得讓遊戲壞掉。共用實作在
`simulator/viewer/saves/store.js`（版本號、遷移、壞檔備份）與
`simulator/desktop/save_files.cjs`（桌面原子寫入）。桌面路徑見文末。

## localStorage / 桌面 `userData/saves/`

| 鍵名 | 版本 | 寫入時機 | 損毀時怎麼辦 |
|---|---|---|---|
| `rov.career.v1` | 1 | 結算、購買、日誌、放棄潛航、考試 stash | `normalizeSave` 夾住欄位；無法解析 → 預設存檔並從 campaign/results 遷移；原文備份到 `rov.career.v1.corrupt` 與 `saves/corrupt/` |
| `rov.campaign.v1` | 1 | 房主、劇情非 idle 且內容變更時 | 退回空進度；備份壞檔；桌面另有 collection `campaign-progress` 鏡像 |
| `rov.results.v1` | 1 | 破最佳分數／獎牌時 | 退回 `{}`；備份壞檔；略過 `version` 欄位讀各關紀錄 |
| `rov.fidelity.v1` | 1 | 任一擬真項目或預設組變更 | 退回版本預設（Steam→assisted，其餘→real）；備份壞檔 |
| `rov.input.v1` | 1 | 手把／按鍵設定變更 | 退回空設定；桌面 `preferences.json` 的 `input` 可覆寫；超大拒絕 |
| `rov.display.v1` | 1 | 顯示偏好變更 | 退回預設；語言未選過不寫入，避免鎖死繁中 |
| `rov.audio` | 1 | 音量／靜音變更 | 退回預設音量 |
| `rov.onboarding.v1` | 1 | 完成教學步驟、重設、開關提示 | 退回全新進度（提示開啟） |
| `rov.achievements.v1` | 1 | 解鎖成就／圖鑑類別 | 退回空清單；Steam 另有自己的紀錄 |
| `rov.coldOpen.v1` | 1 | 看過開場、設定開關、重玩開場 | 退回 `{seen:false, enabled:true}` |
| `rov.objectiveCard.v1` | 1 | 潛航次數、收合／隱藏卡片 | 退回 `{dives:0,…}` |
| `rov.quality.learned.v1` | 1 | 自動畫質在遊戲視角收斂時 | 忽略並改用硬體提示；備份壞檔 |
| `rov.menu.last.v1` | 1 | 下水前記住快速開始 | 退回空物件 |
| `rov.menuSettings` | 1 | 介面開關（PIP、下水動畫、搖桿…） | 退回介面預設 |
| `rov.controlLayout.v1` | 1 | 操控佈局選擇 | 非法值 → `ROV_USA` |
| `rov.playerName` | 1 | 名稱變更／下水 | 退回「操作員」 |
| `rov.vehicle` | 1 | 機型選擇 | 退回 `x1`；桌面亦寫 `preferences.json` |
| `rov.quality` | 1 | 畫質選擇 | 退回 `auto`；桌面亦寫 `preferences.json` |
| `rov.mission` | 1 | 任務模式選擇 | 退回 `campaign` |
| `rov.sticker` | 1 | 貼紙選擇 | 退回 `none` |
| `rov.operatorVisible` | 1 | PIP 開關 | 退回 `false` |
| `rov.hud.drawer` | 1 | 工程抽屜開關 | 退回關閉 |
| `rov.pilotGuide.dismissed.v1` | 1 | 關閉導引並記住 | 退回顯示 |

`sessionStorage` 的 `rov.session:<ws>:<room>` 只活在分頁內（重連 resume_token），不算長期存檔。

## 收藏與桌面檔案

| 鍵名／路徑 | 版本 | 寫入時機 | 損毀時怎麼辦 |
|---|---|---|---|
| IndexedDB `rov-personal-collection` / 桌面 `collection/` | 1 | 拍照、結果、封面、匯入 | 寫入前驗證；匯入拒絕壞格式；桌面原子 tmp+fsync+rename |
| `preferences.json` | 1 | 機型／畫質／input IPC | 解析失敗 → 預設；原子寫入 |
| `window.json` | 1 | 顯示模式／Alt+Enter | 驗證失敗 → Deck 全螢幕或工作區視窗；原子寫入 |
| `userData/saves/<key>.json` | 與上表相同 | 每次 `localStorage.setItem('rov.*')`（桌面鏡像） | 讀失敗略過該鍵；壞檔可進 `saves/corrupt/` |

## 桌面路徑與 Steam 雲端

Electron `app.getPath('userData')`（Windows 通常在 `%APPDATA%/ROV Simulator`）：

```
userData/
  preferences.json
  window.json
  saves/                 ← Steam Auto-Cloud 同步此資料夾（不含 corrupt/）
    rov.career.v1.json
    rov.campaign.v1.json
    …
    corrupt/             ← 損毀備份，不進雲端
  collection/
    index.json
    photos/
  local-backups/<stamp>/ ← 每次啟動快照（含 saves/）
  reports/
```

寫入皆先寫 `*.tmp-<uuid>`，`fsync` 後再 `rename`（`desktop/save_files.cjs`）。
Steam Auto-Cloud 規則見 `simulator/desktop/steam/RELEASE.md`：包含 `saves/**`，排除
`saves/corrupt/**`、`local-backups/**`、logs、`numba-cache`。

## 測試

- `node --test simulator/tests/test_save_store.mjs`：空、舊版、損毀 JSON、超大、欄位缺漏。
- `node simulator/desktop/test_save_files.cjs`：原子寫入與鍵名防護。
