# J1 離岸養殖箱網

基底 `main@8fd466c`。`aquaculture_pen` 是第二章場景入口，不改職涯解鎖／經濟。
一口直徑 36 m、網深 16 m 的圓形 HDPE 箱網；水深 25 m、能見度 8 m、表／中／底流
0.8／0.5／0.3 kn、泥底、coastal 水色。尺寸、魚的反應、勾掛保持力皆為訓練假設，非現場量測。

## 資料與碰撞

`qysim/aquaculture.py` 是位置唯一定義：雙管浮框、扶手柱、沉子環、四角格框、浮球、
斜向錨鏈與錨塊。網衣為 48 邊形薄 Box 面板，破洞分割面板並真正留空；底網為薄條帶。
每個面板和繫泊纜設 `snag_hold`，沿用既有 ROV／臍帶碰撞與勾纏模型。
前端 `aquaculture.js` 從相同障礙物建立六個材質批次，無逐條網線幾何。
單張雙面網衣，透明 WebP 菱形網目加 alpha test（不畫碰撞盒的前後雙層）；附著顏色依深度變化，上部偏綠。
`flow_field.js` 的局部流速驅動頂點擺動，最大水平位移 < 0.05 m，伺服器物理不動。
錨鏈的低面數交錯鏈環位於膠囊碰撞包絡內。

網目中的細小空隙不允許載具／纜線穿過，這是規格要求的低解析網衣碰撞；兩個大破洞才是
實際通路。底網邊緣採內接階梯近似，魚群限於半徑 14 m、深度 3–13 m。

`world.scenario.aquaculture` 與 `models/aquaculture/mission.json` 提供兩個破洞與四條死魚的
穩定 ID／NED 座標。活的工作物件位置與所有權沿用 `state.operations.objects`。
三個目標：半徑 19.2–22.5 m、深度 3–14 m 的 24 方位覆蓋；距破洞 0.6–4 m、
朝向且無實體遮擋的拍照；實際夾住死魚並提到深度 15.3 m 以上。需選現有配機械臂的載具。
網衣未加入推進器吸入／撕裂模型。繫泊檢查點可由障礙物 ID 使用，本輪未加第四個評分目標。

## 魚群

先檢查並沿用 `marine_registry.js` 的原創低面數紡錘魚形與 ecology 伺服器魚群，
無外部素材。八群、每群 48 尾，繞圈並避開載具與開啟的燈光；前端只減少實例數，
低／中／高畫質為 96／232／384 尾，魚體放大為養殖魚尺度。
四條灰白死魚使用原有機械臂負載、抓取、釋放和底面接觸，非靜態碰撞障礙物。

## 重建

```bash
python -m pip install -r simulator/requirements.txt pillow
blender -b --python cad/build_aquaculture_pen.py
python simulator/tools/build_menu_previews.py
node simulator/tools/aquaculture_asset_report.mjs
ROV_CHROMIUM=/usr/bin/chromium python simulator/tools/run_browser_checks.py \
  browser_aquaculture_review browser_aquaculture_onboard
```

Blender 固定 seed=71，輸出原始 GLB 到忽略的 `simulator/output`，並呼叫固定版本
`@gltf-transform/cli@4.5.1` 產生 meshopt＋WebP GLB。不保存 `.blend`。
原創素材 CC0；工具 MIT／BSD。GLB 為可攜檢視用簡化資產（圓柱錨鏈、未含動態魚），
執行時依碰撞原語繪製，避免兩份靜態場景位置漂移。

## 預算

見 [資產報告](asset-report.json) 與 [渲染報告](render-report.json)。離線量測包含完整箱網、
錨鏈、所有魚的實例數；渲染報告另外包含載具、海床、水面與共用環境。
`residentTrianglesIncludingHidden` 是快取的所有 LOD／隱藏物件，不能當作當幀三角形；
`visibleTriangles` 是可見物件，視角條目的 calls／triangles 累加全部渲染 pass。

| 畫質 | 箱網＋魚三角形 | 結構 draw calls | 魚 draw calls |
|---|---:|---:|---:|
| 低 | 86,228 | 6 | 12 |
| 中 | 102,684 | 6 | 12 |
| 高／LOD0 | 121,076 | 6 | 12 |

固定總覽實際渲染（含共用環境／載具與後製 pass）：低 95,843 三角形／35 calls，
中 114,355／43，高 134,795／43；完整可見場景亦低於 200k。

新增貼圖只有 256² RGBA 網衣，含完整 mipmap 約 0.333 MiB。
連同 `seabed.js` 四張共用 256² 海床貼圖保守計算為 1.667 MiB，低於 32 MiB。
渲染報告的 texture 欄只列材質直接持有的貼圖，不含 shader closure 裡的共用海床貼圖；
後製 framebuffer 與共用載具資產不算本次場景貼圖預算。
`pen.glb` 約 111 KiB、`net.webp` 約 21 KiB、任務資料 < 1 KiB；精確 bytes 見 JSON。
新增檔案均 < 2 MB。提交壓縮 GLB／WebP／任務資料是為離線部署與可攜檢視，
提交選單資料是為連線前可選場景，提交 JPEG／報告是本任務要求的審查證據。

## 圖片與限制

這是新增場景，main 無相同場景可做前後比較。以下均在模擬器內產生，非 Blender render：

- [真實模式機載位置](onboard-real.jpg)
- [輔助模式第三人稱總覽](third-assisted.jpg)
- [網衣近距離](net-close-real.jpg)
- [死魚與下層破洞](mort-hole-real.jpg)

總覽沿用 scene review 自由機位及輔助遠霧；三張真實視角沿用 underwater shots 的單幀 replay
方法，把機體與原有燈具放到指定檢查位置（燈光第 2 檔），經真正的機載相機／光學／後製截圖，
保持 8 m 能見度。這些是固定審查姿態，並非實際飛行軌跡；沒有增加場景燈或改動物理。
`browser_aquaculture_review` 先產出總覽／效能，再以 `browser_aquaculture_onboard` 更新三張機載圖。
位置與設定見 `onboard-report.json`。渲染時間是共享 CPU／SwiftShader 數值，非實機 GPU FPS。

## 依據

已讀 AGENTS、場景 README、G7 `cad/build_wreck_chenjiao.py` 及自有量測目錄（目前只有合成資料）。
指定兩份文件未在 main 工作樹：遊戲方案讀自 `d21092b:docs/design/game-plan.md`；
養殖 SOP §2.3 讀自 `d9390fb:research_notes/遊戲設計/real_rov_jobs_missions.md`。
場景為圓形 HDPE 養殖設施的通用訓練近似，沒有宣稱符合特定場址或設施規範。

## 本機驗證

- `cd simulator && python -m unittest discover -s tests`：455 項，980.155 s，OK。
  套件執行期間追加的真實夾爪測試另以完整 aquaculture 測試組 5/5 驗證（見下）。
- `browser_aquaculture_review browser_aquaculture_onboard`：2/2 通過，125.9／85.6 s，無頁面錯誤。

- `node --test simulator/tests/*.mjs`：158/158 通過。
- `cd simulator && python -m unittest discover -s tests -p test_scene_consistency.py`：18/18 通過。
- `cd simulator && python -m unittest discover -s tests -p test_aquaculture.py`：5/5 通過，含真正夾爪抓取／提離／釋放。
- 指定四項瀏覽器：4/4 通過（browser_smoke 133.9 s、observation_smoke 22.3 s、
  browser_tether_smoke 20.1 s、browser_menu_smoke 284.1 s）。
- `python simulator/tools/check_changed_js.py origin/main` 與 `git diff --check` 通過。
