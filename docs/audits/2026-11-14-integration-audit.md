# ROV 模擬器 main 線整合稽核報告

稽核對象：`jekaihsu/rov` main（HEAD `1a8af07`，T17 合併後）。唯讀稽核，未修改、未提交任何檔案；結束時 `git status` 為乾淨。
標示規則：**［實跑］** = 我實際執行並觀察到；**［閱讀］** = 只由讀程式碼推得；**［推論］** = 有間接證據但未直接重現。

## (a) 結論

各 PR 單獨都能過自己的測試（Python 164 項、Node 26 項全過），但**合在一起後，預設體驗並不符合 AGENTS.md 的「真實模式」，而且有三個現在就會打到使用者的問題**：(1) 選單預設的「劇情與新手教學」對新玩家啟動的是 T22 的事故演練 `incident_compass`，不是 T12 的序章教學；(2) 戰役 JSON 以系統預設編碼讀取，在非 UTF-8 的 Windows 上伺服器一啟動就會崩潰，連帶 SDK 使用者也起不來；(3) 前端輸入層預設送 `assist:2`（定點輔助），T01 後端合併後這個預設真的生效，一解鎖就是定點保持，與「推桿即推力、輔助全關」的驗收基準相反。其餘是手把鍵位互撞（十字鍵上同時換飛行檔位、View 長按同時切 A/S/C、A 鍵同時推進對話與拍照、F 同時噴漆與切輔助）、教官監看時學員連收放纜都被擋、`numba` 沒列在 requirements 使三機房間跑不到即時、以及幾個疊層遮擋。SDK 語意在不送新欄位時沒有發現行為改變。建議先修三個 P0 與鍵位互撞，再談發行。

## (b) 執行紀錄

環境：Linux、4 核 Xeon 2.1 GHz、Python 3.13、Node 22.23、Chromium 軟體繪圖（SwiftShader，單頁 4–13 FPS）。瀏覽器腳本複製到暫存目錄執行（輸出不落在倉庫），以 `sitecustomize` 墊片把 Playwright 指到 `/opt/pw-browsers/chromium`。

| 項目 | 結果 | 實際輸出／失敗原文 |
|---|---|---|
| `pip install -r requirements.txt` + `python -m unittest discover -s tests` | 通過 | `Ran 164 tests in 249.842s OK (skipped=1)`。另裝 `numba` 後重跑：`Ran 164 tests in 123.113s OK`（0 skipped） |
| `node --test simulator/tests/*.mjs` | 通過 | `tests 26 / pass 26 / fail 0` |
| `node simulator/desktop/test_collection_store.cjs`（唯一的 `test_*.cjs`） | 通過 | `Collection storage passed: ...`。會寫入 `simulator/output/collection-validation/`（已被 gitignore；我事後已刪除） |
| `node --check`（viewer 下 44 個 JS，排除 vendor） | 通過 | 無輸出 |
| `vendor_manifest.py --check` | 通過 | `Three.js manifest: 10 files` |
| `sync_version.py --check` | 通過 | exit 0 |
| `build_showcase.py --out /tmp/showcase-audit` | 通過 | `wrote /tmp/showcase-audit (22.8 MB)` |
| 展示包靜態解析（110 個 import／fetch／href／url） | 1 個缺檔 | `index.html → controller-check.html` 不存在（HTTP 實測 404）。以靜態伺服器實際載入：進入回放、無 page error |
| `browser_smoke.py`（3 頁） | 失敗（環境） | 第 45 行 `wait_for_function('window.__viewer.S.rc.right_switch===2')` `Timeout 30000ms exceeded`。單頁探針同一步驟通過 |
| `browser_menu_smoke.py` | 通過 | `Menu flow passed` |
| `browser_hud_smoke.py` | 通過 | `HUD geometry, tap timeout, hold/release, D-pad adapter, hiding and drawer persistence passed.` |
| `browser_campaign_smoke.py` | **失敗（真缺陷）** | 首次因環境缺 ffmpeg（腳本要錄影）中止；關掉錄影後重跑兩次，皆在第 27 行 `wait_for_function('window.__viewer?.S?.campaign?.chapter === "prologue"')` `Timeout 90000ms exceeded`。見 P0-1 |
| `browser_camera_smoke.py` | 通過 | `Real onboard default, input actions, orbit, gimbal and physical capture restore passed` |
| `browser_camera_input_smoke.py` | 通過 | `Live V cycle, orbit pad ownership, B/G separation and settings focus guards passed.` |
| `browser_input_smoke.py`（需 8080/8765） | 失敗（環境競態 + 腳本過時） | 第 31 行 `S.rc.rc_lock===0 && S.rc.right_ud>1500` `Timeout 90000ms`；診斷顯示封包帶 `'assist': 2, 'profile': 'normal'`、用戶端 `rc_lock` 被改回 1。加 4 秒等待的複本可跑完全部（對應精靈 4 軸 17 鍵），但原腳本第 38 行的斷言 `all('assist' not in rc ...)` 現在必為 False。見 P1-9 |
| `browser_audio_smoke.py` | 通過 | `Audio smoke passed: gesture, nonzero waveform (peak=0.0385), mute, no page errors` |
| `browser_audio_review_smoke.py` | 通過 | `PASS: M changes flight mode without changing mute ...` |
| `browser_attitude_smoke.py`（需 8094） | 通過 | `{"passed": 8, ...,"errors": []}` |
| `browser_connection_smoke.py` | 通過 | `Server address, room navigation, query selection, and model persistence passed.` |
| `browser_mission_smoke.py` | 失敗（環境競態） | 第 21 行 `Math.abs(S.operations.arm.joints[0]-20)<.5` `Timeout 30000ms`。探針：載入後等 3 秒再下同一指令，640×400 與 1600×1000 都在約 1 秒內到位。見 P1-10 |
| `browser_pilot_guide_smoke.py` | 通過 | `"errors": []` |
| `browser_gameplay_smoke.py`（需 8094） | 通過 | `scenario_training round trip passed {"status": "passed", ...}` |
| `browser_paint_smoke.py`（需 8093） | 失敗（環境） | 第 61 行（按住 Q 下潛到離底 2.2 m）`Timeout 180000ms`；診斷 `control_generation: 158`，即 3 分鐘內被失效保護上鎖約 158 次 |
| `browser_expedition_smoke.py` | 失敗（研判為環境，未獨立驗證） | 第 68 行 `S.room.players.length===3` `Timeout 30000ms`（3 頁同時軟體繪圖） |
| `browser_collection_storage.py`（需 8094） | 通過 | `{"imported": {"addedPhotos": 8, ...}` |
| `browser_visual.py` | **失敗（腳本過時）** | 第 17 行 `wait_for_function('window.__viewer?.S?.vehicle_id')` `Timeout 30000ms`：網址沒有 `play=1`，現在會停在主選單 |
| `browser_fleet_perf.py`、`browser_expedition_perf.py` | 未執行 | 量測畫面幀率，軟體繪圖下數字無意義 |
| `benchmark_room.py`（3 機，600 ticks） | 已量測 | 無 numba：`wall_mean_ms 11.78, p95 16.30, batch_fraction 0.0`；有 numba：`wall_mean_ms 4.73, p95 6.66, batch_fraction 1.0` |

### 效能（每步 0.01 s 模擬時間；即時倍率 = 10 ms ÷ 平均每步耗時）

| 情境 | 依 requirements 安裝（無 numba） | 加裝 numba |
|---|---|---|
| 1 機 coral_reef | 5.17 ms，**1.94×** | 2.30 ms，**4.35×** |
| 3 機 coral_reef | 11.84 ms，**0.84×（低於即時）** | 4.64 ms，**2.15×** |
| campaign 掛鉤（閒置） | 0.0002 ms/步，可忽略 | 同左 |
| instructor 掛鉤（無人監看） | 0.006–0.011 ms/步（約 0.1%） | 0.005–0.010 ms/步 |
| campaign 進行中：序章 | 0.03 ms/步（0.7%） | 0.02 ms/步（1.3%） |
| campaign 進行中：事故章節 | **0.42 ms/步（16%）** | **0.48 ms/步（22%）** |

`docs/physics-performance.md` 記載的基準是 7.69 ms、編譯批次 99.39%；本機無 numba 時批次為 0%。

## (c) 缺陷排序

### P0：使用者現在就會遇到

**P0-1　新玩家的「劇情與新手教學」啟動的是事故演練，不是序章（T12 × T22）**
- 證據：`simulator/qysim/campaign/__init__.py:221-222` 章節以 `chapter_order`（前置深度）排序，同深度依檔名；T22 的五個 `incident_*.json` 沒有 `requires`，排在 `prologue` 前。`simulator/viewer/story/campaign.js:162-167` 自動啟動時取第一個「未完成且前置已滿足」的章節。`simulator/viewer/main_menu.js:33` 選單預設模式就是 `campaign`。
- 確認方式：［實跑］Python 印出章節順序為 `incident_compass, incident_current, incident_jacket, incident_silt, incident_wreck, prologue, harbor, ...`；瀏覽器以全新設定檔開 `?play=1&mission=campaign`，得到 `chapter: incident_compass`、場景 `incident_compass`、對話「演練注入通報：羅盤偏移…」；`browser_campaign_smoke.py` 兩次都卡在等 `prologue`。
- 影響：第一次進遊戲的人沒有教學，直接進鋼構旁撤離演練。玩完序章的人下一個自動啟動的也會是事故章節而不是「港灣」。
- 建議：章節加明確的 `order` 與 `category`（`story`／`incident`），自動啟動只挑 `story`；排序鍵改為 `(category, order)`；`test_campaign.py` 加一條「全新存檔自動啟動必為 prologue」。

**P0-2　戰役 JSON 用系統預設編碼讀取，非 UTF-8 的 Windows 上伺服器無法啟動**
- 證據：`simulator/qysim/campaign/__init__.py:8`、`:65` 的 `read_text()` 沒有指定 `encoding`；`Room.__init__`（`room.py:44-45`）每個房間都會建立 `Campaign`，所以是啟動路徑。`simulator/START_SIM.bat:12` 只檢查 `import numpy, websockets`，舊安裝不會補裝 T12 新增的 `jsonschema`。
- 確認方式：［實跑］以 `LC_ALL=C PYTHONCOERCECLOCALE=0 python -X utf8=0` 建立 `Room(Simulator())`，得到 `UnicodeDecodeError: 'ascii' codec can't decode byte 0xe7`。逐檔以 cp950／cp1252／cp936／cp932 解碼，14 個檔有 13 個失敗。［閱讀］`START_SIM.bat` 的相依檢查。［推論］打包版：`desktop/main.cjs:32` 對打包的 exe 只設環境變數 `PYTHONUTF8=1`（開發模式才有 `-X utf8`），PyInstaller 凍結程式一般不讀 `PYTHON*` 環境變數，`build_backend.py` 也沒有設 UTF-8 選項；我沒有 Windows 可實證。
- 影響：Windows 上用 `START_SIM.bat` 或直接 `python -m qysim.server` 的訓練員與 SDK 開發者（Python 3.15 之前預設不是 UTF-8）起不來；Steam 打包版很可能相同。
- 建議：兩處改 `read_text(encoding='utf-8')`；`START_SIM.bat`、`START_QIRC_SIM.bat` 的檢查加 `jsonschema`；加一條以非 UTF-8 locale 啟動的測試；打包版在 PyInstaller 加 `X utf8` 選項並在 Windows 上實測。

**P0-3　預設飛行是定點輔助（assist 2），與「真實模式為預設與驗收基準」相反（T01 × T02 × T12）**
- 證據：`simulator/viewer/input/index.js:36` `const rc = {..., assist: 2, profile: "normal"}`；`simulator/viewer/input/actions.js` 的 `assistFields` 在 `state.assist` 存在時就送出；`simulator/PROTOCOL.md:167` 寫明「The viewer defaults to `assist:2`」，但同檔 243 行又寫「Manual thrust control remains the default」；`docs/campaign.md:20-21` 說教學要等 T01 合併後採用預設定點輔助。後端預設是 0（`engine.py:810-813`）。
- 確認方式：［實跑］全新頁面 `?play=1`，送出的 RC 封包帶 `"assist":2,"profile":"normal"`；按 Space 解鎖後伺服器回報 `assist: {level: 2, holding: true}`。
- 影響：AGENTS.md 要求水平推桿是推力、內部訓練版輔助全關。現在任何人一解鎖就是鬆桿定點、抵抗洋流。輔助等級也沒有存檔與選單設定，只能每次按 F 切回手動。我把它列為 P0 是因為它讓驗收基準本身不成立；功能上並沒有壞。
- 建議：輸入層預設改 `assist: 0`；輔助等級與檔位進設定並持久化，Steam 版若要預設開輔助，用明確的版本旗標；修正 `PROTOCOL.md:167`；教學若需要定點輔助，由章節腳本明確要求並在畫面標示。

### P1：行為錯誤或彼此不一致

**P1-1　手把與鍵盤鍵位互撞**
- 證據與確認（皆［實跑］，以假的 standard 手把與真實按鍵）：
  - 十字鍵上（b12）：`actions.js:30-31` 同時綁 `profile` 與 `up`。按一下，HUD 跳出「任務與目標」卡，飛行檔位同時 `normal → sport`。`docs/design/ui-direction.md:44-45` 指定十字鍵給速覽卡。
  - View／Back（b8）：`actions.js:26`、`:37` 同時綁 `mode` 與 `engineering`。長按開工程抽屜（`hud/flight_hud.js:268`）的同時，控制模式 `left_switch 0 → 1`。
  - A（b0）：`actions.js:22` 是拍照；`story/campaign.js:139` 直接讀 `buttons[0]` 推進對話。對話中按 A，送出 1 次拍照、`state.photos` 變 1。序章最後一步的條件是 `photos > 0`，所以會被提前滿足。
  - 鍵盤 F：`input/index.js:111` 切輔助等級；`surface_paint.js:95` 噴漆。開啟噴漆後按 F，兩者同時發生（輔助 2 → 0，且執行了噴漆）。
  - ［閱讀］`record: b1` 與 `back: b1`（`actions.js:23`、`:36`）同鍵，未實測。
- 建議：`BUTTONS` 以單一表格檢查重複並加單元測試；`profile` 換到不與十字鍵衝突的鍵；`engineering` 長按期間抑制 `mode`；噴漆換鍵或在噴漆開啟時讓 F 只做噴漆。

**P1-2　戰役模組繞過輸入層自己讀手把**
- 證據：［閱讀］`story/campaign.js:139`、`:214` 直接呼叫 `navigator.getGamepads()`，不經 `input/devices.js` 的裝置正規化、重新對應、選定裝置，也不受收藏面板或設定面板開啟時的封鎖。遊戲中另有 `main_menu.js:93`（選單）與 `controller-check.js`（獨立頁）各自輪詢。
- 建議：對話確認改用 `input.registerActions` 註冊 `accept`，並在對話顯示時消耗掉 `photo`。

**P1-3　教官監看時，學員所有非 RC 指令都被拒（T17 × 其餘）**
- 證據：`simulator/qysim/server.py:495-496`。
- 確認方式：［實跑］設 `room.instructor.supervised = True` 後，`payout`、`auto_payout`、`operation arm`、`campaign_advance`、`mission_photo`、`operation_mode`、`shaping`、`remote_release` 全部回 `instructor_override`。
- 影響：被考核的學員不能收放纜、不能操作機械臂、不能拍照取證、不能推進對話。纜線管理正是研究報告列為核心的技能。
- 建議：只擋共同場景類指令（`scenario`、`reset`、`pause`、`current`、`model`），載具自身操作照常。

**P1-4　教官取樣永遠在跑，樣本與報告無上限成長**
- 證據：`simulator/qysim/instructor.py:131-133` 每模擬秒對每台載具取樣；`:155` 持續 append；`:204` 每次 `room.reset` 把含完整軌跡的報告加入 `reports`。`room.py:195` 無條件呼叫。
- 確認方式：［實跑］無教官的房間跑 10 秒後 `samples = {'v1': 9}`，重置後 `reports` 多 1 份含 9 點軌跡的報告。
- 影響：長時間開著的伺服器（含只給 SDK 用的預設房間）記憶體持續成長。
- 建議：只在 `supervised` 或有覆蓋事件時取樣；`samples`、`reports` 設上限。

**P1-5　`numba` 沒列在 requirements，照文件安裝會走慢速纜線路徑**
- 證據：`simulator/requirements.txt`、`requirements-server.txt` 都沒有 `numba`；`qysim/_cable_accel.py:9-12` 匯入失敗就退回 NumPy。
- 確認方式：［實跑］見上表：3 機 0.84× 對 2.15×，`batch_fraction` 0.0 對 1.0；單元測試少跑 1 項（skipped=1）。
- 建議：把 `numba` 列入 requirements（或列為 extras 並在啟動時印出目前走哪條路徑）；CI 兩種都跑。

**P1-6　事故章節的輪詢迴圈每次更新重算最多 32 次完整狀態**
- 證據：`simulator/qysim/campaign/__init__.py:162-194`，`incident_*.json` 的 `poll → failed → finished → repeat → poll` 會在 `for _ in range(32)` 內繞圈，每次判斷都呼叫 `sim.viewer_state()`（`:181`、`:191`）。
- 確認方式：［實跑］每次 `campaign.update` 4.2–4.8 ms，占每步 16–22%；序章只占約 1%。
- 建議：每次更新只取一次狀態；回到已走過的 `wait` 節點就結束本次更新。

**P1-7　疊層遮擋**
- 確認方式：皆［實跑］，1280×720 與 390×844，以 `elementFromPoint` 與截圖確認。
  - 戰役對話框（`story/campaign.js:77-79`，`left:30%; bottom:18%; width:40%; z-index:25`）在追蹤視角蓋住載具下半部；機載視角蓋住畫面中下方。
  - 回放字幕（`style.css:258`，`bottom:118px; z-index:5`）正好蓋住被 `hud.css:70` 上移到 `bottom:96px` 的速度／纜線／電量讀數。
  - 回放列（`style.css:249`，`z-index:6`）蓋住「視角」按鈕（`hud.css:15` 把它移到右下）與小地圖的「北朝上」按鈕，兩者點不到。
  - 手機寬度：回放列淡出時，字幕攔截對播放鍵的點擊，要點兩次。
- 已知回報「HUD 擋住回放控制列的點擊」：**未重現**。回放列顯示時，播放、進度、速度、片段按鈕在兩種尺寸都可點；實際情況是反過來，回放列擋住 HUD 按鈕。
- 建議：定一份共用的 z-index 表；對話框改貼下緣或左下並縮窄；回放時讀數與字幕錯開；「視角」按鈕在回放時移出回放列範圍。

**P1-8　其餘真實模式預設不一致**
- ［閱讀］`main_menu.js:44` 選單預設控制配置是 `UAV_CHN`（「ROV 雙桿」），後端與工程抽屜預設是 `ROV_USA`（選單自己標為「X1 配置」）。
- ［閱讀］影像延遲有實作（`state_buffer.js:173-174`，預設 150 ms），但只能用網址參數 `videoDelayMs`、`presentation=assisted` 調整，沒有介面，也沒有與輔助等級合成一個「真實／輔助」開關。
- ［閱讀］HUD、音效讀未延遲的狀態（`app.js:1189`），畫面姿態延遲 150 ms，兩者不同步。
- 符合的部分：預設視角是機載第一人稱（［實跑］`視角：機載`）；後端預設手動；SDK 遠端控制時輔助停用。
- 建議：設一個單一的呈現設定（內部訓練版＝全關），由選單寫入，輸入層、鏡頭、HUD 都讀它。

**P1-9　瀏覽器驗證腳本過時且彼此不相容**
- ［實跑］`tools/browser_input_smoke.py:38` 斷言封包不含 `assist`／`profile`，T01 合併後必敗；`tools/browser_visual.py:16` 的網址少 `play=1`，停在選單。
- ［閱讀］腳本各自寫死埠號（8080、8092、8093、8094、8095、8096），無法對同一台伺服器跑完；`browser_campaign_smoke.py` 強制錄影；CI（`.github/workflows/browser.yml`）只跑 smoke 與 menu 且為 advisory，所以 P0-1 沒被擋下。`backend.yml` 的 `paths` 不含 `simulator/campaign/**` 與 `simulator/examples/**`。
- 建議：埠號改參數並共用一個啟動 helper；修兩支過時腳本；把 campaign、hud、input 三支納入 CI。

**P1-10　加入後數秒內或畫面卡頓時，失效保護會吃掉指令**
- 證據：［實跑］每個探針載入完成時 `control_generation` 已是 2–3（表示加入後已被上鎖過）；`room.py:67-69` 上鎖會把機械臂目標重設為現值；`app.js:551-554` 重新同步時以伺服器值覆寫本地的鎖定與開關。最大 RC 間隔在 4 FPS 時量到 562 ms，離 0.6 秒門檻很近。
- 影響：［推論］實機上若載入模型或編譯 shader 造成超過 0.6 秒的卡頓，第一次解鎖或機械臂指令會無聲失效。低於約 2 FPS 時載具無法操控（`control_generation: 158`）。
- 建議：RC 心跳移到 Web Worker 或獨立計時來源；加入後給一段寬限；重新同步時保留使用者在這之後的操作。

### P2：清理

- **協定文件**：`PROTOCOL.md:295-296`「Unset/empty disables authentication」實際是停用整個教官功能（［實跑］空碼與無碼都回 `instructor authentication failed`；`instructor.py:39-41`）；錯誤碼清單（52 行）缺 `instructor_override`、`controller_only`；`profile` 非字串會讓整個 RC 封包被拒（［實跑］`RC profile must be a string`，`server.py:508-509`），與「unsupported values use those defaults」不符；範例 `capacity: 4`、`v1–v4` 與 `Room.capacity = 3`（`room.py:28`）不符；`state.rc` 現在多了 `assist`、`profile` 兩鍵（新增、未記載）。
- **展示包**：`index.html` 連到被 `build_showcase.py:28` 排除的 `controller-check.html`（404）；內部用的 `instructor/` 頁面被打進公開展示包（［實跑］200）。
- **桌面打包**：`build_backend.py:37` 把整個 `campaign/` 打包，含 `screenshots/`（0.41 MB）與 `INCIDENTS.md`。其餘檢查結果：戰役 JSON、`jsonschema_specifications`、viewer（含 `input/controller-db.json`、`hud/`）都有打包；`instructor/` 頁面有排除；`examples/` 執行期不需要。目前沒有設任何 CSP，頁面除 importmap 外沒有 inline script，視窗為 sandbox + contextIsolation；日後若加 CSP，importmap 需要 hash 或 nonce。
- **重複負責**：`updateTether` 每個狀態被呼叫兩次（`app.js:559` 未延遲、`state_buffer.js:192` 延遲），前者白做；震動回饋有兩個來源（`input/index.js` 的 `feedback` 與 `hud/flight_hud.js` 的 `input.pulse`）；畫面搖桿顯示有三個擁有者（`app.js:1254` 的 `optSticks`、`input/index.js:29-33`、`hud/hud.css:24-25` 的 `!important`），其中核取方塊實際上被 CSS 蓋掉；手把選擇有選單 `pad` 參數與遊戲內設定兩處。
- **環繞視角吃掉右搖桿**：`camera_rig.js:63-72` 在 orbit 模式把 `right_lr`、`right_ud` 歸零給鏡頭用，載具可能正在解鎖移動中。
- **重複程式**：操作模式通道表在 `app.js:606`、`story/campaign.js:22`、`pilot_guide.js:10`、`qysim/rc.py` 各一份；`clamp` 在 6 個模組各自定義；`browser_*.py` 20 支各自重寫啟動樣板。
- **佐證媒體**：五種放法、共 94 檔 8.7 MB：`docs/evidence/T12`（3.9 MB，含 webm）、`docs/tasks/evidence/T02、T04`（2.4 MB）、`docs/validation/T03`（60 檔）與 `T17`、`docs/reviews/T05`、`simulator/campaign/screenshots`（在執行期資料目錄內）。超過 2 MB 的新資產沒有發現；既有大檔為 `cad/*.blend`、`sim/rov.glb`、`viewer/demo_recording.json`（5.8 MB）。
- **其他**：每次載入都有 favicon 404；`index.html` 的按鍵提示沒有 F、G、B、`[ ]`、Tab、1–4；`campaign_restore` 在每次房主加入時都送；測試會寫 `simulator/output/`。

### SDK 相容性

沒有發現「不送新欄位時行為改變」的情況：［實跑］不帶 `assist` 的 RC 封包得到 `assist 0 / normal`；`test_sdk_mock.py` 全過；SDK 取得遠端控制時輔助被略過（`engine.py:171`）。唯一的連帶風險是啟動相依（P0-2）。

## (d) 無法驗證的部分

- **Windows 與 Electron 打包**：沒有 Windows 與建置環境。P0-2 的打包版結論、`smoke_backend.py`、`sync_backend.py` 都未執行。
- **真實手把與 Q-iRC USB**：鍵位互撞用假的 standard 手把重現；實體裝置、震動、USB 橋接路徑未測。
- **真實 GPU 下的時序**：`browser_smoke`、`browser_paint_smoke`、`browser_expedition_smoke` 的失敗我判為環境造成，其中 `expedition_smoke` 沒有獨立驗證；P1-10 在硬體繪圖下的發生頻率未知。
- **幀率類腳本**：`browser_fleet_perf.py`、`browser_expedition_perf.py` 未執行。
- **教官台端到端**：需設 `QYSIM_INSTRUCTOR_CODE`，只在 Python 層驗證了伺服器行為，沒有開教官頁面實操。
- **與真機一致性**：只核對了預設值與語意是否符合 AGENTS.md 與研究報告，沒有任何實機資料可比對手感。

## 附註

- 稽核期間我在環境裡 `pip install numba`（為了量測兩種路徑），這不在倉庫內，但之後在這台機器跑測試會走編譯路徑。
- 我啟動的模擬伺服器都已停止；8092 那台中途因背景時限被系統停掉一次，我重啟後重跑了受影響的 `browser_campaign_smoke.py`，結果相同。
- 截圖與探針腳本在 `/tmp/claude-0/-home-user-rov/c18300da-7030-5b94-b1a0-14632023d865/scratchpad/`（`campaign_chase.png`、`replay_desktop.png`、`probe1.py`–`probe5.py`、`bench.py`）。
