# M3 小艇尾板下水

`?play=1&model=x1&launchMode=swim-platform` 選用小艇；省略 `launchMode`、指定 `a-frame` 或未知值，
維持既有工作船 A 字架。建構 API 為 `launchIntroClass(mode)`，回傳與 `DeployIntro` 相同介面的類別；
`loadAssets` / `play` / `hold` / `release` / `skip` / `aboveWater` / `dispose` 與原程序共用。
不新增協定欄位，不變更伺服器的纜線、浮力、推力、出生點或解鎖閘門。

## 委託選用

| 委託／載具 | 建議下水方式 |
|---|---|
| YX Model R（內部 `x1`）港內 `harbor`、`hull`、`harbor_signoff` | 小艇尾板，低乾舷、人工提機架放入 |
| Model R 近岸 `reef`、未來近岸／養殖巡檢委託 | 有小艇接駁時用尾板；岸邊、水池另行處理 |
| Model R 風場觀測 `offshore` | 平穩海況、小艇執行的觀測委託用尾板 |
| Model O / V / S、離岸大船、重載裝備、惡劣海況 | 既有 A 字架與吊索 |
| `prologue` 水池、岸上課程 | 不自動套用小艇 |

此表是內容編排契約；本 PR **不自動重新指定既有委託**，以遵守「預設不變」。委託入口可在未來以
`launchIntroClass('swim-platform')` 選用；目前可用上述 URL 參數完整體驗。海上風場、平台船與日光直接沿用 main 的 surface_set / wind_farm / daylight。人工搬運速度／手臂姿態／小艇尺寸均為視覺假設，非實測程序。

本次重做已合併 main，依 game-plan §11 的艇上選單方向製作。
研究依據：`docs/reference/real-rov-research.md` 的下水／入水後才運轉推進器與資料缺口、
`docs/reference/own/README.md`（目前僅合成資料）、既有 `../intro-v2/README.md`。
本模式不把較小機型的物理數字套到 Model R。

## 內容與節點

原創硬舭、收尖船艏、白色玻璃纖維船殼、25 條柚木板與黑色填縫、兩側座位／艙蓋、不鏽鋼欄杆與艉緣下水梯、
螢光黃綠捲纜、黑色防磨護套、安全掛繩。只複用專案既有載具，沒有從照片重建載具或品牌字樣。
參考照片未下載、未放入版本庫、未裁切、未作投影或任何貼圖輸入。貼圖由固定亂數種子產生。

座標：glTF 公尺、Y 向上、尾板朝 -Z、水線 Y=0。`SmallBoat` extras 與既有工作船讀取契約相同。

| 節點 | 用途 |
|---|---|
| `rov_slot_0` / `rov_slot_1` | 尾板表面高度的兩個載具中心；程式另加載具半高 |
| `menu_camera` / `menu_target` | 座艙俯看雙載具的眼點與注視點（不是固定背景圖） |
| `hand_left` / `hand_right` | 初始人工操作區錨點，手臂在執行時追蹤機架 |
| `water_entry` | 尾板外下水位置參考 |
| `TetherExit` | 捲纜引出點 |
| `TetherDrum` | 空的相容節點；此模式不用動力絞車 |

相機與停放節點在 meshopt 後保留。`?menuStage=boat` 啟用 `menu/boat_stage.js`；預設選單維持不變。
`goTo('anchor_cockpit'|'anchor_platform'|'anchor_logbook'|'anchor_horizon')` 平滑移動；減少動態偏好直接切換。
畫面路由：主選單／簡報→駕駛台，裝備／載具→尾板，設定／訓練→日誌，場景選擇→艇艏海平線。
`screen_main`、`screen_log`、`frame_licence`、`photo_wall_0…5` 為獨立 UV 0–1 平面；
`gear_slot_0…5` 是裝備架的插槽。控制箱、雙搖桿、無線電、水壺、舵輪、駕駛椅、桌面日誌與筆皆為幾何。
文字沒有烘入貼圖；螢幕使用程式繪製的無文字海圖，照片牆沿用本專案自己渲染的選單預覽，沒有外部照片。
`?menuStage=boat&sky=clear` 為日間；預設晨昏（亦可 `sky=dusk`），兩組共用 daylight 模型。

| 鏡位 | 無 HUD 遊戲內截圖 |
|---|---|
| 駕駛台 | [anchor_cockpit](anchor-cockpit.png) |
| 尾板雙機 | [anchor_platform](anchor-platform.png) |
| 日誌／照片牆 | [anchor_logbook](anchor-logbook.png) |
| 艇上作業地點 | [anchor_horizon](anchor-horizon.png) |
| 日間對照 | [日間海平線](anchor-horizon-day.png) |
原模式前後比較基準見 [A 字架截圖](../intro-v2/README.md)。

## 四階段與水面纜線

| 秒 | 動作 | 模擬器內截圖 |
|---|---|---|
| 0 | 尾板停放；座艙俯視雙機 | [俯視](ingame-overhead.png) |
| 2.3 | 既有 worker.glb 船員以骨架／IK 兩手提起機架 | [提起](ingame-lift.png) |
| 5.2 | 平移到尾板外、緩慢放低，不拋擲、不以臍帶纜吊掛 | [放入](ingame-lower.png) |
| 7.3 | 水面漂浮、手臂收回；沿用入水後的功能檢查效果 | [漂浮](ingame-float.png) |
| 8.2 | 螢光纜線在水面形成鬆弛彎曲，載具端紅標 | [浮纜](ingame-cable.png) |

水上／水下光照與曝光沿用 main；pipeline 安裝已移出 frame()，沒有逐幀建立選項與閉包。
8.8–11.8 秒下潛至伺服器指定起點，交還實際載具與纜線顯示；Esc／跳過／程序 hold 與原模式相同。
截圖由實際 qysim 伺服器／viewer 產生，1600×900、`quality=high`。`introReview` 是明確啟用的
審圖參數：固定過場時間，不更動模擬狀態；因此程序面板仍顯示潛前狀態。沒有照片合成。

現況檢查：`deploy_intro.js` 使用 `0xe9c534` 金黃纜線與出舷後下垂曲線；航行的
`tether/tension.js` 也以 `#e9c534` 為低張力色，依張力漸變橘／紅，`app.js` 從後端節點畫線。
M3 修正新過場纜線的外側繞序（既有 tube 的法線與面方向相反），只改新過場為黃綠 `0xc5f500`，中段貼近水面且蜿蜒、末段跟隨接頭，另加紅色末端套管。
**航行調整方案**：日後將實體纜線低張力底色改黃綠，保留既有警示色／勾點提示；紅標須另繪短套管，
不混入張力色。水面呈現僅依伺服器節點的水面區段加細小視覺波動，不改節點、受力或把水下纜線
硬抬至水面。該方案未改動目前航行顯示，避免把視覺浮纜誤認為物理浮力證據。

## 可重建與預算

```bash
blender -b --python cad/build_small_boat.py -- /tmp/small_boat.glb
python -c "from simulator.tools.build_support_assets import compress; from pathlib import Path; compress(Path('/tmp/small_boat.glb'), Path('simulator/viewer/models/small_boat.glb'), ())"
python simulator/tools/render_swim_platform.py
python simulator/tools/browser_swim_platform_smoke.py
```

建置使用 Blender 4.3.2、既有 `support_assets_lib.py` 的 numpy／Pillow 與 gltf-transform 4.5.1。
不存 .blend、不提交原始 PNG；CC0 授權見 `simulator/viewer/models/CREDITS.md`。

| 指標 | 實測 | 上限 |
|---|---:|---:|
| 小艇全部三角形 | 19,156 | 60,000 |
| GLB 大小 | 292,840 B | — |
| 材質／mesh | 9／17 | — |
| WebP 貼圖 | 512×512 四張（膠殼 base／normal／ORM、柚木） | — |
| GPU 貼圖含 mipmap，RGBA8 ×4/3 | 5.33 MiB | 24 MiB |

詳見 [機器可讀報告](asset-report.json)，測試直接讀 GLB 驗證壓縮擴充、節點與預算，非只讀報告。
既有 Model R、海面 normal、PiP 人員資產不計入小艇預算；小艇模式不另載入工作船模型。
選單執行時的 6 張既有 480×270 預覽與 3 張 512×384 畫布另佔約 6.96 MiB；小艇加選單平面合計約 12.29 MiB，低於 24 MiB。

## 假設與限制

- 尺寸、手動搬運姿態與船艇配置是呈現假設，未當作實船量測或認證的下水程序。
- 此次對話未附參考照片；沒有聲稱完成與照片的逐像素或實船尺寸比對。模型為程式建模，仍可繼續做美術審查。
- 人物沿用專案既有甲板模型；腳步為程序位移與 IK，並非動作捕捉。靜態安全掛繩兩端固定於掛點，非承載用動態吊索。
- 第二台載具為選單／過場擺設，沒有第二套物理。屏幕平面已可替換，這次不新增委託交易或日誌資料系統。
- 原 A 字架比較基準見 `../intro-v2/`，退回版截圖可在 PR 前一提交查看；本目錄新圖全部 1600×900 無 HUD。

## 驗證

實際指令與最新結果見 PR #81 描述。資產測試直接讀取已提交 GLB；截圖工具也檢查遊戲中載入的具名節點與 UV。

- Python：495 tests，OK（skipped=1），827.175 s。
- Node：323 passed，0 failed。
- browser_smoke／browser_menu_smoke／browser_swim_platform_smoke／browser_procedure_smoke／browser_hud_smoke／browser_camera_smoke：6/6 PASS。
- 最後 pipeline 調整後 browser_smoke 再跑 PASS；雙手接觸斷言（<10 cm）加入後小艇 smoke 再跑 PASS。
- 所有 10 張截圖皆為 1600×900，鏡位重拍與手部姿態修正重拍皆無頁面 JS 錯誤。
