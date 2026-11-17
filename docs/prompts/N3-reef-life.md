# N3：CC0 海洋生物與珊瑚（需要 Sketchfab 帳號，GPT＋Blender）

```
你負責為 ROV 模擬器「ROV Solution」（GitHub：jekaihsu/rov）把一批 CC0 的真實標本掃描做成可以放進遊戲的模型。
先從最新的 main 開新分支 task/N3-reef-life，完整讀 AGENTS.md 與 research_notes/素材/open_assets.md（第 6、7 項有每個模型的 Sketchfab 連結與授權證據）。

要做的模型（每一個都要先在 Sketchfab 原頁確認授權欄寫的是 CC0；不是 CC0 就跳過並在 PR 註明）：
- 海膽、海星、蟹、海參、貽貝、藤壺（ffishAsia-and-floraZia 帳號）
- 蝴蝶魚、神仙魚、條紋魚、隆頭魚（同帳號）
- 史密森尼的珊瑚：鹿角珊瑚 Acropora palmata、桌形珊瑚 Acropora hyacinthus、腦珊瑚、Pocillopora、Porites

做法：
1. 用我的 Sketchfab 帳號下載原始檔到電腦上的暫存資料夾（不要放進儲存庫）。
2. 在 Blender 用一支腳本 cad/build_reef_life.py 處理（可重跑）：減面、把原始細節烘焙成法線貼圖與顏色貼圖、輸出 glTF。
   - 三角形上限：小型生物（海膽、海星、蟹、貝類）近看 ≤ 1500、遠看 ≤ 300；魚 ≤ 2500／≤ 700，鼻尖朝 +Z、背朝上、公尺為單位、真實體長；珊瑚 ≤ 4000／≤ 800。
   - 貼圖 ≤ 512 px，WebP；每個 GLB ≤ 400 KB。
   - 珊瑚是乾燥標本的白骨色，要重新上成活珊瑚的顏色（參考公開的水下珊瑚資料描述，不得用任何照片當貼圖）。
3. 輸出到 simulator/viewer/models/reef/<名稱>.glb 與 <名稱>_lo.glb。
4. 每個模型寫進 simulator/viewer/models/CREDITS.md：原始頁網址、作者、授權（CC0）、授權證據網址、做了哪些修改。
5. 在 docs/design/reef-life/ 放每個模型的棚拍渲染（1600×900 JPEG，≤ 300 KB）與一份繁體中文 README（三角形數、檔案大小、授權）。
6. 不要改遊戲程式（接進遊戲由我們處理）。開 draft PR，完成後轉為 ready for review。
```
