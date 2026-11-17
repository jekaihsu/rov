# 掃描材質與岩石（CC0）

日期：2026-11-16。分支 `feat/scan-materials`（基底 `claude/awesome-brahmagupta-2zupid`）。

擁有者回饋：導管架太乾淨；單樁轉接段（TP）看起來假，平台底面是一整片黑。本次把海床、岩石、鋼結構塗裝與鏽蝕、
混凝土、平台格柵換成 Poly Haven 與 ambientCG 的 CC0 實拍掃描材質。**只改呈現層**：伺服器幾何、碰撞、物理與協定都沒有動。

## 1. 素材與授權

全部 CC0 1.0，來源頁、作者、修改內容與授權證明網址見 `simulator/viewer/models/CREDITS.md`「Scanned materials and rocks」。
授權證明：Poly Haven <https://polyhaven.com/license>、ambientCG <https://docs.ambientcg.com/license/>（2026-11-16 查核）。
選材依據：`research_notes/素材/open_assets.md`。

| 用途 | 素材 | 出貨檔（`simulator/viewer/models/scan/`） |
|---|---|---|
| 沙 | Poly Haven sand_03 | `sand_c.webp` 204 KiB、`sand_n.webp` 43 KiB |
| 貝殼砂 | Poly Haven shell_floor_01 | `shell_c` 343、`shell_n` 135 KiB |
| 珊瑚碎屑 | Poly Haven coral_gravel | `gravel_c` 388、`gravel_n` 124 KiB |
| 岩盤露頭 | Poly Haven low_tide_rocks | `rockbed_c` 451、`rockbed_n` 167 KiB |
| 泥 | ambientCG Ground054 | `mud_c` 237、`mud_n` 84 KiB |
| 沙紋 | Poly Haven aerial_beach_01 | `ripple_n` 235 KiB（法線＋高度） |
| 大尺度色差 | Poly Haven coast_sand_01 | `macro_c` 4 KiB（256 px） |
| 塗裝鋼（漆＋鏽） | ambientCG PaintedMetal016＋Poly Haven green_metal_rust | `coating_c` 309、`coating_n` 323 KiB |
| 粗鏽 | Poly Haven rust_coarse_01 | `rust_c` 145、`rust_n` 235 KiB |
| 混凝土 | Poly Haven concrete | `concrete_c` 205、`concrete_n` 125 KiB |
| 花紋鋼板 | ambientCG DiamondPlate008C | `plate_c` 61、`plate_n` 224 KiB |
| 格柵（穿孔走道） | ambientCG MetalWalkway014 | `grating_c` 180、`grating_n` 320 KiB |
| 岩石 | Poly Haven rock_07、rock_09、boulder_01、stone_01 | `rocks.glb` 216 KiB、`rocks_c` 153、`rocks_n` 216 KiB |

合計約 5.3 MB，單檔最大 451 KiB（沒有超過 2 MB 的檔案）。貼圖 1K（海床法線 512 px），WebP；粗糙度或高度放在法線圖的
alpha。沒有用 KTX2：viewer 尚未 vendor Basis 解碼器（`vendor-manifest.json` 的 runtime 為空），本機也沒有編碼器。

重建：`python simulator/tools/build_scan_materials.py --list` 列出下載網址；手動下載到儲存庫外的暫存資料夾後
`--source <資料夾>`。腳本先比對 `simulator/tools/scan_materials_sources.json` 的 SHA-256，下載檔只當資料讀（Pillow
解碼；岩石的 glTF 由腳本自己解析，Blender 只收到頂點清單做減面），不執行下載內容。Poly Haven 條款不允許批次爬取，
所以腳本不會自己下載。

不採用（下載檢視後）：rusty_painted_metal（貨櫃浪板，法線會讓每根鋼管起皺）、painted_concrete／rebar_reinforced_concrete
（綠／紅漆）、metal_grate_rusty（沒有透明度）、ambientCG Rust009、Ground083。PaintedMetal016 的黃黑警示條紋不出現在畫面
（只取鏽蝕區域，漆面改成灰階亮度，再套場景的漆色）。

## 2. 改了什麼

- **海床**（`seabed.js`）：每個場址一組底質（離岸：沙＋貝殼砂；港區：泥＋貝殼砂；沉船：泥＋沙；礁區：沙＋珊瑚碎屑＋岩盤；
  海草：沙＋泥）。掃描貼圖先正規化成灰，再乘場址原本的色票，所以水色與曝光的校正不變。底質讀兩次（2 m 與旋轉 0.35 rad、
  1.37 倍的格子），由 5 m 噪聲混合；160 m 噪聲與 47 m 的海灘掃描再調色，1–10 m 內看不到重複（`mud`、`sandwide` 對照：
  舊版的方格貼圖重複在 `mud-lamps-before.jpg` 很明顯，新版沒有）。沙紋法線 12 m 一格（波長約 0.25 m）。
- **岩石**：棲地岩石（伺服器有碰撞球）換成 rock_07／rock_09／stone_01 掃描，依內切半徑對稱地包住碰撞球（看到與撞到的差距
  ≤ 0.6×(1−r)/(1+r) 倍縮放，約 0.15 m，`test_scan_assets.py` 檢查）；護坡拋石（scour／toe）換成 boulder_01／rock_09，
  頂點都在單位球內，所以仍在膠囊碰撞內。舊錄影才有的純視覺散石（沒有碰撞）上限改成 0.6 m，不再出現 4 m 巨石。
  沉船場的 snag 岩石仍是程序幾何（合併在批次網格裡，未換）。
- **鋼結構**（`structure_materials.js`）：塗裝鋼讀 coating 掃描，alpha 是鏽蝕傾向，`rustAt` 決定漆面破損程度（導管架腿 .55、
  斜撐 .5、TP .88；浪濺區更早破）；再疊原本的附著生物深度帶。單樁本體改深灰環氧漆，黃色只在 TP。港區樁改為濕混凝土。
- **平台**（`site_topside.js`、`topside_materials.js`、`structures.js`）：單樁法蘭平台改成徑向梁、斜撐、外圈梁加鍍鋅穿孔格柵
  （alpha 測試、雙面、不投影），從下面看得到梁與透過格柵的天光，不再是實心黑盤；導管架甲板改成主梁＋次梁＋格柵，貨櫃下有
  花紋鋼板；水面以上漆面加掃描細節（浪濺區附近較多鏽）。TP 在 +3 m 的環形平台也改成格柵加梁。

## 3. 前後對照（1600×900）

`*-before.jpg` 為基底分支，`*-after.jpg` 為本分支；同一姿態、同一相機（`simulator/tools/browser_scan_materials.py`，
`fidelity=real` 機載相機，燈 0／2 級；水面以上為 `browser_daylight_shots.py` 的凍結相機）。基底分支而不是 origin/main：
水面以上的導管架與單樁平台只存在於基底分支。

| 檔名 | 內容 |
|---|---|
| `sand-*`、`sandwide-*` | 開放水域沙床 1.6 m 高、3.4 m 高斜看（廣角，看重複） |
| `mud-*` | 港區泥底 |
| `harbourrock-*` | 港區棲地岩石近看（掃描岩石） |
| `reef-*` | 珊瑚礁碎屑 |
| `jacket1m-*`、`jacket3m-*` | 導管架腿 10 m 深，距表面 1 m／3 m |
| `pile1m-*`、`pile3m-*` | 港區樁 8 m 深，距表面 1 m／3 m |
| `scour-*` | 單樁護坡拋石 |
| `tpsplash-*` | 單樁 TP 浪濺區（水下 1.6 m） |
| `jacket-surface`、`jacket-deck-under`、`monopile-surface`、`monopile-platform-under` | 水面以上 |

`report-*.json`：每張的曝光、白平衡、繪製呼叫、三角形與 GPU 貼圖記憶體。

## 4. 成本（`budget-*.json`，SwiftShader 軟體繪圖，只能相對比較）

GPU 貼圖記憶體由 WebGL 上傳呼叫加總（含 mipmap，不含 render target）。表格為 前 → 後。

| 畫面／檔位 | 繪製呼叫 | 三角形 | 貼圖 MB | 幀時間中位數 ms |
|---|---|---|---|---|
| 沙床 performance | 37 → 37 | 26.8K → 25.3K | 9.1 → 12.3 | 237 → 172 |
| 導管架 performance | 46 → 46 | 31.1K → 29.6K | 9.1 → 12.3 | 300 → 149 |
| 護坡 performance | 40 → 41 | 36.3K → 34.8K | 9.1 → 12.3 | 245 → 530 |
| 單樁水面 performance | 78 → 81 | 105K → 104K | 45.3 → 55.6 | 538 → 689 |
| 沙床 medium | 44 → 44 | 28.9K → 31.4K | 9.6 → 30.5 | 2199 → 2621 |
| 港區泥 medium | 56 → 56 | 38.4K → 81.9K | 9.6 → 48.3 | 2576 → 2528 |
| 礁區 medium | 62 → 63 | 101K → 104K | 14.3 → 36.9 | 2726 → 3070 |
| 導管架 medium | 54 → 54 | 34.6K → 37.1K | 9.6 → 48.3 | 2224 → 2430 |
| 護坡 medium | 47 → 48 | 38.5K → 124K | 9.6 → 39.4 | 3734 → 5634 |
| 單樁水面 medium | 172 → 179 | 246K → 335K | 46.5 → 92.0 | 894 → 1684 |
| 護坡 high | 51 → 51 | 66.3K → 199K | 10.9 → 63.8 | 3345 → 7882 |
| 單樁水面 high | 180 → 186 | 275K → 427K | 95.1 → 162 | 2407 → 2924 |

各檔位預算：
- **low／performance**：結構物不載入掃描貼圖、護坡維持 8 面程序岩石；海床只讀一張 512 px 底質色圖；棲地岩石用 96 面掃描
  加 512 px 色圖。繪製呼叫與三角形不變，貼圖 +3 MB。
- **medium**：海床底質 1K 色圖、512 px 法線、次要底質與沙紋 512 px；結構物 1K 色圖＋512 px 法線；岩石 320 面（棲地）／
  96 面（護坡）。
- **high**：全部 1K，海床多讀第二張法線、次要與岩盤法線、47 m 色差；棲地岩石 1200 面，護坡 96 面。
- 岩石三角形：每顆 1200／320／96；一個單樁護坡約一千顆，所以護坡畫面的三角形主要來自這裡（medium +86K）。

## 5. 尚待改善（誠實評估）

- **燈下 1 m 過曝**：`jacket1m-lamps`、`sand-lamps` 前後都是白色過曝，掃描細節與黃漆在燈下看不到。這是曝光／燈光問題
  （另一分支 `fix/lamp-exposure` 正在處理），本分支未動。
- 導管架在 10 m 深的日光下幾乎只剩綠色，黃漆要靠燈；1 m 黑暗中看得到漆面破損與鏽，已不再「太乾淨」，但附著生物仍是
  程序上色，沒有藤壺／貽貝的立體感（沒有 CC0 附著材質，見研究筆記第 3 節）。
- 從平台下方看格柵偏黑、像星空般的小亮點：穿孔板的孔小，背光下本來就暗，但比起實心黑盤仍有差距；真實平台多為條狀格柵
  （bar grating），開孔率更高。
- 單樁 TP 從水面看底部像浮在水上（深色浪濺帶的下緣），是既有的水面／浪濺帶畫法，本次沒改。TP 在 +3 m 的環形平台本身就不
  寫實（真實 TP 在這個高度沒有整圈平台），本次只把它改成格柵。
- 岩石重用原掃描的法線圖，沒有對減面網格重新烘焙；近看稜線處光影略有不一致。沙漠色的岩石已正規化成灰再上場址色。
- 沙紋在日光的遠景偏弱，在燈下略強；沙紋方向全場一致（真實波紋方向也大致一致，但會隨地形轉向）。
- ambientCG 不提供實際尺寸，泥、花紋鋼板、格柵、PaintedMetal016 的平鋪尺寸是假設值（`scan_materials.js` 的 `SCAN_TILE`）。
- 成本：medium 貼圖記憶體由約 10 MB 增至 30–48 MB（水下）、水面單樁 92 MB；尚未在實體 GPU 上量幀時間。
- `docs/prompts/README.md` 規定「不得提交由照片像素做成的貼圖」（針對外派參考照片）；本次的 CC0 掃描是照片攝影測量，
  依任務指示採用，請審查者確認此規則是否同樣適用於 CC0 掃描素材庫。
