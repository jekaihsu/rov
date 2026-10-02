# ROV 協作潛航模擬器（qysim）

## 0.3 開發版

- 同一房間最多 3 位駕駛，各自控制一台 ROV；房主切換共享場景與洋流。斷線後保留短暫重連席位，失聯推進上鎖。
- X1、BlueROV2 Heavy、Falcon 三種機型。Falcon 已按 Saab 官方多角度照片重建，含可動機械臂、工作物抓取及負載反作用；尚非原廠 CAD 精確複製。BlueROV2 Heavy 仍是估算外形；原廠 R3 CAD 參考沒有混入發行模型。
- 珊瑚礁、海草床、港灣場景；固定種子生成魚群、珊瑚、海星等生態，含分層／局部洋流、地形接觸及沉積物揚起。
- 航點／覆蓋路線、定高、巡檢標記、照片及姿態、WebM 錄影、JSON 任務回放。
- 操作員小視窗預設關閉，可開啟／關閉並記住選擇。機載視角隱藏機身時仍保留照明。
- 右側姿態儀以 ROV 側視圖呈現俯仰、艉視圖呈現橫滾；虛線為水平基準。俯仰正值為抬頭、橫滾正值為右舷下沉，保留帶正負號的實際角度與航向。這是本模擬器的姿態介面，不代表任何廠牌的原廠儀表。

啟動後先進入主選單：選擇機型、貼紙、場景、伺服器與房間，並在設定中選手柄、控制配置及畫質。機器與場景會即時預覽；按「開始潛航」後才連線進入遊戲。遊戲內可返回主選單調整。

主選單新增「海洋探索與工程」：1～3 人在同一海域自由接案，完成巡檢、物件回收或觀測儀部署後可繼續探索。機載相機有效拍到珊瑚、海星、海草、海藻、魚群可登錄個人圖鑑；照片與工程紀錄可永久收藏及匯出備份，桌面重開換埠號也會保留。首版工程海域為珊瑚礁、海草床與港灣；回收及部署需 Falcon。詳見 [探索與工程操作](../docs/expedition.md)。

原有三種玩法保留：自由探索不計任務倒數或扣分；協作巡檢由最多三人共享 12 分鐘，靠近觀測站低速懸停 3 秒後拍照，有巡檢物時須朝向目標；場景訓練保留各場景既有評分。房主決定共同模式，隊友的有效巡檢會同步計入進度。詳細規則見 [任務模式](../docs/mission-modes.md)。遊戲側欄提供可收起的操作提示，依目前控制配置顯示鍵位。

貼紙提供警示斜紋、潛水旗與巡檢編號。遊戲左側「表面噴漆」可選四色及 3–30 cm 半徑，啟用後點擊表面或按 F 對準中央噴漆。需距離機器 3 m 內且位於水下；可標記海床與設施，不接受魚類、珊瑚或機器。標記全房共享，最多保留 300 筆，重設場景會清除；錄製回放包含貼紙與標記。這是表面標記功能，尚未模擬漆霧擴散或附著化學。

操控修正與原始論文來源見 [ROV 動力學研究](../docs/rov-dynamics-research.md)。目前物理參數仍包含估算，尚未完成實機水槽校準。

幀率偏低時，主選單最上方「本機效能 → 畫質」可選「自動」或「流暢」。自動模式在本機偵測實際 WebGL 繪圖裝置，對整合顯示晶片、GeForce MX 入門獨顯、其他獨顯、軟體繪圖與未知裝置採不同起始比例；再以實測 FPS 動態調整。主選單與遊戲右上角可看到渲染比例。此硬體分類是保守起點，不是顯示卡跑分，資訊不會傳送到伺服器。錄影期间暫停縮放；固定畫質保持使用者設定；60 FPS 是目標而非保證。桌面版會記住畫質並將視窗限制於螢幕工作區。

啟動後可開 `/model-preview.html?model=falcon` 檢視新版 Falcon，使用正面／側面／斜前視角和關節滑桿。模型來源、重建方式與估算限制見 [模型說明](../cad/VEHICLE_MODELS.md)。

區域網路多人：以 `python -m qysim.server --host 0.0.0.0` 啟動，各電腦開啟 `http://主機IP:8080/`，填相同房間代碼後加入。桌面版也可在「伺服器位址」填 `ws://主機IP:8765`；已部署的線上主機填 `https://你的網域`，會使用 `/ws` 安全連線。允許主機防火牆通過 HTTP 8080 與 WebSocket 8765；SDK RPC 僅監聽本機。網際網路部署範本位於 `deploy/`，需設定自己的 `ROV_DOMAIN`、網域解析及主機；尚未部署公共服務。

瀏覽器會記住最後成功切換的機型；也可在網址加 `model=falcon` 指定新房間的機型。桌面版把這項偏好存於使用者設定目錄，重開程式仍會保留。重新連上原有席位時，以伺服器保留的機型與鎖定狀態為準。

Windows 桌面封裝位於 `desktop/`，Steam 上傳範本位於 `desktop/steam/`；這是測試建置，未上架 Steam。實機 USB 遙控器、遠端公网連線及實際 GPU 的 1080p/30 FPS 仍需驗收。物理使用 0.01 秒固定步長；四台複雜纜線場景目前可能慢於即時，不能把步長視為已達成 100 Hz 效能。水動力、抓取與生態行為是近似模擬，並非實機校準資料。

給同事練習操控 X1 等級 ROV 的模擬器：6 推進器全向物理、**碰撞**、**臍帶纜物理**（拖曳、纏繞、張力、斷纜）、**分層洋流（kn）**、**練習情境與隨機模式**與評分；
並附一套**與 QYSea OpenSDK 介面相同的模擬 SDK**，讓既有的 `sdk_tester`、`rov_gamepad`、P240/P250/P260 程式不改一行就能在模擬器上跑。

```
USB 手把 / 鍵盤 ──▶ 3D 畫面（瀏覽器）──WebSocket──┐
                                               ├──▶ qysim 模擬引擎（0.01 s 固定步長）
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
- LED（Start / L）：0 → 1 → 2 檔。自然光隨深度衰減（約每 10 m 剩 1/e），20 m 以下沒開燈只看得到輪廓；開燈後看得到光錐與被照亮的結構表面。
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

#### X1 原廠遙控器與輸入檢查

原廠 Q-iRC 可透過 USB 轉接程式操作搖桿、波輪、燈光、模式及主要功能鍵，**不需要水下機器或網路線**。
目前驗證的裝置是 Q-iRC / QY665，遙控器韌體 `RC_V001R003S001`。其他版本需另行驗證。
在另一台電腦使用時，需先安裝 Android Platform Tools，將 `adb` 所在目錄加入 PATH，或以 `--adb` 指定執行檔；本機下載的工具不包含在 GitHub 原始碼中。

1. USB-C 接電腦，在原廠 App 的 Sys → Connection mode 選 **Local Data Transfer**，並允許 USB 偵錯（若有詢問）。
2. 關閉舊模擬器，雙擊 `START_QIRC_SIM.bat`。程式使用本機 `.runtime/android/platform-tools/adb.exe`，也可使用 PATH 中的 `adb`。
3. 開啟或重新整理 <http://127.0.0.1:8080/?nointro>，等待左側顯示 **Q-iRC USB 已連接**，按遙控器鎖定鍵或鍵盤空白鍵解鎖。
4. 使用下表的遙控器功能；網頁按鈕及鍵盤仍可使用。
5. 在模擬器視窗按 Ctrl+C 結束，程式會嘗試重新開啟遙控器原廠 App。

| Q-iRC 原廠控制 | 模擬器功能 |
|---|---|
| 左右搖桿、左右波輪 | 六個操控通道，依目前 ROV 操控手模式對應 |
| 左三段開關 T1 | A / S / C 模式 |
| 右三段開關 T2 | 燈光關閉 / 小燈 / 全亮，畫面顯示 LED 0 / 1 / 2 |
| 鎖定鍵 H | 每按一次切換鎖定 / 解鎖 |
| 定深鍵 A | 每按一次切換定深 |
| 拍照鍵 D | 按一下新增模擬照片 |
| 錄影鍵 C | 按一下開始、再按一下停止模擬錄影 |

三段開關在連線及切換位置時套用；網頁調整後，再撥動實體開關即可接手。
按住按鍵不會重複觸發；連線時已按住的鍵須先放開再按。其餘自訂鍵目前未對應功能。

USB 轉接會暫停原廠 FIFISH / RCTool，避免同時讀取串列埠；使用期間請保持它們關閉。
斷線或超過 0.6 秒未收到有效資料時，模擬器會回中並上鎖；重新接通後須再解鎖。
瀏覽器搖桿檢查頁不會列出這種專用 USB 輸入，請看模擬器內的連線提示及搖桿數值。

命令列：`python -X utf8 -m qysim.server --qirc`；可加 `--adb 路徑` 或 `--qirc-serial 裝置序號`。
轉接僅發送通道數值查詢，不修改遙控器韌體、USB 模式或校準資料。

開啟 <http://127.0.0.1:8080/controller-check.html>，點一下頁面、按遙控器按鍵，再推動搖桿。
檢查頁會列出所有瀏覽器可見的裝置、即時軸值、移動範圍與按鍵，可按「產生檢查結果」複製回報。
若沒有裝置，在 Windows 執行 `joy.cpl`，檢查系統是否將遙控器識別為遊戲控制器。

使用者提供的 QYSea OpenSDK V1.2.1（20260520、Python 3.13）中，`QYRovControllerManage`
提供的是向 ROV **送出**搖桿指令；`QYRovRealTimeStatusManage.get_rov_status()` 文件中的
`RC_Switch_Status` 只有鎖定、定深、拍照／錄影、模式及 LED 等狀態，未列出兩支搖桿及兩個波輪的原始軸值。
因此 USB 轉接直接查詢遙控器本機通道，不使用 SDK 的 `set_*` 發送介面充當實體輸入讀取。

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
| `korean_castle` | Korean Castle 沉船調查 | 150 m 貨輪斷成三截躺在 32 m 海床；依 X1 格網編號檢查兩處斷裂面、二號貨艙（艙外）、艉樓窗框；深處要開燈 |
| `random` | 隨機模式 | 隨機結構物、洋流、能見度、纜長；`--seed` 可重現同一題 |

評分：完成目標得分，碰撞扣分（輕觸 5／重撞 15／嚴重 30），纜線張力過高扣 10；**斷纜或嚴重碰撞 3 次即任務失敗**。
嚴重碰撞會打壞撞擊點附近的推進器（推力剩 55%），`ego_self_test()` 會回報該電機異常。

### Korean Castle 沉船模型

`cad/korean_castle/Korean_Castle_Display.blend`（依海報推估的示意模型，**非實測、不可用於導航**）。
船體、附著物與海床轉成網頁模型；模型裡的碰撞網格預先算成 0.3 m 的距離場，ROV 機身、纜線與測距都會真的撞到船體。
換模型或改碰撞網格時：

```bash
blender -b --python tools/wreck_blender_export.py -- ../cad/korean_castle/Korean_Castle_Display.blend OUT
python tools/build_wreck.py OUT            # 產生 qysim/assets/korean_castle_field.npz 與 .json（需要 scipy）
# 再用 gltf-transform 壓縮 OUT/korean_castle_raw.glb → viewer/models/korean_castle.glb（meshopt）
```

### 周邊環境

每個情境都會加上沙紋海床與遠處沙丘、礁岩、散落鋼板與管線、隨流擺動的海藻、繞著結構物游的魚群；
水面有遠方島嶼、離岸風機、其他船隻與航道浮標。這些只是外觀（沒有碰撞），會避開結構物、檢查點與起點附近。網址加 `?noenv` 可關掉。

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

- `python tools/record_demo.py`：用真正的模擬器跑四段示範飛行（導管架碰撞、纜線纏繞脫困、強流懸停、Korean Castle 沉船調查），存成 `viewer/demo_recording.json`。
- `node tools/render_movie.js --ffmpeg <ffmpeg>`：把回放逐格渲染成 MP4（需要 Playwright；先用靜態伺服器開 `viewer/`）。
- 不開伺服器也能看：`viewer/index.html?replay=demo_recording.json`（需要用任何靜態網頁伺服器開，例如 `python -m http.server`）。
- `python tools/build_showcase.py` 產生 `docs/showcase/`（GitHub Pages 用）。在 GitHub repo 的 **Settings → Pages** 選 *Deploy from a branch*，分支選這個分支、資料夾選 `/docs`，網址就是 `https://<帳號>.github.io/rov/`。
- 3D 模型來源與授權見 [`viewer/models/CREDITS.md`](viewer/models/CREDITS.md)（全部 CC0 / MIT）。

## 協定與程式結構

- 通訊協定：[`PROTOCOL.md`](PROTOCOL.md)
- `qysim/physics.py` 剛體與推進器　`controller.py` 飛控　`rc.py` 遙控器與操控手模式　`world.py` 結構物／碰撞／洋流
  `tether.py` 臍帶纜　`navigation.py` 自動駕駛　`scenarios.py` 情境與評分　`engine.py` 整合＋SDK 語意　`server.py` 服務
- `viewer/app.js` 駕駛台　`deploy_intro.js` 下水動畫　`pilot_pip.js` 操作員子畫面　`humanoid.js` 人物骨架與 IK　`environment.js` 周邊環境　`cable.js` 纜線繪製　`glb.js` 模型載入
- 測試：`python -m unittest discover -s tests`
