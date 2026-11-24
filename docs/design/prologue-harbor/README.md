# 序章港內淺水區（R1b）

擁有者評 R1 序章「畫面太無聊」：訓練池白牆、空水、池底 A／B／C 板，與開場（導管架、魚群、光束）落差太大。
本版把**導演序章**改到港內避風淺水區；`tutorial_pool` 仍留給訓練模式與課程（`course_b01`、`p1_pool_checkout`）。

## 場景（`qysim/harbor_shallows.py`）

| 項目 | 值（暫定，非實測） |
|---|---|
| 水深 | 6 m（4–8 m 訓練帶） |
| 能見度 | 8 m，水色 `harbour` |
| 海況 | 晴天上午、平潮、0.18 kn 往北（推向 2 號樁） |
| 起點 | `(0,0,1.8)` 朝北；纜盤 `(−5,0,0)` 在機體後方，拍照時纜線從鏡頭後方／上方延伸 |
| 地標 | 三根港樁（2 號在中線）、蟹籠、浮碼頭浮筒／錨鏈／卸扣、輪胎、斷纜；岸壁改用 plain `wall`＋`dress_quay` 配件（不用 `kind=quay`，避免 20 m 背臉與 SDF 不一致） |
| 魚群 | 三群固定在樁間（`fish_schools`） |

小意外靠情境資料：鬆桿時北向平潮把機體推向 2 號樁；定深限制垂向漂移，但仍需微推修回水平位置。單元測試見 `tests/test_harbor_shallows.py`。

## 節拍

`black → establish（小艇尾板入水鏡頭 5 s）→ unlock → approach（2 號樁）→ descend（蟹籠）→ coast／hold／trim → A 樁牌 → B 蟹籠 → C 卸扣 → report → licence → harbor`

閒置提醒上限 15 s。演出沿用 `beat_stage.js`／`cutscene_look.js`；過場開光束，接手後還原擬真設定。

## 聯絡表

本目錄 `NN-<beat>.jpg` 與 `contact-sheet.jpg` 由 `browser_prologue_smoke.py` 以 1600×900、medium 畫質拍攝。請與 `docs/design/prologue-r1/contact-sheet.jpg` 並排比較。

### 自問：每一張單獨拿出來，都比舊版好看嗎？

| 節拍 | 判定 | 說明 |
|---|---|---|
| black | 持平 | 黑畫面本來就沒有場景。 |
| establish | **較好** | 黑邊＋地點字卡；尾板視角看得到水面、黃纜入水與三根附著樁。小艇甲板本體與陽光光束在 medium 仍偏淡；R5 附著合併後會更密。 |
| unlock / approach | **較好** | 正前方就是 2 號樁，不再是空水；淺水時上方可見水色／結構。 |
| descend / coast / hold / trim | **較好** | 海底有輪胎、碎石、蟹籠與樁根，鬆桿漂向樁的意外看得見。 |
| A / B / C | **較好** | 樁牌、蟹籠／箱形目標、錨鏈卸扣取代白牆 A／B／C；纜盤在後方，纜線不再橫過鏡頭中央。 |
| report / licence / harbor | 持平／沿用 | 結算卡與章節卡。 |

結論：飛行節拍整體比舊水池好看；establish 還要再磨（尤其小艇入水構圖與 R5 附著）。不要假裝已經等於開場導管架那一檔。

## 開場標準對照

見 PR 描述表格。
