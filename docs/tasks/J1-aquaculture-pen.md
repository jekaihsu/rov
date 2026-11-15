# J1：養殖箱網場景

分支：`task/J1-aquaculture-pen`；draft PR 標題：`J1: 養殖箱網場景`。

第二章養殖場需要能巡檢網衣、拍攝破洞與夾爪回收死魚的離岸場景。
新增 `aquaculture_pen`，圓形雙管浮框、扶手、透明菱形網衣、沉子環、四角繫泊格框、
浮球、錨鏈、泥底、四條死魚與兩個破洞；沿用 ecology／marine_registry 的魚群。
水深 25 m，網深 16 m，直徑 36 m，能見度 8 m，潮流 0.3–0.8 kn。

網衣畫面與物理分離：畫面透明貼圖，伺服器以既有 Box／Cylinder 形狀和 snag_hold 處理；
僅前端依 flow_field 擺動。任務輸出穩定 ID、NED 座標，照片與實際夾爪事件作為完成證據。

預算：LOD0 ≤ 200k 三角形、預設新增貼圖 GPU 記憶體 ≤ 32 MiB，meshopt＋WebP，
低畫質合併 draw calls。原創資產 CC0，不提交 .blend，每個新資產 < 2 MB。

實作、重建、假設及圖像見 [場景文件](../design/scenes/aquaculture/README.md)。

驗收指令：

```bash
cd simulator
python -m unittest discover -s tests
node --test tests/*.mjs
ROV_CHROMIUM=/usr/bin/chromium python tools/run_browser_checks.py \
  browser_smoke observation_smoke browser_tether_smoke browser_menu_smoke
ROV_CHROMIUM=/usr/bin/chromium python tools/run_browser_checks.py browser_aquaculture_review
```

另有網衣碰撞、破洞通路、拍照朝向、完整繞圈、真實夾爪回收、魚群限域、前端擺幅與
draw-call 合併的新增測試；現有 scene consistency 測試自動納入新情境。
