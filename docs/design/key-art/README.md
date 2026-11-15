# 主視覺試作：實景＋抽象符號

參考擁有者提供的海報提示詞（上半真實影像、下半由主體提煉的抽象符號；瑞士式解構、細線、網格、編號、
印刷顆粒與錯位）。`poster.html` 以 SVG 與 CSS 製作，`poster.jpg` 是輸出（3:4，1500×2000）。

- 上半：遊戲內的 A 字架下水畫面（`photo.png`，取自 `docs/design/support-assets/intro-v2/`），輕量調色。
- 下半：YX Model R 的俯視符號——機身模組、四具向量推進器（45° 短軸）、兩具垂直推進器、相機罩、臍帶纜弧線、
  深度軸；橘色作為功能編碼（印刷錯位的第二版、目前深度），青綠標記相機與纜線端點。
- 文字只作索引標註（型號、Block、編號）。

可延伸用途：Steam 主視覺與商店圖、載入畫面、章節標題卡、YX 執照與裝備圖示、每台機型一個符號（R／O／V／S）。

## 識別系統與章節標題卡（試作）

- `marks.html` → `marks.jpg`：YX 標誌（Y 的直線延伸成臍帶纜，X 是推進器的兩條對角線；深色底版本只有一筆用橘色），
  以及四台機型的符號（Model R／O／V／S），每個只用三到四個元素。
- `chapter_card.html?c=0|1|2` → `chapter-0/1/2.jpg`：章節標題卡（16:9），左半是該章實景，右半是該章符號
  （水池：矩形、水線、下潛點；港口：水線、三根樁、船殼弧；養殖場：浮框圓環、網衣斜線、破洞）。

目前的實景是既有截圖（港灣那張是調整水質之前的過飽和綠），正式使用前要重拍。

## 進入遊戲（`simulator/viewer/brand/`）

試作的標誌與符號已搬進遊戲，兩邊共用同一份來源 `simulator/viewer/brand/marks.js`（純函式，輸出 SVG 字串）：

- `identity_sheet.html` → `identity-sheet.jpg`：直接匯入 `marks.js` 重畫的總表（需以 HTTP 開啟）。取代 `marks.html`
  作為識別系統的現行版本；`marks.html`／`marks.jpg` 保留為第一版試作紀錄。
- Model V 與 Model S 重畫：第一版像電視機。現在是側視的 ROV——實心浮力塊、開放框架（V 有滑橇、S 有斜撐）、
  前伸機械臂與張開的夾爪、由頂部離開的臍帶纜（V）或吊點（S），各四個元素加一個橘點。
- 線寬依顯示尺寸決定（`strokeFor(size)`），同一個符號在 32 px 與 600 px 都清楚。
- 章節符號共 11 個（水池、港灣、船殼、離岸、礁區、沉船、夜間回收、箱網、事故、課程、通用）。
- 標誌的青綠端點改為墨色：遊戲內只用深海藍黑、冰白、安全橘三色，橘色只出現在標誌的一筆與每個符號的一個點。

`in-game/` 是遊戲內截圖（1600×900，由 `simulator/tools/browser_brand_shots.py` 產生）：

| 檔案 | 內容 |
|---|---|
| `title.jpg`、`loading.jpg` | 標題畫面與載入畫面的 YX 標誌 |
| `hangar-model-r.jpg`、`-o.jpg`、`-v.jpg` | 機庫：機型標題旁與選擇鈕上的機型符號 |
| `chapter-card-prologue.jpg`、`-harbor.jpg`、`-offshore.jpg` | 章節標題卡 |
| `licence-trainee.jpg`、`licence-senior.jpg` | 操作員執照（見習、資深） |

章節標題卡左半的實景由 `simulator/tools/build_chapter_plates.py` 從 `docs/design/scenes/` 的場景截圖裁出
（`viewer/brand/plates/`，每張 30–70 KB）。這些截圖含任務標記球，正式版要重拍不含標記的畫面後重跑該工具。
委託方名稱（港務單位、船東、離岸平台業主…）是暫定的虛構角色，不是真實機構；待劇情定稿後更新
`viewer/brand/chapters.js` 的 `STRINGS.cards`。
