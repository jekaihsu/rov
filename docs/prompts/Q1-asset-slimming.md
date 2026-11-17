# Q1：素材瘦身與載入速度（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。simulator/viewer/models/ 目前 36 MB，最大的 GLB：korean_castle 5.5 MB、falcon 4.5 MB、rov 與 observation_rov 各 3.2 MB、workboat_high 1.7 MB。目標：首次進入潛水的下載量與載入時間減半，畫面不變差。
1. 寫 simulator/tools/asset_budget.py：列出每個 GLB 的檔案大小、三角形數、貼圖數與解析度、實際 GPU 記憶體估計，以及哪些場景會載入；可 --check 對照 docs/design/asset-budget.json 的上限（新增一個 node 或 python 測試呼叫它）。
2. 所有 GLB 套用 meshopt 幾何壓縮（viewer 已 vendor meshopt_decoder，見 simulator/viewer/glb.js）；貼圖改 WebP 或 KTX2（若加 Basis 轉碼器，照 vendor_manifest.py 規則 vendor 並說明授權），以 npx @gltf-transform/cli 或可重跑的腳本處理，腳本放 simulator/tools/。
3. 缺 LOD 的大模型補 LOD（falcon、bluerov2_heavy、workboat、worker），並確認 viewer 依距離／畫質切換。
4. 刪除執行時沒有被載入的檔案（先用 asset_budget 證明沒人用）；同時修好 vendor_manifest.py --check（Sky.js、Water.js 已無人 import）。
5. 量測：browser_gpu_bench 前後、首次載入時間（冷快取）各畫質；前後截圖（同鏡位，近看 1 m 與遠看）證明畫面沒有變差。
瀏覽器檢查：browser_smoke browser_menu_smoke browser_vehicle_assets_smoke browser_gpu_bench observation_smoke。

共同規則：
- 先完整讀 AGENTS.md（有約束力，特別是第 5、6、8 條與「X1 專屬參數目前都是暫定值」）、docs/prompts/README.md 最後的「所有場景的共同規則」。
- 不得改動 SDK 語意與協定既有欄位；任何參數都要標明來源等級（measured／published／estimated）與出處，不得把其他機型或廠商宣稱的數字當成 X1 的事實。
- 新素材只接受 MIT／BSD／Apache／zlib／CC0／公有領域，記入 simulator/viewer/models/CREDITS.md；不得新增廠商名稱、商標或其設計外觀。
- 本機測試必跑並把指令與結果貼進 PR：cd simulator && python -m unittest discover -s tests；node --test simulator/tests/*.mjs；python ../tools/test_check_matrix.py；以及任務列出的瀏覽器檢查（python tools/run_browser_checks.py ...）。
- 從最新 main 開分支 task/<編號>-<短名>，開 draft PR，完成後轉 ready for review。
```
