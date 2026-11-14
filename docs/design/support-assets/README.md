# 甲板支援資產：工作船、甲板人員、操作台（前後對照）

所有圖片 1600×900。資產圖用 `simulator/tools/render_support_assets.py`（頁面 `simulator/tools/asset_review.html`）以
**相同機位與燈光**分別對舊版（main 的 `simulator/viewer`）與新版算圖；遊戲內圖是實際伺服器上的下水動畫
（`--intro`，於動畫時間 0.6 s／2.6 s／5.4 s／8.0 s 擷取，軟體繪圖下時間點會有一兩幀誤差）。

```bash
cd simulator
python tools/render_support_assets.py OUT                       # 新版資產圖
python tools/render_support_assets.py OUT --viewer OLD/viewer --prefix before
python tools/render_support_assets.py OUT --intro               # 遊戲內下水動畫
python tools/build_support_assets.py             # 重新產生 workboat.glb / worker.glb（需 bpy 與 npx）
```

| 項目 | 前 | 後 |
|---|---|---|
| 工作船 三分之四 | `before-boat-quarter.png` | `after-boat-quarter.png` |
| 工作船 側面（不含水面，看得到水線以下） | `before-boat-side.png` | `after-boat-side.png` |
| 工作船 後甲板近景 | `before-boat-deck.png` | `after-boat-deck.png` |
| 工作船 水下仰視（ROV 下水／回收時看到的船底） | `before-boat-below.png` | `after-boat-below.png` |
| 甲板人員 三分之四／側面／近景 | `before-crew-*.png` | `after-crew-*.png` |
| 操作員畫中畫 肩後／正面 | `before-station-*.png` | `after-station-*.png` |
| 遊戲內下水動畫 | `before-intro-*.png` | `after-intro-*.png` |

## 資產數據

| 檔案 | 三角形 | 貼圖 | 檔案大小 |
|---|---|---|---|
| `workboat.glb`（原 772 三角形的 CC0 漁船） | 49,437（預算 120k，未做 LOD） | 船殼 2048×1024 ×3（基礎色／法線／粗糙度金屬度）、艉板 1024×512 ×3、甲板止滑漆／舊漆面／拉絲金屬 1024² 各 ×3、帆布 512² ×3、船籍字 1024×256、甲板螢幕 512×320；WebP | 1.61 MB（meshopt） |
| `worker.glb`（原 8.4k 三角形） | 11,936（預算 40k） | 工作服布紋 512² ×3、靴與安全帽 256² ×3；WebP | 0.79 MB（含 12 段原動畫） |
| 操作台 `pilot_station.js` | 程式即時產生（three.js 幾何） | 兩個 canvas 螢幕（遙測、聲納） | — |

未壓縮時船的貼圖約佔 95 MB 顯示記憶體（WebP 在 GPU 上仍是 RGBA8）。專案目前沒有 KTX2 編碼工具，這是之後該補的。

## 改善了什麼

- **工作船**：原創的 11.6 m 鋁製測量／支援工作船，比例照實際尺寸（船寬 3.9 m、甲板高出水線 0.45 m、艉舷牆 0.57 m）。
  硬舭船殼與外飄船艏、艏樓駕駛艙（斜前窗、門、雨刷、救生筏、救生圈、爬梯）、桅杆（雷達罩、VHF 天線、GPS、桅燈、
  甲板工作燈）、紅綠舷燈與艉燈、橡膠護舷條、欄杆、雙柱繫纜樁、錨與錨機、碰墊、掛在舷側的舊輪胎、舷梯。
  後甲板有艉 A 架（液壓缸、滑輪組、吊鉤）、電動纜線絞車（纜盤是獨立節點，下水時會轉動，纜線由盤頂引出）、
  不鏽鋼控制櫃與接到絞車的電纜、遮陽棚下的駕駛桌（加固控制箱、螢幕、手持控制器、折凳）、ROV 運輸箱、艙口蓋。
  水線以下：防污漆、水線污垢與藻膜、黑色水線帶、艉鰭、雙軸與 P 型支架、四葉銅槳、舵、鋅塊、冷卻水進水格柵、
  換能器整流罩、噴濺條。船殼貼圖有肋骨間的板面凹陷、焊道、排水口與鏽水痕、靠球擦痕、吃水標。
- **甲板人員**：沿用原骨架、權重與 12 段動畫（`humanoid.js` 的骨名與 IK 不變）。頭縮到 90%，
  連身工作服（上下身仍可分別上色）、袖口與小腿反光條、雨靴、工作手套，背心與安全帽改成模型內的獨立蒙皮網格
  （`LifeVest`、`HardHat`），隨骨架彎曲而不再是貼在身上的圓筒；駕駛不戴時由程式隱藏。
- **操作台**：桌面圓角與桌下抽屜櫃、主螢幕（照舊鏡射主畫面）＋左右各一台遙測與聲納螢幕（會更新）、
  開蓋的加固控制箱（指示燈閃爍、黃色纜線）、鍵盤、滑鼠、杯子、耳機、五爪辦公椅、隔音牆板與層架。
  手把與 IK 握持不變，仍隨即時 RC 輸入動作。

## 仍然不足（如實說明）

- 全部是程式建模。近看仍是「乾淨的工業示意」而非照片級：船殼沒有真正的板材厚度與焊接細節幾何，窗戶是不透明的深色玻璃，
  駕駛艙沒有內裝，帆布是平面，纜線與繩子沒有編織細節。
- 人物仍是 Quaternius 的低面數造型：臉部沒有貼圖與細節，手掌是連指手套般的大塊，背心邊緣在腋下仍有鋸齒，
  安全帽是車削形狀而不是真實的帽殼與帽帶。沒有找到可直接下載、品質明顯更好且為 CC0 的帶骨架人物
  （Quaternius 的 Universal Base Characters 是 CC0，但需經 itch.io 下載流程，這次沒有引入）。
- 下水動畫本身仍是「人把 ROV 拋過艉板」。研究報告記載 V6 家族的手冊要求只用纜線把 ROV 放入水中、不可拋擲
  （`docs/reference/real-rov-research.md`），X1 約 30 kg 的吊放方式沒有公開文件。新船已備有 A 架與絞車，
  改成吊放或順纜放入是動畫的後續工作，不在本次範圍。
- 船只有一級 LOD，沒有碰撞代理；水下仰視時船底在這套燈光下偏暗（遊戲內由水面亮度襯托成剪影，屬合理）。
- X1 與實船尺寸、甲板配置是假設的典型小型支援船配置，不是任何實船或廠商資料。
