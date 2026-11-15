# H4 CI 執行時間與分層

量測日期：2026-11-15（UTC）。基底 `5c5dc4c`。Linux 雲端工作區，Python 3.12.14、Node v24.22.1，
5 vCPU AMD EPYC 9V74；Chromium / Playwright 1.62.0 軟體渲染，numba 0.68.1、numpy 2.3.5。這是單次本機實測，不是 GitHub runner 的保證值。
Python 與瀏覽器兩組量測同時進行，各組內逐檔循序執行；CPU 競爭可能拉長時間。
numba 使用本機預設磁碟快取，包含首次編譯與後續命中，未人工清除。CI 使用獨立 `NUMBA_CACHE_DIR`。
每個 Python 模組以獨立 `unittest discover -s tests -p <模組>.py` 執行（含 import／程序啟動），
每個瀏覽器腳本含專屬伺服器啟動與清理。FAIL 是實際失敗時間，不能解讀為成功完成的預算。
既有測試內容未修改；重複被 discover 載入的測試維持原行為。
診斷／截圖腳本的 PASS 僅表示程序 exit 0，不代表畫面經人工驗收或效能達標。

## 共用分層

`tools/check_matrix.py` 是唯一分層／路徑對照表，CI 與本機共用。

| 層級 | Python | Node | 瀏覽器 |
|---|---|---|---|
| quick | encoding、protocol_doc、vendor_manifest、power、thermal + 選測回歸測試 | 全部（數秒） | HUD smoke |
| full | 全部 `test_*.py` + 選測回歸測試 | 全部 | 原有標準清單 22 支（包含 quick） |

- 非 draft PR 的 opened/synchronize/reopened 跑 quick；ready_for_review 或手動 dispatch 跑 full。
  ready 後的新 push 跑 quick；需要重新完整驗證時手動 dispatch。draft 的所有 PR jobs 均跳過。
- Backend quick 是每個非 draft PR 都會有的固定小型 gate，不因 docs-only 而消失。
- Browser PR workflow 保留 `paths: simulator/viewer/**`。後端、桌面或 CI 工具單獨變更都不啟動它。
  手動 dispatch 明確選擇完整瀏覽器檢查。
- `--changed` 比較 merge-base(base, HEAD) 到工作樹，加上未追蹤檔，包含 staged／unstaged／刪除。
  沒有共同祖先時直接報錯，不會靜默跳過。預設 base 是 `origin/main`，CI 使用 PR base SHA。
- HUD-only：full 選 HUD、overlay、attitude；quick 選 HUD。其他 viewer 路徑或同時變更後端／依賴時保守選該層全套。
  qysim/sdk_mock/依賴/檢查工具變更選該層 Python 全套；單獨測試檔變更選該層中的該檔；純文件不跑產品測試。
- `--changed` 仍執行選測器本身的回歸測試。Node 在 viewer、desktop、tests、檢查工具／workflow 變更時執行。
- 手動指定瀏覽器腳本名稱是本機診斷覆寫；不受 tier 過濾。其餘 15 支診斷／截圖／效能／歷史相容腳本
  保留原本 explicit-only 行為，全部另行量測如下；未偷偷刪除或放寬測試。
- quick 每個測試 job 上限 5 分鐘（目標包括安裝與啟動）；full backend 20、browser 60 分鐘。
  各 job 與 workflow 均設定 concurrency/cancel-in-progress，避免舊工作繼續消耗額度。
- Windows 維持僅 workflow_dispatch，沒有 macOS 工作。pip 與 numba 在 Python 依賴工作快取；
  numba key 隔離 OS、架構、Python 版本、依賴與後端來源，允許相同平台前綴還原，由 numba 檢查來源相容性。

## 實際驗證

```bash
python tools/run_checks.py --changed --report /tmp/h4-changed.json
python tools/run_checks.py --tier quick --kind unit --report /tmp/h4-unit-quick.json
python tools/run_checks.py --tier full --kind unit --report /tmp/h4-unit.json
python tools/run_checks.py --tier full --kind node --report /tmp/h4-node.json
node simulator/desktop/test_collection_store.cjs
python simulator/tools/run_browser_checks.py --tier quick --report /tmp/h4-browser-quick.json
python simulator/tools/run_browser_checks.py --tier full --report /tmp/h4-browser-full.json
# 等同本次額外量測的明確腳本清單，每支 timeout=900 秒：
python simulator/tools/run_browser_checks.py \
  browser_expedition_perf browser_fleet_perf browser_input_smoke browser_menu_screens \
  browser_onboard_smoke browser_procedure_compat browser_procedure_smoke browser_scene_ab \
  browser_scene_review browser_sonar_smoke browser_tether_smoke browser_underwater_pipeline \
  browser_underwater_shots browser_vision_smoke browser_visual --report /tmp/h4-browser-extra.json
(cd simulator && python -m unittest discover -s tests)
/tmp/actionlint
git diff --check
```

| 驗證 | 結果 | 秒 |
|---|---|---:|
| quick Python | 6/6 通過 | 8.05 |
| full Python（逐模組） | 40/40 通過 | 357.48 |
| Node／desktop | 29/29 通過 | 5.13 |
| --changed（browser 無變更略過） | 36/36 入口成功 | 10.67 |
| quick browser | 1/1 通過 | 17.27 |
| full browser | 20/22 通過 | 1205.53 |
| explicit-only browser | 12/15 通過 | 1865.10 |
| 原始 unittest discover 全套 | exit 0 | 335.28 |

quick 三組本機時間合計 30.45 秒，不含依賴安裝；CI 的 5 分鐘目標仍需額度恢復後確認。

## Python 模組與 Node 測試檔

| 模組／檔案 | 秒 | 結果 |
|---|---:|---|
| `test_campaign` | 11.45 | PASS |
| `test_campaign_chapters` | 9.25 | PASS |
| `test_comms_link` | 8.24 | PASS |
| `test_controller_frames` | 0.29 | PASS |
| `test_core` | 52.54 | PASS |
| `test_currents` | 10.99 | PASS |
| `test_ecology` | 2.89 | PASS |
| `test_encoding` | 1.14 | PASS |
| `test_examples` | 14.68 | PASS |
| `test_expedition` | 7.23 | PASS |
| `test_flight_assist` | 16.51 | PASS |
| `test_incidents` | 6.53 | PASS |
| `test_inertial_dynamics` | 0.20 | PASS |
| `test_instructor` | 8.05 | PASS |
| `test_instructor_faults` | 2.46 | PASS |
| `test_instructor_sensor_faults` | 2.53 | PASS |
| `test_mission_modes` | 1.94 | PASS |
| `test_multiplayer` | 5.83 | PASS |
| `test_observation_rov_asset` | 0.26 | PASS |
| `test_operations` | 0.95 | PASS |
| `test_paint` | 1.11 | PASS |
| `test_physics_validation` | 1.15 | PASS |
| `test_power` | 2.63 | PASS |
| `test_procedure` | 1.82 | PASS |
| `test_protocol_doc` | 0.36 | PASS |
| `test_qirc` | 2.06 | PASS |
| `test_scene_consistency` | 25.30 | PASS |
| `test_sdk_mock` | 8.83 | PASS |
| `test_sensors` | 88.01 | PASS |
| `test_silt` | 6.04 | PASS |
| `test_solver_status` | 0.37 | PASS |
| `test_sonar` | 1.52 | PASS |
| `test_tether_ops` | 14.10 | PASS |
| `test_tether_physics` | 17.59 | PASS |
| `test_tether_validation` | 15.01 | PASS |
| `test_thermal` | 5.81 | PASS |
| `test_vehicles` | 0.42 | PASS |
| `test_vendor_manifest` | 0.16 | PASS |
| `test_vision_dataset` | 0.10 | PASS |
| `test_vision_transport` | 1.13 | PASS |
| `input_layer.mjs` | 0.28 | PASS |
| `test_asset_config.mjs` | 0.20 | PASS |
| `test_assist_pill.mjs` | 0.17 | PASS |
| `test_audio.mjs` | 0.19 | PASS |
| `test_bindings.mjs` | 0.25 | PASS |
| `test_camera_actions.mjs` | 0.20 | PASS |
| `test_dialogue_input.mjs` | 0.27 | PASS |
| `test_fidelity.mjs` | 0.16 | PASS |
| `test_flight_hud.mjs` | 0.18 | PASS |
| `test_flow_field.mjs` | 0.14 | PASS |
| `test_frontend_cleanup.mjs` | 0.24 | PASS |
| `test_hud_style.mjs` | 0.23 | PASS |
| `test_menu.mjs` | 0.32 | PASS |
| `test_overlay_scale.mjs` | 0.27 | PASS |
| `test_rc_scheduler.mjs` | 0.18 | PASS |
| `test_real_defaults.mjs` | 0.14 | PASS |
| `test_render_quality.mjs` | 0.17 | PASS |
| `test_sensor_view.mjs` | 0.20 | PASS |
| `test_silt_field.mjs` | 0.13 | PASS |
| `test_state_buffer.mjs` | 0.21 | PASS |
| `test_tether_reel.mjs` | 0.12 | PASS |
| `test_tether_tension.mjs` | 0.15 | PASS |
| `test_video_link.mjs` | 0.21 | PASS |
| `test_water_optics.mjs` | 0.18 | PASS |
| `test_backend_lifecycle.cjs` | 0.03 | PASS |
| `test_collection_store.cjs` | 0.19 | PASS |
| `test_desktop.cjs` | 0.05 | PASS |
| `test_input_guard.cjs` | 0.04 | PASS |
| `test_steam.cjs` | 0.03 | PASS |
| `check_matrix` | 0.09 | PASS |

## 每支瀏覽器腳本

| 腳本 | 層級 | 秒 | 結果／細節 |
|---|---|---:|---|
| `browser_attitude_smoke` | full | 19.63 | PASS  |
| `browser_audio_review_smoke` | full | 10.32 | PASS  |
| `browser_audio_smoke` | full | 67.83 | PASS  |
| `browser_camera_input_smoke` | full | 5.75 | PASS  |
| `browser_camera_smoke` | full | 2.15 | PASS  |
| `browser_campaign_smoke` | full | 37.09 | PASS  |
| `browser_collection_storage` | full | 97.61 | PASS  |
| `browser_connection_smoke` | full | 14.45 | PASS  |
| `browser_expedition_perf` | explicit-only | 37.20 | FAIL playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded. |
| `browser_expedition_smoke` | full | 243.41 | FAIL playwright._impl._errors.TimeoutError: Page.wait_for_function: Timeout 30000ms exceeded. |
| `browser_fleet_perf` | explicit-only | 7.71 | PASS  |
| `browser_gameplay_smoke` | full | 92.39 | PASS  |
| `browser_hud_smoke` | quick + full | 19.58 | PASS  |
| `browser_input_smoke` | explicit-only | 3.70 | FAIL AssertionError |
| `browser_link_smoke` | full | 16.65 | PASS  |
| `browser_menu_gamepad_smoke` | full | 82.36 | PASS  |
| `browser_menu_screens` | explicit-only | 378.71 | PASS  |
| `browser_menu_smoke` | full | 41.99 | PASS  |
| `browser_mission_smoke` | full | 52.77 | PASS  |
| `browser_onboard_smoke` | explicit-only | 14.35 | PASS  |
| `browser_overlay_smoke` | full | 159.92 | PASS  |
| `browser_paint_smoke` | full | 139.94 | FAIL playwright._impl._errors.TimeoutError: Page.click: Timeout 90000ms exceeded. |
| `browser_pilot_guide_smoke` | full | 2.73 | PASS  |
| `browser_procedure_compat` | explicit-only | 10.45 | PASS  |
| `browser_procedure_smoke` | explicit-only | 54.90 | PASS  |
| `browser_scene_ab` | explicit-only | 750.23 | PASS  |
| `browser_scene_review` | explicit-only | 458.05 | PASS  |
| `browser_slow_render_smoke` | full | 34.45 | PASS  |
| `browser_smoke` | full | 44.35 | PASS  |
| `browser_sonar_smoke` | explicit-only | 6.98 | PASS  |
| `browser_tether_smoke` | explicit-only | 4.21 | PASS  |
| `browser_underwater_pipeline` | explicit-only | 2.28 | PASS  |
| `browser_underwater_shots` | explicit-only | 93.54 | PASS  |
| `browser_vehicle_assets_smoke` | full | 13.73 | PASS  |
| `browser_vision_smoke` | explicit-only | 7.03 | PASS  |
| `browser_visual` | explicit-only | 35.74 | FAIL playwright._impl._errors.TimeoutError: Page.wait_for_function: Timeout 30000ms exceeded. |
| `observation_smoke` | full | 6.42 | PASS  |

## 未通過項目與限制

標準 full 本次 20/22 通過，未修改的兩支測試失敗：

- `browser_expedition_smoke.py:111`：deploy 取消後 `expedition.active === null` 等待 30 秒逾時。
- `browser_paint_smoke.py:95`：`#engineering` 的標題攔截 `#flightDrawer` 點擊，等待 90 秒逾時。

未放寬斷言、未刪除腳本、未改為 continue-on-error。這兩項仍在 full gate；本 PR 不宣稱完整瀏覽器驗證全過。
原始 Python discover：407 tests，331.162 秒，OK（總程序時間見上表）。
explicit-only 另有 3 支失敗：expedition_perf（按鈕不可見）、input_smoke（舊協定不帶 assist 的斷言）、
visual（等待 vehicle_id 逾時）。瀏覽器失敗的診斷訊息列於上表；畫面／流程修正不屬於 H4，留待後續任務。
`browser_menu_screens.py` 會覆寫 `docs/design/menu-redesign/*.png`；本次已還原這些量測產生的變更，
未提交圖片／錄影／大型產生物。若要重跑全部診斷，建議使用乾淨的獨立工作樹。
CI 為 Python 3.11／Node 22，本機為 Python 3.12／Node 24；未為驗證而消耗 Actions 額度。

## 每月 CI 分鐘預估

假設每月 52/12 = 4.33 週，每週 10 PR，每個 PR 推 3 次，另轉 ready 一次。
保守以 **130 次 quick + 43.33 次 full** 估算（實際 draft 推送不執行，因此通常更低）。
以包含安裝／checkout 的規劃數值計算：backend quick 1、full 12 分鐘；frontend 1 分鐘；
browser quick 3、full 40 分鐘。設 p 為涉及 viewer 的 PR 比例，並先假設 frontend 比例同 p：

`130 × (1 + 4p) + 43.33 × (12 + 41p) = 650 + 2296.53p Linux 分鐘/月`。

- p=25%：約 **1,224 分鐘/月**；再加每 PR 合併一次 Pages build+deploy 合計 2 分鐘，約 **1,311 分鐘/月**。
- p=100%：約 **2,947 分鐘/月**；含 Pages 約 **3,034 分鐘/月**，仍會超過 2,000 分鐘免費額度。
- 若三次 push 都在 draft，只有 ready 執行 full：p=25% 含 Pages 約 **1,051 分鐘/月**。
- desktop-only PR 的 frontend 工作另加每次約 1 分鐘；Windows 手動工作與重新 dispatch 不包含在上述預估。
  Windows 依平台倍率另計；沒有 macOS 工作。取消舊執行、HUD 選測與快取節省未額外扣除。

這是保守容量規劃，不是本機秒數直接換算 GitHub 帳單。12/1 額度恢復後應以實際 Actions job 時間與
viewer PR 比例更新；本次只建立 draft PR，不為取得 CI 時間主動消耗 Actions 額度。
