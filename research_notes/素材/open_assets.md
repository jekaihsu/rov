# 開放授權 3D 素材與材質調查（寫實化用）

調查日期：2026-11-16。只收白名單授權：MIT、BSD、Apache-2.0、zlib、CC0、Public Domain Mark（AGENTS.md 硬性規則 5）。
每一項的授權都在**原始頁面**確認，下表「授權證明」欄是實際載明授權的網址。本文件只做調查，沒有下載任何素材進儲存庫。

> 圖例：★ 推薦採用、○ 可用但需處理、✕ 不採用。三角面數與檔案大小是頁面或官方 API 標示的數字；未標示者寫「未標示」。
> Poly Haven 檔案大小是用官方 API（`api.polyhaven.com/files/<id>`）查到的 glTF（含貼圖）或 JPG 貼圖總和；
> ambientCG 是官方 API 標示的 1K／2K JPG 壓縮包大小（含位移、AO 等全部貼圖，runtime 只需 color／normal／ORM，轉 WebP 後約為三分之一以下）。

## 0. 結論摘要

- **小型工作船／遊艇（優先 1）：找不到合格的寫實 CC0 模型。** 公開 CC0 船體只有兩類：博物館掃描的歷史船（木造划艇、1898 年救生艇、1940 年代貨船），
  或風格化低模（Grab3D、Kenney、Quaternius）。寫實的現代遊艇／運動釣魚船在 Sketchfab 幾乎都是 CC-BY 或標示不一致。
  **建議：繼續用 `cad/build_support_vessel.py` 自製船體，但把材質與甲板道具換成下面的 CC0 素材**（防滑鋼板、上漆鋼板、繩索、救生圈、救生衣、浮標、油桶）。
  12–25 m 船員運輸船（CTV）同樣沒有任何合格素材。
- **海床、岩石、鏽蝕與工業材質：Poly Haven 與 ambientCG 完全足夠**，品質高、CC0、PBR 齊全，是本次最可靠的來源。
- **海洋生物：Sketchfab 使用者 `ffishAsia-and-floraZia` 有大量 CC0 實物攝影測量模型**（海膽、海星、螃蟹、海參、貽貝、藤壺、
  多種磯釣／岩礁魚類），寫實度極高但面數 40–150 萬，必須減面烘焙。
- **珊瑚：Smithsonian 的珊瑚標本掃描是 CC0**（10 萬面），但是乾燥標本（骨骼色），要重新上色或只當死珊瑚／珊瑚碎屑。
  沒有找到合格的活珊瑚、海扇、海綿、海藻（kelp／海草）3D 模型。
- **人物：MakeHuman 的核心資產是 CC0**，可做比 Quaternius 更寫實的工人；注意部分衣物包是 CC-BY。
- **風機：IEA 15 MW 參考風機（Apache-2.0）提供葉片、塔架、單樁、浮式平台的外形 STL**，工程上正確，沒有材質。
- **音效：Freesound CC0 篩選可找到真實水下錄音（水聽器）、遊艇引擎怠速、無線電雜訊**。Sonniss GDC 套組**不是 CC0**，不合白名單。
- 魚類套件作者 cda-social（<https://cda-social.github.io/fish/>）只有 fish-kit 與 squid-kit（烏賊、軟絲），**沒有珊瑚、礁魚、螃蟹套件**。

## 1. 船隻（優先 1）

| 狀態 | 名稱 | 網址 | 授權／證明 | 格式・面數・大小 | 判斷 |
|---|---|---|---|---|---|
| ✕ | Grab3D Fishing Boat／Motor Yacht／Motorboat／Tugboat | <https://grab3d.com/models/vehicles/fishing-boat/> | CC0 1.0，<https://grab3d.com/license/> | GLB／FBX／BLEND／OBJ；Fishing Boat 20,910 tris、GLB 1.4 MB、2K 貼圖 | 授權合格，但頁面自述為「Small stylized fishing cutter」，屬風格化低模，達不到紀錄片風格。產製方式：載具類為 Blender Python 程序生成（程式碼由 AI 協助撰寫），有機物類為 AI 影像轉 3D 後修整（<https://grab3d.com/how-we-make-models/>），採用時須依 Steam 規則揭露 |
| ✕ | Scottish Maritime Museum CC0 系列（"Venus" fourareen、RNLB Jane Anne、MV Spartan、SY Carola） | <https://sketchfab.com/ScottishMaritimeMuseum/collections/scottish-maritime-museum-cc0-b367fa03fcea40279a5470eea7872709> | CC0（Sketchfab 各模型頁授權欄） | 攝影測量／雷射掃描；Venus 5 萬面、Jane Anne 18.5 萬面、MV Spartan 51 萬面 | 授權合格、寫實，但都是 19–20 世紀的歷史木船或蒸汽貨船，與現代 ROV 作業船不符；MV Spartan 也許可當沉船素材參考 |
| ✕ | Poly Haven `dutch_ship_*`、`ship_pinnace` | <https://polyhaven.com/a/dutch_ship_large_01> | CC0，<https://polyhaven.com/license> | 7–18 萬面 | 17 世紀帆船，不符 |
| ✕ | Sketchfab「Yacht」（k3ddesign、MesXwi）等寫實遊艇 | 例 <https://sketchfab.com/3d-models/yacht-36f922655d5a4f79a48a7fb2188b6b5c> | **CC-BY**（不合白名單） | — | 授權不合格 |
| ✕ | Sketchfab「Epstein's Yacht (The Expanse)」 | <https://sketchfab.com/3d-models/epsteins-yacht-the-expanse-137498e7aabb47dfaee3fe2652fadefa> | 說明寫 CC0，授權欄卻是 CC-BY，上傳者自承不是原作者；又是影視作品的設計 | — | 授權來源不明，不採用 |

**建議做法**：維持自製船體（有船尾游泳平台、駕駛艙、A 架的版本），只換材質與道具。可直接用的 CC0 道具與材質：

| 狀態 | 名稱 | 網址 | 授權 | 面數・大小 | 判斷 |
|---|---|---|---|---|---|
| ★ | Ocean Buoy（紅色燈浮標，有鏽、海生物） | <https://polyhaven.com/a/ocean_buoy> | CC0，<https://polyhaven.com/license> | 12K tris；glTF 1K 3.0 MB／2K 10.5 MB | 很寫實，高 2.7 m，頁面未提到文字或商標；港區與錨地場景直接可用 |
| ★ | Lateral Sea Marker（側標） | <https://polyhaven.com/a/lateral_sea_marker> | 同上 | 13K tris；1K 2.5 MB | 港口航道標，寫實 |
| ★ | Lifebuoy、Life Jacket | <https://polyhaven.com/a/lifebuoy>、<https://polyhaven.com/a/life_jacket> | 同上 | 10.7K／9K tris；1K 約 2.5 MB | 甲板道具；使用前檢查貼圖上有無文字 |
| ○ | Barrel_03、metal_jerrycan、plastic_jerrycan、metal_toolbox、propane_tank | <https://polyhaven.com/a/barrel_03> 等 | 同上 | 1.5K–20K tris | 甲板雜物，寫實；油桶貼圖若有標誌須確認 |
| ★ | ambientCG DiamondPlate008C（防滑花紋鋼板） | <https://ambientcg.com/view?id=DiamondPlate008C> | CC0，<https://docs.ambientcg.com/license/> | 1K 7.9 MB／2K 24.3 MB（壓縮包） | 甲板、踏板 |
| ★ | ambientCG Rope002（含鋼芯）、Rope001、Net004A | <https://ambientcg.com/view?id=Rope002> | 同上 | 1K 約 4–5 MB | 臍帶纜、繫泊纜、網具的貼圖 |

## 2. 海床：岩石、礫石、貝殼、沙紋、泥（優先 2）

### 2.1 材質（PBR）

| 狀態 | 名稱 | 網址 | 授權 | 最大解析度・大小 | 判斷 |
|---|---|---|---|---|---|
| ★ | Poly Haven `coast_sand_01`、`sand_03` | <https://polyhaven.com/a/coast_sand_01> | CC0，<https://polyhaven.com/license> | 8K；1K 全套約 3.4–4.2 MB | 實拍掃描的海岸沙，色調自然；水下套藍綠色衰減後很像淺海沙床 |
| ★ | Poly Haven `aerial_beach_01`（wavy） | <https://polyhaven.com/a/aerial_beach_01> | 同上 | 8K；1K 1.2 MB | 有沙紋（ripple）起伏的航拍沙灘，適合大面積沙紋底圖 |
| ★ | Poly Haven `shell_floor_01` | <https://polyhaven.com/a/shell_floor_01> | 同上 | 8K；1K 3.6 MB | 碎貝殼底質，極適合貝殼砂海床 |
| ★ | Poly Haven `coral_gravel`、`coral_ground_02` | <https://polyhaven.com/a/coral_gravel> | 同上 | 8K；1K 約 3.7 MB | 珊瑚碎屑礫石，珊瑚礁周邊海床 |
| ○ | Poly Haven `low_tide_rocks`、`gravelly_sand`、`brown_mud_02` | <https://polyhaven.com/a/low_tide_rocks> | 同上 | 8K–16K；1K 3.3–6.5 MB | 礫石灘、粗砂、泥；陸上泥地色偏乾，水下需降飽和、加濕 |
| ★ | ambientCG Ground060、Ground056（貝殼沙） | <https://ambientcg.com/view?id=Ground060> | CC0，<https://docs.ambientcg.com/license/> | 1K 5.9 MB／7.5 MB | 與 Poly Haven 互補 |
| ○ | ambientCG Ground093B／C（沙丘、風成層理） | <https://ambientcg.com/view?id=Ground093B> | 同上 | 1K 5.1 MB | 可當沙紋細節 |
| ○ | ambientCG ShellSet001（貝殼圖集，Atlas） | <https://ambientcg.com/view?id=ShellSet001> | 同上 | 1K 4.5 MB | 帶透明的貝殼貼片，可做散布貼花 |

### 2.2 岩石模型

| 狀態 | 名稱 | 網址 | 授權 | 面數・大小 | 判斷 |
|---|---|---|---|---|---|
| ★ | Poly Haven `rock_07`、`rock_09` | <https://polyhaven.com/a/rock_07> | CC0 | 27.8K／23.3K tris；glTF 1K 2.0–2.2 MB | 掃描岩塊，面數適中，最適合 web；可做 LOD |
| ★ | Poly Haven `rock_moss_set_01`／`02` | <https://polyhaven.com/a/rock_moss_set_01> | CC0 | 63K／58K tris（整組）；1K 1.9 MB | 一組多顆小石頭；苔蘚是陸生色，水下可改色當藻類覆蓋 |
| ○ | Poly Haven `boulder_01`、`namaqualand_boulder_04`、`stone_01` | <https://polyhaven.com/a/boulder_01> | CC0 | 72K–124K tris；1K 3.7–5.8 MB | 大型巨石，需減面；沙漠岩色偏紅，需重新調色 |
| ✕ | Poly Haven `coast_rocks_*`、`coastal_cliff_*` | <https://polyhaven.com/a/coast_rocks_05> | CC0 | 100–290 萬面 | 太重，不適合 web（除非離線減面＋烘焙） |
| ○ | Sketchfab「Shells & Stones」（nebulousflynn） | <https://sketchfab.com/models/afb2db4613b94dfd9103b646bce6ebd7> | CC0（模型頁授權欄） | 5 萬面 | 手機拍攝的海灘貝殼與石頭，作者自述近拍覆蓋不足、細節有限 |
| ○ | Poly Haven `lambis_shell`（水字螺） | <https://polyhaven.com/a/lambis_shell> | CC0 | 12.5K tris；1K 2.2 MB | 單一大型貝殼，寫實 |

## 3. 海生物附著、鏽蝕、塗裝鋼、混凝土（優先 3）

**沒有找到 CC0 的藤壺、貽貝、藻類附著 PBR 材質**（Poly Haven、ambientCG 都沒有）。建議：把第 5 節 CC0 的藤壺、貽貝掃描模型
烘焙成可平鋪的高度圖與顏色圖，再與下列鏽蝕材質混合。

| 狀態 | 名稱 | 網址 | 授權 | 大小 | 判斷 |
|---|---|---|---|---|---|
| ★ | Poly Haven `green_metal_rust`（標籤有 ship、tank） | <https://polyhaven.com/a/green_metal_rust> | CC0 | 8K；1K 1.3 MB | 上漆船殼鋼板加鏽斑，很適合船殼與水下結構 |
| ★ | Poly Haven `rusty_painted_metal`、`rust_coarse_01`、`metal_plate_02`（corroded steel sheeting） | <https://polyhaven.com/a/rusty_painted_metal> | CC0 | 16K；1K 2.2–4.2 MB | 腐蝕鋼板、粗鏽 |
| ★ | Poly Haven `metal_grate_rusty` | <https://polyhaven.com/a/metal_grate_rusty> | CC0 | 8K；1K 5.0 MB（含 metal 圖） | 鏽蝕格柵 |
| ★ | Poly Haven `peeling_painted_wall`、`rebar_reinforced_concrete`、`painted_concrete` | <https://polyhaven.com/a/rebar_reinforced_concrete> | CC0 | 8K；1K 3.4–4.1 MB | 剝落油漆、露筋混凝土：碼頭、橋墩、消波塊 |
| ★ | ambientCG Rust009／Rust010、MetalPlates013、Metal041B | <https://ambientcg.com/view?id=Rust009> | CC0，<https://docs.ambientcg.com/license/> | 1K 7–8 MB | 鏽蝕補充 |
| ★ | ambientCG PaintedMetal016（黃色條紋警示漆加鏽）、PaintedMetal017 | <https://ambientcg.com/view?id=PaintedMetal016> | 同上 | 1K 9–10 MB | 海上設施警示漆、船上機具。PaintedMetal017 有「danger」警示標誌，使用前檢查文字 |
| ○ | ambientCG Concrete042C（破損混凝土＋鏽鋼網） | <https://ambientcg.com/view?id=Concrete042C> | 同上 | 1K 8.0 MB | 老舊碼頭結構 |
| ○ | TextureCan「Seashore Rock Texture Covered by Barnacles (Rock 0004)」 | <https://www.texturecan.com/details/173/> | CC0 1.0，<https://www.texturecan.com/terms/>（原文 "Creative Commons CC0 1.0 Universe License"） | 1K–4K＋SBSAR | 唯一找到的 CC0 藤壺岩石材質；**來源不明**（頁面未說是實拍還是生成，也沒有 AI 聲明），採用前要先檢視貼圖並在 PR 中註明 |
| ✕ | AITextured「Seashore Rock … Barnacles」 | <https://aitextured.com/textures/rock/seashore-rock-texture-covered-by-barnacles-free-pbr.html> | 自訂「Free Commercial License v1.1」，不是 CC0 | — | 授權不合格 |

## 4. 珊瑚礁：珊瑚與礁魚（優先 4）

### 4.1 珊瑚（Smithsonian，CC0）

Smithsonian 在 Sketchfab 的珊瑚模型授權欄都是「CC0 Public Domain」，說明欄寫明
"This media file is in the public domain (free of copyright restrictions)"，並連回 Smithsonian 3D 原始資料
（例：Acropora palmata 頁面附 <https://ids.si.edu/ids/media_view?id=3d_package:6fd30c79-3345-4d06-b27c-99d5b320ce5f>）。
**都是博物館乾燥標本**（Acropora palmata 頁面寫 "PREPARATION: Dry"，1862 年採集），也就是珊瑚骨骼色，沒有活體的組織顏色。

| 狀態 | 名稱（型態） | 網址 | 面數 | 判斷 |
|---|---|---|---|---|
| ★ | Acropora palmata（鹿角珊瑚，分枝大型） | <https://sketchfab.com/models/8cb986313c824ac38c373c0fabd0805f> | 100K | 形狀非常真實；需重新上色（褐黃）才像活珊瑚，原色可當白化／死珊瑚 |
| ★ | Madrepora (Acropora) hyacinthus（桌形珊瑚） | <https://sketchfab.com/models/5e8f3939400d4753bcb8e4a43819473c> | 100K | 桌形珊瑚 |
| ★ | Diploria labyrinthiformis（腦珊瑚，塊狀） | <https://sketchfab.com/models/cbbf64f211f84a7cb62887fec11f54fe> | 100K | 塊狀珊瑚 |
| ○ | Pocillopora damicornis、Seriatopora hystrix（細分枝） | <https://sketchfab.com/models/925b1db06f1d407f8bbca23d91031049>、<https://sketchfab.com/models/b6be88ce19e14e5bb038918d111430d5> | 100K | 細枝，減面後容易破 |
| ○ | Porites monticulosa、Goniastrea favulus（塊狀） | <https://sketchfab.com/models/68c44f2315374bb0a4f088c9a1ab174e>、<https://sketchfab.com/models/526ede8a83f943ee868d6991a6d5a533> | 100K | 塊狀珊瑚補充 |
| ○ | Tridacna squamosa（硨磲貝）、Linckia laevigata（藍指海星）、Panulirus longipes（龍蝦） | <https://sketchfab.com/models/4f08856d40e14a9780a7f7714a4ff5a7>、<https://sketchfab.com/models/bb908c03334d47f493955f579fb4313c>、<https://sketchfab.com/models/d7cc2b585ad943ef81274e014e6f745b> | 100K | 礁區點綴；同樣是標本色 |
| ✕ | 海扇（gorgonian）、軟珊瑚、海綿（活體） | — | — | 沒有找到 CC0 的寫實模型（只有化石標本，例如 DigitalAtlasOfAncientLife 的 Porifera 化石） |

格式：Sketchfab 下載提供 glTF／GLB／USDZ 與原始上傳檔，需要登入；壓縮包大小未登入看不到。

### 4.2 礁魚與其他魚（ffishAsia-and-floraZia，CC0）

Sketchfab 使用者 **ffishAsia-and-floraZia** 上傳大量日本與亞洲水生生物的攝影測量模型，每個模型的授權欄是「CC0 Public Domain」，
說明欄第一行也寫「License: **CC0**」，下面附分類學資料。是實物掃描（不是 AI 生成），沒有商標或人物問題。
缺點：面數 40–150 萬、沒有骨架與動畫，必須減面到數千面、烘焙法線，並套用我們自己的游動頂點波（`fish_life.js` 已有）。
**沒有找到雀鯛（damselfish）、刺尾鯛（surgeonfish）的 CC0 模型**；蝴蝶魚科只有關公魚。

| 狀態 | 名稱 | 網址 | 面數 | 判斷 |
|---|---|---|---|---|
| ★ | 關公魚（ハタタテダイ，Pennant Coralfish，蝴蝶魚科） | <https://sketchfab.com/models/27f435f82a0443ef8980b42e4bd9105e> | 816K | 珊瑚礁代表魚，寫實 |
| ★ | 金蝴蝶魚／條紋蓋刺魚（キンチャクダイ，Blue-striped Angelfish） | <https://sketchfab.com/models/a5c0bb6877184e698c1992e5ce1a69d0> | 587K | 礁區代表 |
| ★ | 柴魚（カゴカキダイ，Stripey） | <https://sketchfab.com/models/32e3ef9d5ea24bd3a05a282416f9baac> | 720K | 臺灣、日本岩礁常見 |
| ○ | 隆頭魚科：キツネダイ、キュウセン、アカササノハベラ、ホシササノハベラ、イラ | <https://sketchfab.com/models/a1fa2be4f363454baadf35fafa403e6b>、<https://sketchfab.com/models/e664129f00664e65bf4734e9ad461c80> | 590K–1.29M | 濑魚（wrasse）來源 |
| ○ | 鸚哥魚（アオブダイ，Knobsnout Parrotfish） | <https://sketchfab.com/models/dac672386dd741af8485fcab811b9db4> | 1.43M | 太重，需大幅減面 |

注意：該帳號也有昆蟲、陸生植物；例如名稱含「Staff Sergeant」的模型是蝴蝶（昆蟲），不是雀鯛科的 sergeant major。

## 5. 海藻、海膽、海星、螃蟹、海參（優先 5）

同樣來自 ffishAsia-and-floraZia（CC0，授權寫在各模型頁）：

| 狀態 | 名稱 | 網址 | 面數 | 判斷 |
|---|---|---|---|---|
| ★ | 紫海膽（ムラサキウニ，Heliocidaris crassispina） | <https://sketchfab.com/models/4cbc27daa0404b628e3b2f05b59d4f49> | 590K | 臺灣、日本岩礁最常見的海膽；棘刺減面後可改用 alpha 卡片或實例化 |
| ★ | 海星（イトマキヒトデ，Blue Bat Star） | <https://sketchfab.com/models/14319712a5f445fe8a1eb461eadf6527> | 723K | 扁平，減面效果好 |
| ○ | 海星（モミジガイ，Sand Sea Star） | <https://sketchfab.com/models/0a9e1faf6a024323991cdcd3f04ed1c6> | 435K | 沙地海星 |
| ★ | 螃蟹（イシガニ，Asian Paddle Crab） | <https://sketchfab.com/models/4915ee5a2d9f46af9a24d3b8da505d00> | 568K | 寫實；腳細，減面要小心 |
| ★ | 海參（マナマコ，Japanese Common Sea Cucumber） | <https://sketchfab.com/models/c8fcb7b084df432c9d5765eee264ee02> | 513K | 形狀簡單，減面效果最好 |
| ★ | 貽貝（ムラサキイガイ，Mediterranean Mussel） | <https://sketchfab.com/models/0920004b72a54a099155abbad85de99d> | 492K | 可烘焙成貽貝附著材質（第 3 節） |
| ★ | 藤壺（クロフジツボ，Tetraclita japonica） | <https://sketchfab.com/models/7e2bbead73344312aad9ba99240be7ab> | 156K | 烘焙藤壺附著材質的來源 |
| ○ | 岩牡蠣（イワガキ）、章魚（マダコ等）、伊勢龍蝦、海鞘 | <https://sketchfab.com/models/986e44403c004b9e8ac23d203f89f470> 等 | 0.7–2.4M | 點綴用，面數高 |
| ✕ | 海帶、昆布、海草（kelp／seagrass） | — | — | 沒有找到 CC0 的寫實模型。建議程序生成（帶狀幾何＋頂點擺動），顏色參考自有影片 |

## 6. 離岸與工業（優先 6）

| 狀態 | 名稱 | 網址 | 授權 | 格式・大小 | 判斷 |
|---|---|---|---|---|---|
| ★ | ambientCG MetalWalkway014（鏽蝕格柵走道）、MetalWalkway010 | <https://ambientcg.com/view?id=MetalWalkway014> | CC0，<https://docs.ambientcg.com/license/> | 1K 6.5–8.6 MB | 平台走道、格柵（需要 alpha） |
| ○ | Poly Haven `ladder_sectioned_01`、`modular_industrial_pipes_01`、`overhead_crane` | <https://polyhaven.com/a/ladder_sectioned_01> | CC0 | 12K–90K tris | 工業道具；陸上用品，水下只能當沉沒物 |
| ★ | IEA 15 MW 參考風機（IEAWindTask37/IEA-15-240-RWT） | <https://github.com/IEAWindTask37/IEA-15-240-RWT> | **Apache-2.0**（儲存庫 LICENSE；CAD 子資料夾 README 沒有另外標授權，依儲存庫授權） | `CAD/` 下有 OpenSCAD 產生的葉片、塔架、單樁、浮式平台外形 STL；SolidWorks 檔 | 工程上正確的通用參考風機（不是特定廠牌），**很適合單樁、浮式平台的 ROV 檢測場景**；沒有材質與 UV，需自己上材質；機艙只有發電機的 SolidWorks 組件，README 也說傳動鏈幾何「likely incorrect」。Apache-2.0 須附 LICENSE 與 NOTICE |
| ✕ | 寫實的 CC0 風機機艙／葉片 3D 模型 | — | — | — | Poly Haven、ambientCG、Sketchfab CC0 都沒有 |
| ✕ | 鏈條、卸扣、繫泊浮筒 3D 模型 | — | — | — | 沒有找到高品質 CC0；鏈條建議程序生成（環狀實例化）＋ ambientCG 鏽蝕材質 |

## 7. 人物（優先 7）

| 狀態 | 名稱 | 網址 | 授權 | 判斷 |
|---|---|---|---|---|
| ★ | MakeHuman 核心資產（基礎網格、targets、骨架、system assets）與 CC0 素材包 | <https://static.makehumancommunity.org/assets/assetpacks.html> | CC0：<https://static.makehumancommunity.org/makehuman/faq/are_makehuman_files_free.html>（"The asset license is CC0"；可在閉源遊戲中使用角色、無需署名） | 比 Quaternius 寫實得多的人體比例與臉，可匯出 FBX／glTF（經 Blender）並自動綁骨；再套我們自己的工作服、救生背心、安全帽（`cad/build_deck_crew.py` 的做法）。**注意**：素材包頁面同時有 CC-BY 包（Shoes 02／03、Equipment 02／03、Hats 03／04、Suits 03 等），只能用標示 CC0 的包；社群使用者上傳的衣物要逐件查。「natural」皮膚包可能取材自真人照片，頁面沒說明，建議用合成皮膚並在 PR 中註明 |
| ○ | Quaternius（現用） | <https://quaternius.com/packs/animatedmen.html> | CC0 | 維持現狀即可；風格偏低多邊形 |
| ✕ | Kenney／Grab3D 人物 | — | CC0 | 風格化；Grab3D 的有機物是 AI 影像轉 3D |

## 8. 音效（優先 8）

全部在 Freesound 原始頁面確認授權為 Creative Commons 0。

| 狀態 | 名稱 | 網址 | 長度・格式 | 判斷 |
|---|---|---|---|---|
| ★ | 140816_Brela_HarborSub5（克羅埃西亞港池水聽器，含船用柴油引擎倒車） | <https://freesound.org/people/blaukreuz/sounds/249758/> | 28.8 s，WAV 48 kHz 24-bit 立體聲，7.9 MB | 真實水下港區聲；尾段是柴油機近距離聲，正好當水下聽到的母船引擎 |
| ★ | Underwater crackling sounds_Hydrophone（Hvar 海灣，槍蝦） | <https://freesound.org/people/KaleidacousticsAudio/sounds/630436/> | 13:30，WAV 48 kHz，222.6 MB | 珊瑚礁、岩礁的真實背景劈啪聲；只需截一段做循環 |
| ★ | 130725_YachtIdleStart_F_4824（700 HP 雙機遊艇，船尾錄音，怠速→加速） | <https://freesound.org/people/blaukreuz/sounds/195743/> | 1:07，WAV 48 kHz 24-bit，18.5 MB | 甲板上聽到的引擎怠速；說明沒提到人聲 |
| ○ | fishing boat onboard engine idle and rev | <https://freesound.org/people/kyles/sounds/451400/> | 1:14，FLAC 48 kHz | **含近距離人聲**（標題寫明），要剪掉人聲段 |
| ★ | REAL RADIO WHITE NOISE（車用收音機白噪、干擾） | <https://freesound.org/people/metrostock99/sounds/345101/> | 36 s，WAV 44.1 kHz | 純雜訊，無廣播內容，適合無線電／通訊雜訊底 |
| ○ | winch and metallic chain | <https://freesound.org/people/vestibule-door/sounds/669695/> | 15 s，WAV 44.1 kHz | 沒有找到船用絞機的 CC0 錄音；這段可當收放纜的金屬鏈聲。其他 CC0「winch」結果多是電動千斤頂（mpuffenbarger 683806） |
| ✕ | 收錄真實廣播內容的無線電錄音（如 NOAA 天氣廣播、短波電台） | — | — | 授權是 CC0，但內容含第三方節目與真人聲音，避免使用 |
| ✕ | Sonniss GDC Game Audio Bundle | <https://sonniss.com/gameaudiogdc/>，授權 <https://sonniss.com/gdc-bundle-license/> | — | **不是 CC0**：是 Sonniss 自訂的免版稅授權，可商用、免署名，但不得以音效形式轉售、**禁止用於 AI／ML 訓練**。不在白名單內，不得採用 |

## 9. 授權未通過或不採用（摘要）

- **Sonniss GDC 套組**：自訂免版稅授權，有限制（不可轉售音效、禁止 AI 訓練），不是 CC0。
- **AITextured 藤壺岩石材質**：自訂 Free Commercial License。
- **Sketchfab 寫實遊艇（k3ddesign、MesXwi 等）**：CC-BY。
- **「Epstein's Yacht」**：授權欄與說明不一致，上傳者不是作者，又是影視作品設計。
- **MakeHuman CC-BY 素材包**（Shoes 02／03、Equipment 02／03、Hats 03／04、Pants 02／03、Suits 03 等）：CC-BY。
- **BlenderKit**：預設「Royalty Free」授權不是 CC0；本次沒有找到 CC0 的船。
- **Meshy、Tripo 等 AI 生成社群模型**：AI 生成且平台自己提醒不涵蓋第三方權利，不採用。
- **授權合格但品質不合**：Grab3D 船（風格化，部分 AI 協助）、Scottish Maritime Museum 歷史船、Poly Haven 古帆船、Kenney／Quaternius 船。

## 10. 使用注意

1. Poly Haven 服務條款禁止未經許可爬取網站，請從網頁手動下載，不要寫批次腳本抓取；官方 API 只用來查詢清單。
2. Sketchfab 下載需要登入。下載後在 `CREDITS.md` 記錄模型頁網址、作者、授權與修改內容（減面、烘焙、重新上色）。
3. 所有攝影測量模型（ffishAsia、Smithsonian）都要離線處理：Blender 減面到數千面，烘焙 normal map，貼圖 1K WebP，gltf-transform meshopt 壓縮；
   單檔目標 < 500 KB，任何新資產超過 2 MB 必須在 PR 中說明（AGENTS.md 規則 6）。
4. Smithsonian 標本是骨骼色。若要做活珊瑚，重新上色屬於我們的修改，須在 CREDITS 註明；不要聲稱是活體顏色。
5. 有文字的貼圖（警示標誌、救生圈、油桶）使用前要逐張檢查，不得含真實品牌或船名（規則 8）。
6. Apache-2.0 素材（IEA 風機）要附 LICENSE 全文；CC0 素材不需署名，但仍在 CREDITS 記錄出處。
