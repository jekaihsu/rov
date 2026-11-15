# M2 水庫進水口（施工中）

這份 draft 是物理與任務接線／碰撞配置，**尚未達到照片級畫面驗收**。
本輪未收到擁有者的參考照片；不能宣稱已完成並排比較或「像同一個地方」。
`main@138c242` 的 game-plan.md 只到 §10，指定的 §11 尚不存在。

## 已接線

- `reservoir_intake`：淡水、3 m 能見度、泥底，無潮流及背景流，碼頭邊出發。
- 三個依序目標：下潛、面向堵塞處且距離 0.6–2.8 m 拍照、返航。
- 進水口、柵條、閘門槽、沉木使用既有 Box／Cylinder；柵條與沉木有 snag_hold。
- 護坡目前為階梯狀 Box 近似；浮筒、船體、設備目前是碰撞 blockout。
- 局部吸入流採光滑橢球衰減，進入共用世界流場，詳見 PROTOCOL.md。
- 停用不適用淡水的既有海洋 habitat；fresh_green 使用現有水體光學，能見度不加長。
- 兩個具名 NED 相機錨點在 `viewer/reservoir.js`，尚未切換選單預設背景。

尺寸、保持力、流速均為訓練假設。吸入流是殘留流危險演練，並非真實場站運轉模型。
研究依據：real_rov_jobs_missions.md §2.7（停機／關閘／上鎖掛牌、沿壩面下潛、逐格拍照與纜線管理）。

## 重建與預算

```bash
blender -b --python cad/build_reservoir.py
node simulator/tools/reservoir_asset_report.mjs
```

原創 CC0，固定配置，不讀取照片，不存 blend。GLB 有低／中兩檔、meshopt；預留 WebP 壓縮流程，
目前沒有貼圖，因此不宣稱已有 WebP 美術資產。執行時由碰撞原語重建，GLB 是可攜檢視資產。
資產報告只量目前結構；不得當成尚未完成山林景觀的最終預算。

## 待完成（不可視為驗收通過）

參考照片比對；山谷與樹林、公路橋、六角護坡、真實小船線型、髒污／鏽蝕／磨損材質；
淡綠靜水水面與水上景觀替換；選單背景接線；最終 meshopt＋WebP 資產及完整場景預算；
水面兩角度、機載開燈／關燈、攔污柵特寫的模擬器截圖與逐圖審視。
目前通用環境的海上裝飾尚未替換，不能用它當水庫驗收圖。

## 初模機載檢查

`browser_reservoir_onboard.py` 使用固定 replay 姿態、既有機載相機與燈具，不加場景燈。
初次圖像顯示幾何過於平整、木枝沒有分岔細節，光色與材質遠未達到寫實標準。
初次截圖還揭露舊出發纜長 65 m 在淺水護坡造成過大初始張力；已改為碼頭外緣出纜、
起始放纜 12 m，接近進水口時需使用原有放纜控制。已隨此修正重拍並檢查三張圖，張力警告消失；仍不能作最終美術驗收證據。

## 本機驗證紀錄

- `node --test simulator/tests/*.mjs`：211/211 通過。
- `python simulator/tools/run_browser_checks.py browser_smoke browser_menu_smoke observation_smoke browser_tether_smoke`：4/4 通過。
- `cd simulator && python -m unittest discover -s tests -p test_regional_flow.py`：4/4 通過。
- reservoir 任務測試：2/2 通過；修改初始放纜長後再跑並增加初始張力斷言：2/2 通過，3.836 s。
- 初始放纜修正後實際 Simulator：張力 0.046 N，前進模擬 1 s 後 0.024 N，未斷纜。
- `browser_reservoir_onboard`：重拍 1/1 通過（53.8 s）；照片為初模檢查，不代表美術通過。
- `check_changed_js.py origin/main`、`git diff --check`：通過。
- 完整 Python suite 尚在執行，**未宣稱全過**；此 draft 不可標記完成／合併。

目前資產均小於 2 MB；GLB 是可攜檢視初模，JPEG 是本任務要求的模擬器審查紀錄。

[開燈](onboard-lights-on.jpg) · [關燈](onboard-lights-off.jpg) · [攔污柵特寫](rack-close.jpg)
