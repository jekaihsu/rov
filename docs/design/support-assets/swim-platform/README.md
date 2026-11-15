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
`launchIntroClass('swim-platform')` 選用；目前可用上述 URL 參數完整體驗。風場剪影是佈景，
不是任務目標或碰撞物。人工搬運速度／手臂姿態／小艇尺寸均為視覺假設，非實測程序。

基底 `138c242` 的 `docs/design/game-plan.md` 只有 §1–10，未有指定的 §11；依本次使用者明確要求執行。
研究依據：`docs/reference/real-rov-research.md` 的下水／入水後才運轉推進器與資料缺口、
`docs/reference/own/README.md`（目前僅合成資料）、既有 `../intro-v2/README.md`。
本模式不把較小機型的物理數字套到 Model R。

## 內容與節點

原創白色玻璃纖維後半船體、25 條有細木紋的柚木板與黑縫、兩側座位／艙蓋、不鏽鋼欄杆與下水梯、
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

相機與停放節點在 meshopt 後保留。選單可取得 `getObjectByName(...)` 的世界位置；本 PR 提供錨點，
不替換原主選單。原模式前後比較基準見 [A 字架截圖](../intro-v2/README.md)。

## 四階段與水面纜線

| 秒 | 動作 | 模擬器內截圖 |
|---|---|---|
| 0 | 尾板停放；座艙俯視雙機 | [俯視](ingame-overhead.png) |
| 2.3 | 兩手握機架提起；簡化袖子、前臂、手掌 | [提起](ingame-lift.png) |
| 5.2 | 平移到尾板外、緩慢放低，不拋擲、不以臍帶纜吊掛 | [放入](ingame-lower.png) |
| 7.3 | 水面漂浮、手臂收回；沿用入水後的功能檢查效果 | [漂浮](ingame-float.png) |
| 8.2 | 螢光纜線在水面形成鬆弛彎曲，載具端紅標 | [浮纜](ingame-cable.png) |

高畫質時，小艇水上過場略過水下自動曝光，避免白船身與海面過曝；入水即恢復原渲染流程。
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
| 小艇全部三角形 | 16,740 | 60,000 |
| GLB 大小 | 174,664 B | — |
| 材質／mesh | 6／6 | — |
| WebP 貼圖 | 512×512 一張 | — |
| GPU 貼圖含 mipmap，RGBA8 ×4/3 | 1.33 MiB | 24 MiB |

詳見 [機器可讀報告](asset-report.json)，測試直接讀 GLB 驗證壓縮擴充、節點與預算，非只讀報告。
既有 Model R、海面 normal、PiP 人員資產不計入小艇預算；小艇模式不另載入工作船模型。
簡化手臂與遠景額外約千個三角形，不需貼圖。

## 限制

- 這是原創程式建模的低面數場景，非照片級重建；梯子轉彎與玻璃纖維外形仍偏簡化。
- 人物只有簡化雙臂，沒有全身行走／指節動畫；掛繩與捲纜為靜態道具，放纜由動態段表現。
- 海面與船身小幅擺動沿用過場效果，非水動力求解。紅標長度隨過場纜線曲線略變。
- 兩台停放載具共用既有模型資料；第二台只是佈景，沒有第二套物理或遙控。

## 本機驗證（2026-11-15）

- `cd simulator && python -m unittest discover -s tests`：**471 tests，OK**，502.172 s。
- `node --test simulator/tests/*.mjs`：**211 passed，0 failed**。
- `cd simulator && python tools/run_browser_checks.py browser_menu_smoke browser_hud_smoke browser_procedure_smoke browser_camera_smoke browser_smoke`：**5/5 passed**（94.8／27.2／189.2／3.2／35.7 s）。
- `python simulator/tools/browser_swim_platform_smoke.py`：**PASS**；驗證預設與未知參數回退、
  hold／release、手提高度、入水高度、水面節點、纜線向艉後彎曲、面方向、skip／座標交接、callback 一次與場景清理。
- `python simulator/tools/render_swim_platform.py`：5 張 1600×900 實際模擬器截圖，無頁面 JS 錯誤。
- `git diff --check`：PASS。

環境：Python 3.12、Node 24.22.1、Blender 4.3.2、Chromium 軟體渲染。
初次完整 Python 執行發現缺少建議的 numba 後中止，安裝 numba 0.68.1 後從頭完整重跑上述 471 項；
未跳過或放寬既有測試。截圖為驗收所需產生物，隨此 PR 提交；每張均低於 1.1 MB。
