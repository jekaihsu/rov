# X1 ROV 操控訓練模擬器（qysim）

給同事練習操控 X1 等級 ROV 的模擬器：6 推進器全向物理、**碰撞**、**臍帶纜物理**（拖曳、纏繞、張力、斷纜）、**分層洋流（kn）**、**練習情境與隨機模式**與評分；
並附一套**與 QYSea OpenSDK 介面相同的模擬 SDK**，讓既有的 `sdk_tester`、`rov_gamepad`、P240/P250/P260 程式不改一行就能在模擬器上跑。

```
USB 手把 / 鍵盤 ──▶ 3D 畫面（瀏覽器）──WebSocket──┐
                                               ├──▶ qysim 模擬引擎（物理 100 Hz）
既有 Python 程式 ──▶ 模擬 qysea SDK ──TCP────────┘
```

## 快速開始（Windows）

1. 安裝 Python 3.10 以上（勾選 Add Python to PATH）。
2. 雙擊 `START_SIM.bat`（第一次會自動安裝 `numpy`、`websockets`、`opencv-python`）。
   指定情境：`START_SIM.bat jacket_inspection`。
3. 瀏覽器開 <http://127.0.0.1:8080/>，插上 USB 手把（Xbox/PS 相容）即可。

命令列：

```bash
cd simulator
pip install -r requirements.txt
python -m qysim.server --scenario tether_untangle     # 或 --scenario random --seed 42
```

## 操控

遙控器語意與真機一致：兩支搖桿、兩個波輪為 PWM 1000–2000（1500 中位），**操控手模式**（ROV_USA / JPN / CHN、UAV_*）決定每支搖桿控制什麼，對照表同 SDK 文件。

- **開機時電機是上鎖的**，先解鎖（手把 Y / 鍵盤 Space）。
- 左撥鈕 **A / S / C**：A 姿態平穩（不能橫滾）、S 運動模式（全向、可 360° 翻滾）、C 在模擬器中同 A。
- 定深（X / H）：鎖住深度，上下波輪改為調整設定深度。
- SDK 取得遠端控制權時（`set_remote_control_status("ON")`），手把輸入會被忽略，畫面顯示 SDK REMOTE。

### USB 手把對照（Xbox 配置；PS 手把按鍵位置相同）

| 手把 | Q-iRC 通道 / 功能 |
|---|---|
| 左搖桿 | `left_ud` / `left_lr`（ROV_USA：俯仰 / 轉向） |
| 右搖桿 | `right_ud` / `right_lr`（ROV_USA：前後 / 橫滾） |
| LT / RT | 左波輪 `left_wave`（ROV_USA：升降） |
| LB / RB | 右波輪 `right_wave`（ROV_USA：橫移） |
| A（按住） | 拍照 `photo` |
| B（按住） | 錄影 `record` |
| X | 定深開關 `keep_depth` |
| Y | 鎖定 / 解鎖 `rc_lock` |
| Back / View | 切換 A / S / C 模式 |
| Start / Menu | LED 亮度 |

瀏覽器要先在頁面上按一下手把任一鍵才會偵測到手把（瀏覽器安全限制）。
沒有手把時可用鍵盤（按鍵說明在左側面板下方），或直接拖動畫面上的搖桿。

### 下水動畫與操作員畫面

- 每次載入情境會先播一段下水動畫：工作船船尾、甲板人員把 ROV 抱起拋出、另一人放纜，入水後滑行到起始點。播放時模擬暫停，按「跳過」或 Esc 可略過。
- 右上角的操作員子畫面顯示坐在控制台前的操作員，手上的手把會跟著實際搖桿輸入動。
- 兩者都可以在左側「顯示」區關掉，或網址加 `?nointro`、`?nopip`。

## 練習情境

| key | 名稱 | 練什麼 |
|---|---|---|
| `open_water` | 開放水域熟悉 | 基本操控、A/S 模式、定深、依序過檢查點 |
| `jacket_inspection` | 導管架樁腿巡檢 | 四腳導管架＋斜撐、分層洋流；在 0.8–2.5 m 距離面向陽極塊停留；避免纜線卡在斜撐 |
| `monopile_current` | 單樁抗流懸停 | 2.5 kn 強流中在樁前懸停 30 秒不碰樁 |
| `tether_untangle` | 纜線纏繞脫困 | 開局纜線已繞樁一圈多；判斷方向反繞解開 |
| `hull_inspection` | 船殼底部檢查 | 從船底下穿過；纜線會卡在船底邊緣 |
| `wreck_survey` | 沉船調查 | 能見度 4 m、揚沙、桅桿 |
| `random` | 隨機模式 | 隨機結構物、洋流、能見度、纜長；`--seed` 可重現同一題 |

評分：完成目標得分，碰撞扣分（輕觸 5／重撞 15／嚴重 30），纜線張力過高扣 10；**斷纜或嚴重碰撞 3 次即任務失敗**。
嚴重碰撞會打壞撞擊點附近的推進器（推力剩 55%），`ego_self_test()` 會回報該電機異常。

## 物理模型摘要

| 項目 | 模型 |
|---|---|
| ROV 本體 | 6 自由度剛體，30 kg，推進器佈局取自 X1 3D 模型；極速對齊規格（前進 4.5 kn、橫移 2.5 kn、垂直 1.5 kn），總前進推力 30 kgf；微正浮力、CB 高於 CG 自動扶正 |
| 碰撞 | 以 10 顆球包覆機身，對圓柱／方塊／牆面／海床做彈簧-阻尼接觸＋摩擦；依法向撞擊速度分 touch / hard / severe |
| 臍帶纜 | 40 節集中質量纜：只受拉的彈簧、法向／切向水阻（逐節洋流）、近中性浮力、與結構物接觸摩擦（會掛住、纏繞），張力回饋到 ROV 尾端纜線接頭；自動放纜、最大 350 m、300 kgf 斷裂 |
| 洋流 | 表層／中層／底層三層（kn、流向）、深度內插、海床邊界層、Ornstein–Uhlenbeck 陣流 |
| 感測 | 前方測距、下方高度（射線）、DVL 速度、深度、姿態、電量、水溫 |
| 自動駕駛 | DR 慣導、H_NAVI（到經緯度，定深／定高）、V_NAVI（牆面／橋墩／Tank 立面掃描 8 種航線）、VCCM 垂直巡航（含 A 檔、解鎖等啟動條件） |

## 用模擬 SDK 跑既有程式

見 [`sdk_mock/README.md`](sdk_mock/README.md)。原則：把 `simulator/sdk_mock` 放到 `sys.path` 最前面（或設 `PYTHONPATH`），
程式裡的 `from qysea.sdk.manage.QY_Rov_Manage import ...` 就會連到模擬器；拿掉就回到真 SDK。

> 真的 QYSea SDK（Windows `.pyd`＋授權）屬 QYSEA 授權軟體，**不放進本 repo**。

### 用團隊的 GUI 測試程式

`qysea_sdk_gui_tester.py`（及同目錄程式）使用的 132 個 SDK 方法模擬 SDK 都有。先啟動模擬器，再在另一個視窗：

```bat
set PYTHONPATH=C:\路徑\rov\simulator\sdk_mock
python qysea_sdk_gui_tester.py
```

測試程式連線、解鎖、導航等操作會直接反映在模擬器的 3D 畫面上。

## 回放與展示頁

- `python tools/record_demo.py`：用真正的模擬器跑三段示範飛行（導管架碰撞、纜線纏繞脫困、強流懸停），存成 `viewer/demo_recording.json`。
- 不開伺服器也能看：`viewer/index.html?replay=demo_recording.json`（需要用任何靜態網頁伺服器開，例如 `python -m http.server`）。
- `python tools/build_showcase.py` 產生 `docs/showcase/`（GitHub Pages 用）。在 GitHub repo 的 **Settings → Pages** 選 *Deploy from a branch*，分支選這個分支、資料夾選 `/docs`，網址就是 `https://<帳號>.github.io/rov/`。
- 3D 模型來源與授權見 [`viewer/models/CREDITS.md`](viewer/models/CREDITS.md)（全部 CC0 / MIT）。

## 協定與程式結構

- 通訊協定：[`PROTOCOL.md`](PROTOCOL.md)
- `qysim/physics.py` 剛體與推進器　`controller.py` 飛控　`rc.py` 遙控器與操控手模式　`world.py` 結構物／碰撞／洋流
  `tether.py` 臍帶纜　`navigation.py` 自動駕駛　`scenarios.py` 情境與評分　`engine.py` 整合＋SDK 語意　`server.py` 服務
- `viewer/app.js` 駕駛台　`deploy_intro.js` 下水動畫　`pilot_pip.js` 操作員子畫面　`humanoid.js` 人物骨架與 IK　`glb.js` 模型載入
- 測試：`python -m unittest discover -s tests`
