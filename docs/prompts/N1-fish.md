# N1：寫實魚模型（GPT＋Blender）

> 整段貼給 GPT（能寫 Blender Python 的那個）。完成後開 **draft PR**，分支 `task/N1-fish-models`。

## 背景

ROV Solution 是寫實的水下遙控載具（ROV）模擬遊戲（儲存庫 `jekaihsu/rov`，先讀 `AGENTS.md`）。
遊戲裡的魚目前由程式產生（`simulator/viewer/fish_life.js`），外形與游動已經對了，但 **1–2 m 內看得出多邊形折角、
身上沒有鱗片與花紋**。擁有者的評語是「鱼好不真实」。這個任務只做**模型與貼圖**；接進遊戲的程式由我們這邊處理。

## 要做的魚（6 種）

| id | 對象 | 真實體長 | 外觀重點 |
|---|---|---|---|
| `salmon` | 養殖大西洋鮭 | 0.6 m | 銀色側面、深藍灰背、背上與鰓蓋有黑色小斑點、脂鰭 |
| `saithe` | 綠青鱈類 | 0.45 m | 橄欖深背、灰銀側面、明顯的淺色側線、兩個背鰭 |
| `fusilier` | 梅鯛類 | 0.25 m | 藍背、上側一條黃色縱帶、藍銀側面、黃色深叉尾 |
| `damselfish` | 雀鯛類 | 0.09 m | 電光藍身體、黃色腹部與尾 |
| `butterflyfish` | 蝴蝶魚類 | 0.13 m | 黃色、白臉、黑色過眼帶、身體後段暗斑，側扁高身 |
| `surgeonfish` | 刺尾鯛類 | 0.20 m | 深藍灰、尾柄上黃色斑塊，側扁 |

只做真實物種的一般外觀，不要卡通化、不要誇張的大眼睛、不要擬人。

## 規格（一定要照）

- **座標**：公尺為單位、真實體長；**鼻尖朝 +Z**、背朝 +Y；原點在身體長度方向的中點、高度中線上。
- **細節層級**（每種三個，同一個 GLB 內三個 mesh，名稱 `<id>_lod0`／`_lod1`／`_lod2`）：
  lod0 ≤ 2500 三角形（近看 0.3–2 m）、lod1 ≤ 800、lod2 ≤ 250。輪廓要平滑，**近看不能有折角**；
  鰭要薄（單片＋雙面，或極薄的雙層），尾鰭要有真實的分叉形狀。
- **貼圖**：每種一張 base color（≤ 512×256，sRGB）與一張 ORM（R=AO、G=roughness、B=metalness）。
  鱗片用細緻的紋理與 roughness 變化表現，**不要**把高光或環境光畫進 base color。
  鮭魚、青鱈側面要有銀色鏡面感（metalness 約 0.4–0.6、roughness 約 0.3），礁魚幾乎不反光。
- **頂點屬性**：保留一組 UV；另外把「沿身體長度 0（鼻）→1（尾端）」寫進第二組 UV 的 x（`uv1.x`），
  游動著色器會用它決定擺尾幅度。
- **檔案**：`simulator/viewer/models/fish/<id>.glb`，每個 ≤ 300 KB（含貼圖；貼圖可用 WebP 或 JPEG）。
- **可重現**：所有模型用一支 Blender Python 腳本 `cad/build_fish_models.py` 產生（參考 `cad/build_deck_crew.py`、
  `cad/build_support_vessel.py` 的寫法），在 Blender 4.x 以 `blender -b -P cad/build_fish_models.py` 執行即可重建全部 GLB。
  貼圖若是程式生成，也放在同一支腳本裡。
- **授權**：全部原創，或只用 CC0 素材（在 `simulator/viewer/models/CREDITS.md` 寫明來源與授權）。
  **不得**使用任何照片當貼圖（包括網路照片），**不得**提交參考照片。

## 交付時附上

1. 每種魚的棚拍渲染：側面、正上方、3/4 前方，各一張 1600×900 JPEG（≤ 300 KB），放在 `docs/design/fish-models/`，
   加一份繁體中文 `README.md`：三角形數、貼圖大小、檔案大小、參考了哪些公開資料（文字描述即可）。
2. 一張六種魚並排、同比例的總覽圖。
3. PR 描述：做了什麼、怎麼重建、未完成或有疑慮的地方。

## 不要做

- 不要改 `simulator/viewer/fish_life.js` 或任何遊戲程式（接線由我們做）。
- 不要加 npm 套件或打包工具。
- 不要用廠商名稱或商標。
