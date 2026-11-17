# Q5：載具模型品質與一致性（GPT＋Blender）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。目標是三台載具（YX Model R／O／V，內部 key x1／bluerov2_heavy／falcon）的 3D 模型在近看 0.5–2 m 時更真實、更一致，並且更輕。
1. 讀 cad/VEHICLE_MODELS.md 與 cad/ 的建模腳本，了解現有模型怎麼產生（不得重現任何廠商標誌、字樣或可辨識的外觀商標；遊戲裡是 YX 原創機型）。
2. 統一材質：PBR（金屬、塑膠、壓克力罩、浮力材、螺旋槳）使用一致的粗糙度與顏色規則；可用 Poly Haven／ambientCG 的 CC0 材質掃描作為細節，記入 CREDITS.md。
3. 細節：螺絲、接頭、纜線入口、推進器護罩、相機罩反光、浮力材表面的細孔紋理；推進器葉片要有正確葉數與螺距方向（與 simulator/qysim/vehicles.py 的推進器方向一致）。
4. 每台三級 LOD（近 ≤ 40k、中 ≤ 12k、遠 ≤ 3k 三角形），每個 GLB ≤ 1.5 MB（meshopt＋WebP 或 KTX2）；推進器、燈、相機、夾爪保留可動節點名稱（與 viewer 現有節點名一致，先列出 viewer 依賴的節點名）。
5. 交付：每台棚拍與水下（遊戲內）前後對照截圖，放 docs/design/vehicle-models/；PR 描述列三角形數、檔案大小。腳本可重跑（blender -b -P cad/<腳本>.py）。
瀏覽器檢查：browser_vehicle_assets_smoke browser_smoke browser_menu_smoke browser_gpu_bench。

共同規則：
- 先完整讀 AGENTS.md（有約束力，特別是第 5、6、8 條與「X1 專屬參數目前都是暫定值」）、docs/prompts/README.md 最後的「所有場景的共同規則」。
- 不得改動 SDK 語意與協定既有欄位；任何參數都要標明來源等級（measured／published／estimated）與出處，不得把其他機型或廠商宣稱的數字當成 X1 的事實。
- 新素材只接受 MIT／BSD／Apache／zlib／CC0／公有領域，記入 simulator/viewer/models/CREDITS.md；不得新增廠商名稱、商標或其設計外觀。
- 本機測試必跑並把指令與結果貼進 PR：cd simulator && python -m unittest discover -s tests；node --test simulator/tests/*.mjs；python ../tools/test_check_matrix.py；以及任務列出的瀏覽器檢查（python tools/run_browser_checks.py ...）。
- 從最新 main 開分支 task/<編號>-<短名>，開 draft PR，完成後轉 ready for review。
```
