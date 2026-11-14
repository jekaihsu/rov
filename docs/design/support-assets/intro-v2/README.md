# 下水動畫 v2：A 架吊放取代「拋過艉板」（前後對照）＋工作船顯示記憶體預算

所有圖片 1600×900 PNG（< 1.1 MB）。`before-*` 是 main 上的舊動畫，`after-*` 是本次的新動畫。
兩組都用 `simulator/tools/render_support_assets.py --intro-frames` 在同一個審圖頁（`tools/asset_review.html?asset=intro&t=…`）
以固定 1/30 s 步長把動畫推進到指定時間後算圖，所以時間點準確、機位與燈光一致（遊戲內擷取在軟體繪圖下會漂移數秒）。
舊動畫與新動畫的時間軸不同，下表是「同一階段」的對照，不是同一秒。

```bash
cd simulator
python tools/render_support_assets.py OUT --intro-frames --prefix after \
  --times 1-establishing=0.8 2-pickup=2.0 3-overboard=4.4 4-water=7.3 5-underwater=10.0
python tools/render_support_assets.py OUT --intro-frames --viewer OLD/simulator/viewer --prefix before \
  --times 1-establishing=0.8 2-pickup=3.2 3-overboard=5.6 4-water=6.2 5-underwater=9.0
python tools/render_support_assets.py OUT --intro --prefix after-ingame --times 2-hoist=2.0   # 遊戲內（含 HUD 按鈕）
```

| 階段 | 前（秒） | 後（秒） | 說明 |
|---|---|---|---|
| 1 開場 | `before-intro-1-establishing.png`（0.8） | `after-intro-1-establishing.png`（0.8） | 右舷船艏外的開場鏡頭不變；後甲板上 ROV 已掛好吊索，A 架向內收 |
| 2 起吊 | `before-intro-2-pickup.png`（3.2，抱起） | `after-intro-2-pickup.png`（2.0） | 甲板手用控制器操作 A 架吊起，纜線手扶著機架；不是人抱 |
| 3 出舷 | `before-intro-3-overboard.png`（5.6，拋出） | `after-intro-3-overboard.png`（4.4） | A 架外擺，ROV 吊在艉後約 1.3 m，纜線手改握纜線 |
| 4 入水 | `before-intro-4-water.png`（6.2，水花） | `after-intro-4-water.png`（7.3） | 放到水面後脫鉤，水面功能檢查：燈閃兩次 |
| 5 下潛 | `before-intro-5-underwater.png`（9.0） | `after-intro-5-underwater.png`（10.0） | 下潛，纜線由絞車放出 |
| 遊戲內 | — | `after-ingame-intro-2-hoist.png` | 實際伺服器上的動畫；舊版在機載視角下 ROV 被隱藏，新版動畫期間會顯示 |

## 新的下水流程（約 11.8 s，Esc／「跳過」與 `?nointro` 照舊）

| 時間 | 動作 | 依據 |
|---|---|---|
| 0–1.2 s | ROV 在後甲板、吊索已掛；纜線手蹲下扶住機架，甲板手拿 A 架控制器 | 回收／搬運時抓機架、不抓纜線（`shipboard_handling.md` §5） |
| 1.2–2.3 s | 吊起到高過舷牆 | — |
| 2.4–4.2 s | A 架外擺（液壓缸跟著伸縮），吊著的 ROV 有小幅擺盪；約 3.2 s 越過艉板時纜線手放手、改握纜線 | 放置而非拋擲（`real-rov-research.md`「只用纜線把 ROV 放入水中、不可拋擲」，`fifish_x1_system.md`） |
| 4.2–6.4 s | 用吊索把 ROV 放進水裡（小水花、水面漣漪），不是用臍帶纜吊 | 臍帶纜不當吊索（`shipboard_handling.md` §1、§5） |
| 6.4–6.9 s | 吊索放鬆、脫鉤；鉤子收回滑輪，A 架之後收回 | — |
| 6.4 s 起 | 纜線從絞車放出（纜盤依放出長度轉動），纜線手雙手交替送纜 | 小船上纜線從甲板捲盤拉出（`real_dive_footage.md` §6.1 V12）；纜線手負責送纜（`shipboard_handling.md` §5） |
| 7.1–8.0 s | 水面功能檢查：燈閃兩次 | — |
| 8.1–8.7 s | 推進器三次短脈衝（氣泡、水面小漣漪、機身微微偏擺），**只在入水後** | 入水後才解鎖、空氣中推進器不得超過 30 s（`fifish_x1_system.md`、`real-rov-research.md`） |
| 8.8–11.8 s | 下潛到起始深度，鏡頭切到水下環繞 | 與舊版相同 |

**假設（沒有 X1 公開資料）**：約 30 kg 的 X1 以艉 A 架加四腳吊索吊放；鉤子是可由控制器遠端脫鉤的型式；
甲板兩人（甲板手＋纜線手）；吊放速度、A 架角度、吊索長度都是視覺上的合理值，不是量測值。
小型 ROV 在碼頭、岩岸、湖岸也常見手抱放入（`real_dive_footage.md` §6.1），本動畫只處理工作船情境。
本專案目前沒有 T23 下水前程序模組（`simulator/viewer/procedure/` 不存在），所以動畫仍是短的過場，
不含逐項檢查表；之後若有該模組，動畫不應重複其內容。

## 工作船顯示記憶體（WebP 在 GPU 上解成 RGBA8，估算 = Σ 寬×高×4 B×4/3 含 mipmap）

`render_quality.js` 的 `assetTextureTier()`：只有使用者選「高」才載入 `workboat_high.glb`，其他（含預設「自動」）載入 `workboat.glb`。

| 品質設定 | 前（同一個檔案） | 後 | 檔案 |
|---|---|---|---|
| 自動（預設）／流暢／標準 | 94.2 MiB（98.7 MB） | **23.5 MiB**（24.6 MB） | `workboat.glb` 1.14 MB |
| 高 | 94.2 MiB（98.7 MB） | 59.5 MiB（62.4 MB） | `workboat_high.glb` 1.70 MB |

| 貼圖組（基礎色／法線／ORM 各一張） | 前 | 後：標準 | 後：高 |
|---|---|---|---|
| 船殼 `hull_*` | 2048×1024 | 1024×512 | 2048×1024 |
| 甲板止滑 `deck_*` | 1024² | 512² | 1024² |
| 艉板 `transom_*` | 1024×512 | 512×256 | 512×256 |
| 舊漆面 `paint_*`、拉絲金屬 `metal_*` | 1024² | 512² | 512² |
| 帆布 `fabric_*` | 512² | 256² | 256² |
| 船籍字 `registration`／甲板螢幕 `screen` | 1024×256／512×320 | 512×128／256×160 | 512×128／256×160 |

降解析度的是在下水鏡頭距離下看不出差別的部分（艉板、甲板、漆面、金屬、帆布、字、螢幕）；這些貼圖本來就是
程式產生的平鋪紋理，沒有做圖集（atlas）：合併成圖集會改變平鋪 UV，省下的只是貼圖數量而不是記憶體。
`python simulator/tools/build_support_assets.py --report` 會列出每張貼圖與總量；建置時標準檔超過 32 MiB 會失敗。

## LOD 與碰撞代理

| 節點 | 三角形 | 切換距離 |
|---|---|---|
| `LOD0`（完整，含可動的 A 架、液壓缸、滑輪、吊鉤、纜盤） | 49,545 | 0 m |
| `LOD1`（全部網格 Blender Decimate 0.4） | 19,788 | 35 m |
| `LOD2`（Decimate 0.12，去掉繩、反光條、燈、螢幕、鋅塊、纜線、船籍字、輪胎、銅槳、深色小件） | 3,978 | 90 m |
| `CollisionProxy`（封閉低面數船殼＋駕駛艙方塊，extras `proxy: "collision"`，前端隱藏） | 78 | — |

`deploy_intro.js` 把三層包成 `THREE.LOD`，碰撞代理放在 `boat.userData.proxy` 供之後的碰撞／遮擋查詢使用（本次沒有接上任何查詢）。

## 仍然不足（如實說明）

- 吊索是直線圓柱，鬆弛時不會下垂；脫鉤後吊索平躺在機架上。
- 人物腳步不移動：纜線手原地轉身；甲板手的控制器沒有電纜。
- 燈光閃爍與推進器脈衝是動畫效果，沒有接到伺服器的燈光與推進器狀態（動畫期間模擬是暫停的）。
- LOD1／LOD2 是自動減面，近看會有破面；只在 35 m／90 m 以外出現，下水動畫的鏡頭都在 35 m 內。
