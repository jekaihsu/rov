# M2 水庫進水口

基底 `main@138c242`。通用虛構水庫，照片僅用於構圖對照；沒有照片、裁切、投影貼圖、
真實地名或標誌進入資產。未放人物。尺寸、水色、流速與勾纏保持力全部是訓練假設，非場址量測。

`reservoir_intake`：淡水、泥底、水深 19 m、能見度 3 m、無背景流或潮汐；
起始已放纜 4 m，沿用既有捲盤放纜功能。由橘藍浮動碼頭邊起航，沿護坡下潛、拍攝堵塞、回碼頭。水庫停用海洋生態與海上風機。
參考 SOP 的正常作業要求停機與隔離；本情境的 0.35 m/s 局部吸入流是未完全隔離的危險演練。

## 同源幾何與限制

`qysim/reservoir.py` 定義護坡、階梯、標尺、浮筒、欄杆繩索、兩艘作業平台船、控制箱、
工具箱、螢光黃綠臍帶纜、進水口、閘門導槽、柵條與沉木。柵條、堵塞枝條與沉木有 snag_hold。
水下沿用 Box／Cylinder（膠囊）碰撞；護坡以 0.5 m 階梯段近似斜面，沒有新增碰撞型別。
水上完全離水的裝飾透過 `scenario.reservoir_decoration` 傳送，避免讓設備纜圈加入水下物理。
護坡六角接縫為程序 WebP，沒有浮雕位移；低能見度近距離可看到階梯近似。

`viewer/reservoir.js` 從相同原語批次繪製水下實體；山坡使用低面數曲面與少量實例樹冠，
遠景公路橋與水面為程序裝飾。標準／低畫質圓柱細分不同，低畫質樹木數減為三分之一。
風景不是照片級地形；平台船為原創簡化造型。沒有發電機操作、閘門動畫或壓力鋼管進入任務。

局部流場由 `World.current_at_many` 統一施加於載具／纜線／泥沙，場外不改舊行為。
使用平滑球形權重疊加向量，非 CFD；見 `simulator/PROTOCOL.md`。
拍照目標需在第一個目標後、面對堵塞、0.6–2.8 m 且無遮擋才完成。

兩個 NED 具名相機 `embankment_overlook`／`dock_equipment` 位於 `scenario.camera_anchors` 與
`models/reservoir/cameras.json`；選單潛點頁使用俯視錨點。它們不更動真實模式相機權限。

## 重建與資產

```bash
blender -b --python cad/build_reservoir.py
python simulator/tools/build_menu_previews.py
node simulator/tools/reservoir_asset_report.mjs
python simulator/tools/run_browser_checks.py browser_reservoir_review browser_reservoir_onboard browser_reservoir_menu
```

Blender 輸出暫存在忽略的 `simulator/output/reservoir`，不保存 `.blend`。
固定 glTF Transform 4.5.1 產生 meshopt＋WebP 的 `default.glb`／`low.glb`。
GLB 是包含遠景的可攜原語預覽，執行時使用同源原語與實例遠景，避免與物理漂移。
原創資產 CC0；工具授權見 `simulator/viewer/models/CREDITS.md`。
提交小型 GLB、WebP、選單資料與 JPEG／JSON 報告，分別供離線部署、選單與本次審查使用。

## 證據

水上兩張為模擬器原生選單場景的兩個具名固定機位（同一 Environment／Structures）；水下三張使用既有單幀 replay、真實模式、機載相機與原有燈具，
不是 Blender render，也不是實際飛行軌跡。關燈使用 0 檔，開燈使用 2 檔；不降低 3 m 水體衰減。
渲染時間來自共享 CPU／SwiftShader，不能當作 GPU FPS。

- [護坡俯看碼頭](embankment-overlook.jpg)
- [碼頭設備](dock-equipment.jpg)
- [機載開燈](onboard-lights-on.jpg)
- [機載關燈](onboard-lights-off.jpg)
- [攔污柵近看](rack-close.jpg)

指定 `game-plan.md` 在基底只有 §1–10，沒有 §11；以使用者規格、§5／8、作業研究 §2.7、
場景 README 與箱網場景做法補足。自有量測目錄目前僅有合成資料，未引用為現場證據。

資產報告：[asset-report.json](asset-report.json)。標準版保守計數水上 97,550／水下 60,830；
低版水上 49,094／水下 27,062 三角形。水下上界把整個遠景也計入；實際水下結構為 14,568／9,600。跨水線材質批次同時計入兩者，含樹冠實例數。
一張 256² RGB WebP 以 RGBA 加 mipmap 計為 0.333 MiB；加四張共用海床貼圖為 1.667 MiB。
不含共用載具與後製 framebuffer；沒有將 WebP 壓縮檔大小當 GPU 記憶體。

## 驗證

完整後端回歸：`cd simulator && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -s tests -v`，
479/479 通過，667.221 s（整合原 PR 初模後重跑）。限制 BLAS 執行緒僅減少小矩陣運算的執行緒負擔，沒有跳過或放寬測試。

- `node --test simulator/tests/*.mjs`：211/211 通過。
- `cd simulator && python -m unittest discover -s tests -p test_reservoir.py`：3/3 通過，
  包含區域邊界／方向／疊加、無設定相容性、固體遮蔽、起點淨空、拍照前置條件、初始張力。
- `cd simulator && python -m unittest discover -s tests -p test_currents.py`：42/42 通過。
- `python simulator/tools/run_browser_checks.py browser_reservoir_launch`：1/1 通過，正常 URL 進場。
- `python simulator/tools/run_browser_checks.py browser_reservoir_review browser_reservoir_onboard browser_reservoir_menu`：2/2 通過，
  最後山林位置調整後獨立重跑 `browser_reservoir_review` 亦通過（70.4 s）。
- `python simulator/tools/run_browser_checks.py browser_reservoir_menu`：通過（43.4 s，整合後重跑），輸出原生選單潛點縮圖與兩張具名機位圖。
- M1 相同四項瀏覽器：`observation_smoke`（11.8 s）、`browser_tether_smoke`（21.5 s）、
  `browser_menu_smoke`（206.7 s）通過；`browser_smoke` 首次等待燈光狀態逾時，單獨重跑通過（190.3 s）。
  另以未修改的 `main@138c242` 對照，smoke 也在點擊步驟逾時；兩者失敗位置不同，不能證明同一原因。
- `node simulator/tools/reservoir_asset_report.mjs`：三角形、貼圖預算與 GLB 的 meshopt／WebP extensions 斷言通過。
- `python simulator/tools/check_changed_js.py origin/main`、`python simulator/tools/vendor_manifest.py --check`、
  `git diff --check` 通過。

最終可攜 GLB（含山林與橋梁）標準 936,072 bytes、低版 383,980 bytes。

水上截圖最後由 `browser_reservoir_menu` 更新，使用原生選單的水上照明，未套水下自動曝光。
`render-report.json` 仍量測飛行頁面的完整場景渲染（含其後製），不是選單的 FPS。

淡水沿用既有 `water="fresh"` 的壓力換算密度；載具水動力仍使用專案既有共用 RHO=1025 模型，
本次未重標定載具／纜線的淡水浮力。

整合原 draft PR #80 的初模提交後，沿用其 `regional_flows` 與 `reservoir_decoration` 契約，
保留 `reservoir_overlook`／`reservoir_equipment` 相機別名、舊 `reservoir_*` 繪圖種類及所有原有流場／任務測試。
原初模 GLB 由本次含山林、橋與程序貼圖的標準／低版替代，舊版本保留在 Git 歷史。
同工具版本重建的幾何邊界與三角數一致，但本機兩次壓縮 payload 有位元差異，不保證 GLB 雜湊完全一致。

整合後 `browser_reservoir_launch browser_reservoir_review browser_reservoir_onboard browser_reservoir_menu`
四項一起重跑，4/4 通過（13.0／54.9／69.0／43.4 s）；Node 211/211 亦重跑通過。
