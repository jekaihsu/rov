# 魚類模型改用 CC0 Fish Kit

日期：2026-11-16。分支 `feat/fish-kit`。擁有者找到一套 CC0 的魚類模型包（Fish Kit，cda-social），喜歡它的建模，
要求把水下魚群換成這套模型，讓魚「終於像真的」。本頁記錄：每個場址用哪些魚種與理由、檔案大小、各畫質的三角形預算、
游動方式、授權與來源，以及前後對照圖。

本目錄的 JPG 全部是本專案自己的渲染（`simulator/tools/browser_underwater_look.py`，1600×900）：
`*-before.jpg` 為 origin/main，`*-after.jpg` 為本分支，同一相機、同一姿態。

## 1. 每個場址的魚種與理由

伺服器的魚群中心、速度與數量都沒有改；只改畫面上每一群畫成哪一種魚。第 k 群（`school-k`）畫成
`SITE_SPECIES[場址][k % 數量]`（`simulator/viewer/fish_kit.js`）。場址由 `seabed.js` 的 `siteProfile()` 判斷。

| 場址（情境） | 魚群 0–3 | 理由 |
|---|---|---|
| 網箱（`aquaculture_pen*`） | 嘉鱲（真鯛，madai），全部 8 群 | 台灣澎湖離岸箱網的主要養殖魚之一，也是日本第二大養殖魚種；東亞箱網真實可見。比青甘（buri）更貼近台灣。同一種魚也用在死魚回收任務。 |
| 外海導管架／單樁／開放水域（offshore） | 白腹鯖（saba）、竹筴魚（aji）、青甘（buri）、白腹鯖 | 外海結構物周邊常見的洄游性中上層魚群；青甘（鰤）成群繞著平台與人工結構物。 |
| 港區樁基（harbour） | 竹筴魚、黑鯛（kurodai）、無備平鮋（mebaru）、黑鯛 | 黑鯛（黑格）是東亞港區、防波堤與樁基最典型的魚；無備平鮋在日韓港區岸壁常見；竹筴魚群常在港內。 |
| 珊瑚礁（reef） | 三線雞魚（isaki）、星點笛鯛（shibudai）、黑瓜子鱲（onagagure）、瓜子鱲（kuchibuto） | 依擁有者指定的礁區魚種；都是東亞暖水岩礁／礁區會成群的魚。 |
| 海草床（seagrass） | 三線雞魚幼魚（isaki_young）、黑鯛、竹筴魚、三線雞魚幼魚 | 海草床是雞魚與鯛類幼魚的育幼場。 |
| 沉船（wreck） | 三線雞魚、無備平鮋、三線雞魚、無備平鮋 | 雞魚與平鮋會在沉船與岩礁旁的水層中聚集。 |
| 泳池（`tutorial_pool`） | 竹筴魚 | 伺服器仍在泳池產生魚群（已知問題，見 underwater-look README）；畫一種最普通的魚。 |

沒有採用的：

- **石狗公（kasago）**：擁有者把它列在沉船，但它是不成群、停在底質或結構上的魚；伺服器的魚群是水層中的群體，
  畫成一群游動的石狗公不真實。要放就得做「停在沉船表面」的定居魚，需要沉船表面的位置與法線，本次未做（見第 7 節）。
- **珊瑚礁的小型定居魚（雀鯛、蝴蝶魚、刺尾鯛）**：模型包沒有對應魚種（包內礁魚都是 25–60 cm 的成群魚），
  所以保留原本的程式魚形（`reef_life.js`）。它們的外觀與模型包的魚並排時比較平、較像玩具；我判斷「沒有對應魚種」
  優先，換成模型包的魚會把礁區魚相改錯。見第 6 節判讀。
- 其他沒用的魚種（suzuki、tachiuo、sawara、kamasu、hiramasa、kihada、magochi、katakuchi）沒有放進儲存庫。

## 2. 檔案與大小

`simulator/viewer/models/fish/`，由 `simulator/tools/build_fish_kit.py --source <fish-kit>/fish` 產生
（只把 GLB 當資料讀，不執行模型包的任何程式）。11 種魚 × 3 個檔案，共 33 個檔案、**3.95 MB**（3.77 MiB），
單檔最大 349 KB（遠低於 2 MB）。

| 檔案 | 每種大小 | 內容 |
|---|---|---|
| `<id>.glb` | 277–349 KB | 原檔照抄（約 5,000 三角形，1024×640 WebP 貼圖） |
| `<id>_lo.glb` | 27–28 KB | 遠距模型（約 700 三角形），移除內嵌貼圖（與 `<id>.glb` 的貼圖逐位元組相同，執行時共用） |
| `<id>_card.webp` | 9–14 KB | 遠處魚的十字卡片：完整模型的正側與正上方正交投影（256×128，無光照） |

合計：完整模型 3.51 MB、遠距模型 0.31 MB、卡片 0.13 MB。只有游泳用不到的頭部／鰓蓋圖（`*_head.webp`、`*_cover.webp`）沒有收。

## 3. 渲染與游動

- **三層細節，整個場景共用名額**（`fish_schools.js` 的 `FISH_LOD`）：每幀把所有魚群的魚依離相機距離排序，
  最近的幾尾用完整模型、接著的用遠距模型、其餘用十字卡片。每個魚群是一個 group，裡面三個 instanced mesh；
  位置、航向都寫在 instance 矩陣裡，`observation_camera.js` 拍照時看到的就是畫面上的魚（拍照目標是整個 group）。

  | 畫質 | 完整模型（≤ 名額、距離） | 遠距模型（≤ 名額、距離） | 其餘 |
  |---|---|---|---|
  | 低 | 0 | 5 尾、8 m 內 | 卡片 |
  | 中 | 2 尾、3 m 內 | 32 尾、10 m 內 | 卡片 |
  | 高 | 5 尾、4 m 內 | 56 尾、14 m 內 | 卡片 |

- **十字卡片**：側面卡（體中面）與上視卡（水平面）各 4 段、共 16 三角形。從側面看時上視卡收成零寬、
  從正上方看時側面卡壓扁（`fish_life.js` 的 `CARD_FOLD`），所以不會看到另一張卡的邊線。
- **游動**：沒有移植模型包的 three.js r187 程式；沿用本專案 `fish_life.js` 的頂點著色器體波，
  改為讀每個模型節點 `extras.swim` 的波長 `lambda`、振幅 `amp` 與包絡 `env`（尾端振幅約 0.07–0.10 體長）。
  每尾魚自己的相位、擺尾頻率（依游速，Bainbridge）、轉彎彎曲都照舊放在 per-instance 的 `aSwim`。
  魚群隊形、避讓 ROV、驚嚇加速的邏輯不變；只是較大的魚（青甘 0.65 m）把隊形依體長放大。
- **材質**：仍是 `MeshStandardMaterial`，所以照常經過 `underwater_lighting.js` 的水中光路（衰減、散射、燈光）。
  照片貼圖在水中太亮，所以整體反照率乘 0.35；灰色、低彩度的鱗片（銀色側腹）再乘 0.6，並把該處金屬度拉到 0.5、
  粗糙度 0.38，作為只在燈近處才閃的鏡面；其他皮膚粗糙度 0.85，避免整條魚在燈下像白色塑膠。鰭與眼睛不算銀色。
- **死魚**：網箱死魚改為嘉鱲完整模型（低畫質用遠距模型）側躺在底網上，長 0.35 m（伺服器質量 0.8 kg），
  稍微彎曲、顏色褪成灰白（`pen_life.js`）。模型載入前或載入失敗時仍顯示原本的程式死魚。
- **載入失敗的退路**：模型非同步載入；載入前與 Node 測試中，三層都先畫原本的程式魚形。

## 4. 三角形預算（最壞情況：名額全滿）

| 魚的三角形 | 低 | 中 | 高 |
|---|---|---|---|
| 單尾：完整／遠距／卡片 | 5,160／722／16（嘉鱲；11 種為 4,926–5,258／688–722／16） | 同左 | 同左 |
| 網箱（96／768／960 尾＋4 尾死魚）main → 本分支 | 8.0k → 8.0k | 82.9k → 65.8k | 117.5k → 101.3k |
| 網箱總量（結構 74.1k＋魚） | 82.2k → 82.1k | 157.0k → 139.9k | 191.6k → 175.4k |
| 一般場址魚群（4 群、最多 160 尾） | 9.6k → ≤ 6.1k | 22.8k → ≤ 35.6k | 34.8k → ≤ 68.3k |

網箱數字來自 `node simulator/tools/aquaculture_asset_report.mjs`（`docs/design/scenes/aquaculture/asset-report.json`，
高畫質 ≤ 200k 檢查通過）。一般場址的上限由 `simulator/tests/test_fish_kit.mjs` 檢查（低 9.6k、中 40k、高 75k）。
低畫質三角形沒有增加；中、高畫質的一般場址增加（模型面數多），網箱則因卡片比原本的低階魚身便宜而減少。

draw call：每個魚群最多 3 個（低畫質 2 個；沒有魚的層會隱藏，不送 draw call）。一般場址最多 12（main 4），
網箱最壞 28（main 20，低畫質 20，main 12）。實際上只有離相機近的魚群才會有完整／遠距層。

`browser_gpu_bench`（`--smoke`，本機 SwiftShader 軟體繪圖、共用機器；幀時間只能看量級；main 與本分支同一台、先後執行）：

| 場址／tier／視角 | draw calls main → 本分支 | 三角形 main → 本分支 | 平均幀時間 ms main → 本分支 |
|---|---|---|---|
| open_water／performance／機載 | 46 → 46 | 59.8k → 51.3k | 279 → 252 |
| open_water／performance／第三人稱 | 72 → 84 | 535.7k → 539.1k | 1433 → 1550 |
| open_water／medium／機載 | 53 → 53 | 76.5k → 53.4k | 1222 → 1092 |
| open_water／medium／第三人稱 | 78 → 78 | 552.4k → 529.2k | 1208 → 1500 |
| tutorial_pool／performance／機載 | 26 → 26 | 23.3k → 15.3k | 353 → 336 |
| tutorial_pool／performance／第三人稱 | 60 → 60 | 509.5k → 501.5k | 1867 → 1767 |
| tutorial_pool／medium／機載 | 33 → 33 | 39.1k → 17.3k | 1183 → 1050 |
| tutorial_pool／medium／第三人稱 | 66 → 66 | 525.3k → 511.6k | 1433 → 1392 |

起始機位離魚群 10 m 以上，魚多半是卡片，所以三角形下降；靠近魚群時以第 4 節的最壞情況為準。
open_water 第三人稱多了 12 個 draw call（相機較遠，更多魚群同時有遠距層）。GPU 實機沒有量。

## 5. 前後對照

6 個場址 × 4 張（`-dark` 機載燈關、`-lamps` 機載燈全開、`<場址>close-*` 距魚群中心 1.1 m 的近景，最近的魚約 0.5–1.5 m；
網箱近景 `penclose-*` 是 1.4 m）。`report-before.json`／`report-after.json` 記錄姿態、水型、能見度、曝光與白平衡。
`browser_underwater_look.py` 本次新增了 5 個 `*close` 近景機位，其餘機位不變。重拍：

```bash
cd simulator
ROV_LOOKS_OUT=../docs/design/fish-kit ROV_LOOKS_TAG=before ROV_HTTP_PORT=<origin/main 伺服器埠> \
  ROV_LOOKS_ONLY=pen-dark,pen-lamps,penclose-dark,penclose-lamps,... python tools/browser_underwater_look.py
ROV_LOOKS_OUT=../docs/design/fish-kit ROV_LOOKS_TAG=after  ROV_HTTP_PORT=<本分支伺服器埠> ROV_LOOKS_ONLY=... \
  python tools/browser_underwater_look.py
```

各場址畫面中最近的魚群：網箱＝嘉鱲、礁區＝黑瓜子鱲（school-2）、港區＝無備平鮋（school-2）、海草＝黑鯛（school-1）、
沉船＝三線雞魚（school-2）、導管架＝白腹鯖（school-3）。

## 6. 判讀（對照 `docs/design/underwater-look/README.md` 的影片目標）

- **燈關（日光）**：前：低多邊形、平塗的紡錘形魚，鰭是大三角形。後：每種魚有自己的外形與花紋（嘉鱲的高背與背鰭棘、
  黑鯛的橫帶、白腹鯖背上的波紋、雞魚的縱帶），1–3 m 內看得到眼睛與鰭條；2–3 m 外融入水色，接近影片
  「側腹只比水亮約 1.25 倍、同色相」的目標（網箱近景燈關：魚 (38–67,91–130,52–82)，水 (56,122,74)，近處略暗於水、遠處融入）。這是本次改善最大的部分。
- **燈開**：在本專案的燈光與曝光模型下，1–2 m 內的魚無論反照率多低都會過曝成白色（試過把漫反射設為 0，只剩 4 % 的
  介電質鏡面反射仍然過曝），這與影片「1–2 m 內側腹接近全白」一致；2–3 m 的魚約 104–157（G 通道；舊版調校目標 120–170），
  看得到花紋與顏色，更遠是暗色剪影。為了不像白色塑膠，照片貼圖的漫反射乘 0.35、非銀色皮膚粗糙度 0.85，
  銀色鏡面只出現在銀色鱗片上。但老實說：最近的幾尾在燈全開時仍是白色，花紋要退到 2 m 外才看得清楚；
  這是燈光強度與曝光的問題，不在本次範圍。
- **遠處**：卡片在 10 m 外與遠距模型幾乎看不出差別；在網箱這種密集場景，3–6 m 也會有卡片（名額用完），
  從側面看正常，從斜上方 30–45° 看時較薄。
- **珊瑚礁定居魚**：本次的機位沒有同時拍到程式礁魚與模型包魚群，並排比較沒有驗證（見第 8 節）。


## 7. 授權與來源

- **授權**：Fish Kit 的 `LICENSE.txt` 與作者條款頁（https://cda-social.github.io/fish/terms.html）：魚與魷魚的模型、
  照片、動作、程式與腳本為 **CC0 1.0**。three.js 只內嵌在 `example.html`（MIT），沒有複製。CC0 在 AGENTS.md 允許的授權清單內。
- **貼圖來源是 AI 生成圖片，不是實拍照片**：模型包的 `making/README.md` 說明，側面魚的「照片」由 OpenAI 的圖像生成
  （透過 Codex CLI）產生，再用 Blender 建成網格。已記錄於 `simulator/viewer/models/CREDITS.md`，並在
  `docs/store/steam/page.md` 的 AI 內容揭露（四種語言與內部對照表）加註：魚類貼圖為第三方 CC0 包中預先生成的 AI 圖片。
- 來源：https://cda-social.github.io/fish/kit/fish-kit.zip（圖庫 https://cda-social.github.io/fish/gallery.html）。

## 8. 尚未完成或沒有驗證

- 石狗公（沉船）沒有放：需要停在沉船表面的定居魚做法。
- 珊瑚礁定居魚（雀鯛、蝴蝶魚、刺尾鯛）保留程式魚形；沒有拍到與模型包魚並排的畫面。
- 模型包的口、鰓蓋、眼球、鰭的細部動作（`fish-kit.js`）沒有移植，只有體波與轉彎彎曲；近景時鰭是固定的。
- 魚的邊緣是 alpha 裁切（0.5），遠處鰭會隨 mipmap 變細；沒有做 alpha-to-coverage。
- GPU 實機的幀時間沒有量（本機為軟體繪圖）。
- 燈全開時 1–2 m 內的魚過曝（同 main），屬於燈光／曝光調校，未改。
