# 箱網與珊瑚礁外觀修正（scene-looks）

基底 `main@138c242`。只動前端呈現與一個呈現用的情境參數；物理、碰撞形狀、任務目標、職涯資料都沒動。
所有數值都是視覺假設，不是現場或 X1 量測。依據：`research_notes/洋流與波浪對ROV作業/real_dive_footage.md`
（§2.1 水色隨深度只剩綠、港內濁水是灰綠而非飽和綠；該筆記沒有養殖箱網或珊瑚礁影片，網衣與珊瑚的外觀是
依一般知識做的假設）、`simulator/viewer/fx/README.md`（水體模型、自動曝光、白平衡）。

## 截圖

全部是模擬器內的實際畫面（`simulator/tools/browser_scene_looks.py`，1600×900 JPEG，皆 ≤ 300 KB）：以真實模擬器
建立單幀 replay，把載具放到固定姿態，由頁面本身的機載相機、燈、水體光學、曝光與 HUD 出圖。真實模式為
`fidelity=real&cam=onboard`；第三人稱為 `fidelity=assisted`，鏡頭放在載具後上方（不含 HUD，原因見「已知問題」）。
`before` 是同一支腳本對 `origin/main` 的伺服器與檢視器拍的。姿態、曝光與檔案大小見
[report-before.json](report-before.json)、[report-after.json](report-after.json)。

| 畫面 | 修正前 | 修正後 |
|---|---|---|
| 箱網：網衣 1.6 m，真實、燈關 | [before](pen-net-dark-before.jpg) | [after](pen-net-dark-after.jpg) |
| 箱網：網衣 1.6 m，真實、燈 1 檔 | [before](pen-net-lamps-before.jpg) | [after](pen-net-lamps-after.jpg) |
| 箱網：網內魚群，真實、燈關 | [before](pen-inside-dark-before.jpg) | [after](pen-inside-dark-after.jpg) |
| 箱網：網內魚群，真實、燈 2 檔 | [before](pen-inside-lamps-before.jpg) | [after](pen-inside-lamps-after.jpg) |
| 箱網：網底死魚，真實、燈關 | [before](pen-mort-dark-before.jpg) | [after](pen-mort-dark-after.jpg) |
| 箱網：網底死魚，真實、燈 1 檔 | [before](pen-mort-lamps-before.jpg) | [after](pen-mort-lamps-after.jpg) |
| 箱網：輔助第三人稱 | [before](pen-third-before.jpg) | [after](pen-third-after.jpg) |
| 珊瑚礁：3.4 m，真實、燈關 | [before](reef-dark-before.jpg) | [after](reef-dark-after.jpg) |
| 珊瑚礁：3.4 m，真實、燈 2 檔 | [before](reef-lamps-before.jpg) | [after](reef-lamps-after.jpg) |
| 珊瑚礁：2 m，真實、燈 1 檔 | [before](reef-close-lamps-before.jpg) | [after](reef-close-lamps-after.jpg) |
| 珊瑚礁：輔助第三人稱 | [before](reef-third-before.jpg) | [after](reef-third-after.jpg) |

## 箱網 `aquaculture_pen`

- **半透明帶的來源**：不是水面、霧或雙面網衣，而是任務標記。`pen_lap` 與 `pen_photo` 兩個目標的座標就是出發點
  (3, 0, 7)，預設標記是半徑 1 m 的水平圓環加線框球；載具一開始就站在環裡，環在畫面上變成一條橫跨的寬帶
  （修正前的 `pen-net-*-before.jpg` 另一個角度仍看得到整個環）。修正：`hud/objective_fade.js` 的
  `objectiveNearFade()` 讓這類圓環標記在相機進到環外 1.4 m 以內開始淡出、0.4 m 內完全不畫；`inspect` 與
  `checkpoint` 標記不變。任務資料沒有動（見「已知問題」）。
- **水色**：`water_type` 由 `coastal` 改為 `shelf`（只影響顯示，PROTOCOL 既有的選填欄位；能見度維持 8 m、物理不變）。
  本專案的 `coastal` 是清澈近岸（Jerlov coastal 1–3，海草床用），顏色偏青；養殖場在營養鹽與懸浮有機物多的
  內灣，對應的是 coastal 3–7，也就是本專案的 `shelf`（綠、藍更少）。這是依水體分類做的判斷，不是場址量測。
  畫面整體亮度由相機自動曝光決定，沒有改。
- **網衣**（`aquaculture.js`、`models/aquaculture/net.webp`）：仍是一張 256² alpha 貼圖、一個批次、三角形數不變。
  貼圖改為無結方目網（40 mm 目腳、約 3 mm 網線），alpha 是跨網線的漸層：近距離在 `alphaTest`（0.35）處切出
  網線，附著多的地方降低門檻讓網線變粗；網目小於一個像素後改用 mip 平均的 alpha（就是網衣實積率）做混合，
  所以遠處是一層薄霧而不是閃爍或消失的格線。另外：網片接縫與每 4 m 深度的繩索、網目隨繩間下垂與不規則
  偏移（只在貼圖座標，頂點不動，仍在一致性容差內）、附著隨深度（近水面最多、偏綠）與斑塊變化、局部被
  附著物塞住的網目。材質改為 `transparent`、`depthWrite: false`。
- **養殖魚**（`pen_life.js`）：原創低面數鮭形（90 個三角形，原本的紡錘魚約 120），背深腹白的頂點色。每群沿
  繞網圓周拉成 13 m 長的鬆散帶狀，游向沿切線（原本是一團 2 m 的球、全部朝同一方向）。群中心、尾數、分級
  顯示數（96／232／384）仍是伺服器與原設定；魚仍在半徑 14 m、深度 3–13 m 的範圍附近，不會穿出網衣。
- **死魚**：同一個鮭形、較淡的配色、身體微彎，側躺在碰撞球的底部（貼著網底）。位置、抓取與物理不變。

## 珊瑚礁 `coral_reef`

- **群體外形**（`reef_life.js`）：伺服器的珊瑚實體（位置、大小、碰撞膠囊不變）由 2 種外形改為 6 種：團塊、分枝、
  桌形、海扇、筒狀海綿、指狀；每個實體依伺服器的 `variant` 與 id 固定選一種。每種外形都落在碰撞膠囊的範圍
  附近（寬約 0.9、高 0.6–1 個單位）。
- **顏色**：每個群體有自己的顏色（`instanceColor`）與明暗（頂點色：生長端較淡、溝紋與海綿內側較暗）。褐、橄欖、
  淡紫在藍綠色日光下仍有差別；海扇與海綿的紅、橘在 12 m 的日光下是暗的，開燈靠近才顯色，這是水體模型算的，
  沒有另外加強飽和度。水下日光很漫射，群體側面的法線往上偏，才不會在亮沙上變成黑色剪影。
- **碎塊與小群體**（僅前端、無碰撞）：每個群體周圍一圈深色的死珊瑚碎塊（3–12 cm），中、高畫質另有 0.3 m 以下的
  小群體，讓一個群體讀起來是一小片礁。高度都低於載具會在意的尺度；它們沒有碰撞，這是與「看得到的就是撞得到
  的」原則的小出入。
- **沙紋**（`seabed.js`）：礁區沙紋對比 0.8 → 1.1；中、高畫質多讀一次沙紋貼圖做 0.13 m 的細沙紋（低畫質不變）。
- **礁魚**（僅前端）：18／42／72 尾 9 cm 左右的定棲小魚，兩兩停在較大的群體上方；標成 `observationIgnore`，
  不擋拍照判定，也不是可登錄目標。伺服器原有的 4 群魚不變。

## 效能

同頁面交替量測不可行（兩邊是不同版本的程式），改為同一台機器同時開 `origin/main`（A）與本分支（B）兩個伺服器，
同一畫質各開一頁，兩頁輪流量測，取各輪中位數的最小值（SwiftShader、800×450，含後製每一道 pass）。
量測時機器的 load average 是 27–46（4 核），單幀 0.6–9 秒；draw call 與三角形數可信，毫秒數大多只是雜訊。

| 潛點 | 畫質 | draw calls A→B（第三人稱／機載） | 三角形 A→B（第三人稱／機載） | ms／幀 A→B（第三人稱／機載） |
|---|---|---|---|---|
| coral_reef | 低 | 67→72／45→51 | 48.6k→49.5k／44.0k→44.8k | 672→715（+6%）／725→635（−12%），7 輪×5 幀 |
| coral_reef | 中 | 74→83／51→60 | 50.7k→87.0k／49.7k→86.0k | 2953→1989／1783→981，2 輪×3 幀，雜訊 |
| coral_reef | 高（調降數量前） | 72→83／48→59 | 44.8k→131k／39.4k→126k | 9326→8773／8137→7327，雜訊 |
| aquaculture_pen | 低 | 48→34／37→38 | 96.4k→99.1k／95.3k→98.7k | 2836→3148／2743→2350，雜訊 |
| aquaculture_pen | 中 | 54→55／44→45 | 114.8k→113.9k／110.1k→113.0k | 5239→3056／5021→4997，雜訊 |
| aquaculture_pen | 高 | 55→55／43→44 | 135.4k→129.6k／130.5k→124.9k | 3627→3655／5440→7918，雜訊 |

- 低畫質珊瑚礁：多 5–6 個 draw call、三角形 +1.8%；7 輪量測兩個視角是 +6% 與 −12%，在雜訊範圍內，沒有看到超過
  10% 的退步。先前兩次只有 2–4 輪的量測在機載視角都是 +29%（當時群體材質還是雙面），之後群體與魚改為單面
  並重量。這台機器上無法給出比這更確定的數字。
- 中、高畫質珊瑚礁：三角形增加 36k（中）；高畫質那一列是把碎塊／小群體從 1300／288 降到 1100／192 之前量的，
  調降後沒有重量。毫秒數在這個負載下沒有意義（三角形多三倍的一邊反而較快），**中畫質 ≤ +25% 的預算沒有驗證**。
- 箱網：網衣三角形與批次不變，魚每尾 90 個三角形（原約 114）；兩頁的房間狀態不同，draw call 與三角形的
  差異不全是本分支造成。網衣改為混合後的填充成本沒有量到可用的數字。

`browser_gpu_bench`（只量 open_water 與 tutorial_pool）通過，見下方驗證。

## 已知問題與後續

- 兩個箱網目標（`pen_lap`、`pen_photo`）的座標在出發點，標記本身沒有指向網衣或破洞；這次只讓標記在貼近時淡出，
  沒有動任務資料（另一個分支正在改職涯與合約）。
- 燈光近距離會過曝：在暗水裡自動曝光以整張畫面的對數平均測光，燈照到的近物（1–1.5 m 內的網線、死魚、珊瑚沙）
  比平均亮十倍以上而泛白。這與真機開燈貼近淺色物體的眩光一致，但比真機的相機更容易發生；改測光會影響所有
  潛點，這次沒有動。「死魚腹部較淡」在燈關的截圖才看得清楚。
- 第三人稱截圖用的是放在載具後上方的自由鏡頭：在「放置而非飛行」的 replay 裡，追蹤鏡頭停在離載具約 0.5 m 處，
  而且載具模型載入後保持隱藏，直到切換一次視角。沒有查是 replay 專屬還是一般問題。
- 網衣改成混合材質後不再是拍照判定的遮擋物（`observation_camera.js` 只把不透明或寫深度的材質當實體）：隔著
  網衣可以登錄魚群。破洞拍照與死魚回收由伺服器判定，不受影響。
- 珊瑚礁仍然稀疏：72 個群體分布在約 74×70 m，是伺服器棲地的密度（也是碰撞），這次沒有動。
- `pen.glb`（可攜檢視用，執行時不載入）內嵌的仍是舊的菱形網目，沒有用 Blender 重建。
- 珊瑚礁的水與沙仍是飽和的青綠色，這是 oceanic 水體加上只修正六成色偏的白平衡的結果，屬於全域光學，沒有動。

## 重建與驗證

```bash
python simulator/tools/build_pen_net_texture.py            # 重建 net.webp（Pillow，seed 71）
cd simulator && python tools/run_browser_checks.py browser_scene_looks   # 重拍 after；ROV_LOOKS_TAG=before 拍基準
node --test simulator/tests/test_scene_looks.mjs
```

本機結果（同一台高負載機器）：

- `cd simulator && python -m unittest discover -s tests`：470 項，2623 s，1 項失敗
  `test_sdk_mock.MockSDKTest.test_camera_stream`（fps 2.3 < 5）。單獨重跑仍失敗；同一時間在 `origin/main` 單獨跑
  也失敗（fps 1.5），是負載造成的已知不穩定測試，與本分支無關。之後只改了前端與 `scene_previews.json` 的一個值，
  另跑 `tests.test_fleet_names tests.test_water_type tests.test_aquaculture`：13 項 OK。
- `node --test simulator/tests/*.mjs`：216／216 通過（含新增的 `test_scene_looks.mjs` 5 項）。
- `python simulator/tools/check_changed_js.py origin/main`、變更檔的 `node --check`、
  `python tools/vendor_manifest.py --check`（18 files）通過。
- `ROV_CHROMIUM=/opt/pw-browsers/chromium ROV_BROWSER_TIMEOUT_SCALE=5 python tools/run_browser_checks.py
  observation_smoke browser_underwater_pipeline browser_hud_smoke browser_menu_smoke browser_gpu_bench`：
  observation_smoke 33.5 s、browser_underwater_pipeline 18.1 s、browser_hud_smoke 74.0 s、browser_gpu_bench 452.1 s
  通過；browser_menu_smoke 第一次在 `#titleStart` 的點擊逾時（Playwright 預設 30 s，不受倍率影響），之後單獨重跑
  兩次都通過（239.1 s）。沒有在 `origin/main` 上重跑比較。這些檢查是在群體改單面材質與最後的數量調整之前跑的；
  之後以 `browser_scene_looks` 重拍三張（無頁面錯誤）與 node 測試確認。
