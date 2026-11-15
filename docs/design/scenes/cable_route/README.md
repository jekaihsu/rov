# L5 海底電纜巡線

`cable_survey`：陸棚型海水、6 m 能見度、砂泥底與潮流，觀測級巡查 300 m。
新增場景，main 無相同場景可作前後比較。尺寸、水深、潮流、10 m 懸空容許長度及
繩索保持力為訓練假設，不是場址實測、工程合格標準或載具性能宣稱。

## 同源資料與互動

`qysim/cable_route.py` 提供中心線、埋設狀態、異常、標牌與碰撞；所有座標為 NED 公尺。
`chainage_m` 為三維折線弧長，終點 300 m；`kp_km` 使用真實業界的公里單位，終點 0.300。
固定建置種子 51，任務種子改變損傷、拖痕和纏繩位置。狀態轉換、起伏與沖刷保持固定，便於教學。

埋設電纜不建立碰撞；表面溝痕為貼合海床的透明著色面。其餘電纜是半徑 0.10 m 的短膠囊。
沖刷坑使用共用海床高度格網，前端與伺服器使用相同深度；懸空下方沒有補碰撞盒。
高度計／DVL 沿用世界射線。無需新增 FieldMesh：現有高度場與 Cylinder、Box、SnagFeature
足以表示本場景；可攜 GLB 不作第二套碰撞來源。

混凝土塊使用 Box、倒角在碰撞內；標牌為無文字薄板，可替換材質。外皮損傷露出螺旋鎧裝線，
半徑仍在原膠囊內。纏繩有逐段碰撞與 `snag_hold`。岩石沿用 SnagFeature，稀疏海星與海膽
亦有碰撞；貝殼碎屑與沙紋沿用海床著色。所有結構按材質合併，不會有逐小段 draw call。

巡線以每公尺覆蓋格累積，需側偏 ≤2 m 且距纜高 0.4–4 m；不能在水面完成。
沿途拍照可先取得證據，不必等第一目標完成。異常需 0.5–4 m、面向目標且無遮擋；
四種異常逐一記錄，重複照片不重複計分。懸空兩端照片轉為沿纜長度，非兩端直線距離。
事件表在評分資料 `cable_records`，量測在 `cable_span_m`。未增設超出真機能力的畫面疊圖。

## 可重建資產

```bash
python -m pip install -r simulator/requirements.txt pillow
blender -b --python cad/build_cable_route.py
python simulator/tools/build_menu_previews.py
node simulator/tools/cable_asset_report.mjs
cd simulator
python tools/run_browser_checks.py browser_cable_onboard
```

不保存大型 blend；全為原創 CC0，無外部照片、模型或投影材質。工具壓縮採固定
`@gltf-transform/cli@4.5.1`，meshopt＋WebP。GLB 為可攜簡化參考（圓柱、方塊），
實際駕駛使用同源碰撞網格、倒角、鎧裝線與共用海床。授權見 models/CREDITS.md。

資產預算見 [asset-report.json](asset-report.json)：統計完整場景結構與高度格網，
貼圖含 mipmap、四張共用海床貼圖與五張共用結構貼圖；不含共用載具／後製 framebuffer。
最終場景 94,588 三角形（含邊界海床延伸），10 個結構 draw calls，保守貼圖預算 6 MiB。
GLB 約 0.46 MB，精確 bytes 以 JSON 報告為準。
提交壓縮 GLB、WebP、JSON 供離線部署；截圖與報告為驗收證據；均無超過 2 MB 的新資產。
既有 scene_previews.json 更新是為離線選單可選新場景，並非參考照片。

## 審查畫面

圖片全部由真實模式、機載相機、原有燈具與光學後製拍攝；不是 Blender render。
使用固定 replay 姿態，非實際飛行紀錄。燈開為第一檔，關燈與裸露段使用相同姿態。

- [埋設](buried.jpg)、[部分裸露](partial.jpg)、[完全裸露／開燈](exposed.jpg)
- [懸空](free-span.jpg)、[保護墊](protected.jpg)、[交越](crossing.jpg)、[關燈](lights-off.jpg)
- [外皮損傷](sheath_damage.jpg)、[錨拖痕](anchor_drag.jpg)、[纏繩](fouling_rope.jpg)、[超長懸空](excess_span.jpg)

**外觀驗收限制**：本次對話沒有附擁有者現場照片；專案 own/ 也只有合成量測。
因此無法完成「與指定照片並排、一眼像同一地方」的驗收，不能宣稱已達照片級或場址一致。
現有圖片供檢查真實渲染路徑、比例、區段可辨識性與燈光差異；仍須以現場照片作最後美術校對。

## 依據

完整讀取 AGENTS、場景與養殖場說明及建置腳本，並查閱 real-rov-research、ui-direction、own/README。
main 缺少指定設計文件，依既有 aquaculture README 記錄，遊戲方案讀自 `d21092b`，
工作研究 §2.5、§3、§4 讀自 `d9390fb`（同名原路徑）。沒有把歷史文件或現場照片加入資產。

## 本機驗證

- `node --test simulator/tests/*.mjs`：211/211 通過。
- `PYTHONPATH=simulator python -m unittest discover -s simulator/tests -p test_cable_route.py`：4/4 通過，
  含弧長／KP、種子、射線淨空、遠距不能完成與真實障礙遮擋下的異常／端點照片。
- `PYTHONPATH=simulator python -m unittest discover -s simulator/tests -p test_scene_consistency.py`：18/18，182.723 s（最終幾何重跑）。
- 指定瀏覽器首次合跑：observation_smoke 22.1 s、browser_tether_smoke 15.2 s、
  browser_menu_smoke 246.6 s 通過；browser_smoke 首次等待夾爪狀態逾時，再跑一次點擊關閉 PiP 逾時。
  首次伺服器在加速套件安裝完成前啟動，使用 NumPy 路徑；第二次已使用 numba，仍受 UI 等待影響。
- 最後單獨執行 `ROV_BROWSER_TIMEOUT_SCALE=3 python tools/run_browser_checks.py browser_smoke`：
  304.0 s 通過。使用專案既有慢機等待倍率，未修改測試斷言或控制行為。
- Blender 無頭重建、glTF Transform 壓縮、資產報告、`check_changed_js.py origin/main`、`git diff --check` 通過。

- `python tools/run_browser_checks.py browser_cable_onboard`：11 張真實模式機載圖，226.4 s 通過。
  實際單幀含載具／共用環境／後製為約 25–31 calls、69k–101k 三角形，見 onboard-report.json。

- `cd simulator && python -m unittest discover -s tests`：474/474，1388.047 s，OK。
  完整套件執行期間修正的幾何，另以最終一致性 18/18 與海纜專項 4/4 重驗。
- 損傷內芯補齊後，以 `ROV_CABLE_SHOTS=sheath_damage` 局部重拍：29.4 s 通過。
