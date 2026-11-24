# 序章港內淺水區（R1b）

擁有者評 R1 序章「畫面太無聊」：訓練池白牆、空水、池底 A／B／C 板，與開場（導管架、魚群、光束）落差太大。
本版把**導演序章**改到港內避風淺水區；`tutorial_pool` 仍留給訓練模式與課程（`course_b01`、`p1_pool_checkout`）。

## 場景（`qysim/harbor_shallows.py`）

| 項目 | 值（暫定，非實測） |
|---|---|
| 水深 | 6 m（4–8 m 訓練帶） |
| 能見度 | 7 m，水色 `harbour` |
| 海況 | 晴天上午、平潮、0.25 kn 往北（推向 2 號樁） |
| 起點 | `(0,0,2)` 朝北；纜盤 `(−6,0,0)` 在機體後方，拍照時纜線從鏡頭後方／上方延伸 |
| 地標 | 三根港樁（2 號在中線）、蟹籠、浮碼頭浮筒／錨鏈／卸扣、輪胎、斷纜、岸壁附著 |
| 魚群 | 三群固定在樁間（`fish_schools`） |

小意外靠情境資料：鬆桿時北向平潮把機體推向 2 號樁；定深限制垂向漂移，但仍需微推修回水平位置。單元測試見 `tests/test_harbor_shallows.py`。

## 節拍

`black → establish（小艇尾板入水鏡頭 5 s）→ unlock → approach（2 號樁）→ descend（蟹籠）→ coast／hold／trim → A 樁牌 → B 蟹籠 → C 卸扣 → report → licence → harbor`

閒置提醒上限 15 s。演出沿用 `beat_stage.js`／`cutscene_look.js`；過場開光束，接手後還原擬真設定。

## 聯絡表

本目錄 `NN-<beat>.jpg` 與 `contact-sheet.jpg` 由 `browser_prologue_smoke.py` 以 1600×900 拍攝。請與 `docs/design/prologue-r1/contact-sheet.jpg` 並排比較。

## 開場標準對照

見 PR 描述表格。
