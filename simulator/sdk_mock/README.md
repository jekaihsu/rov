# qysea mock（模擬器後端的 SDK 相容層）

純 Python 的 `qysea` 替身，模組／類別／方法簽名對齊 OpenSDK `qysea.sdk.manage.*`（V1.2.1），
每個呼叫轉發到 qysim。既有工具只要改成 import 這份 `qysea`，即可連上模擬器開發。
僅需 numpy。下載照片需要 OpenCV（`opencv-python-headless`）或 Pillow；OpenCV 另提供較順的
`get_frame`、OSD、`show_video` 與 MP4 下載。

## 使用方式

```bash
cd simulator && python -m qysim.server            # SDK RPC：127.0.0.1:9760
export PYTHONPATH=/path/to/rov/simulator/sdk_mock  # Windows: set PYTHONPATH=...\simulator\sdk_mock
python my_tool.py                                  # from qysea.sdk.manage.QY_Rov_Manage import ...
```

自己用目錄行走尋找 SDK 的工具（若位在原廠樹內）會先找到**原廠** SDK。請在原廠樹外執行，
或把 `sdk_mock/qysea` 放到工具旁邊。`qysea.IS_QYSIM_MOCK` 為 `True` 可辨識 mock。

沙盒範例（從本目錄執行）：

```bash
cd simulator/sdk_mock
PYTHONPATH=. python examples/depth_heading_cruise.py --host 127.0.0.1
PYTHONPATH=. python examples/standoff_inspect.py --host 127.0.0.1
PYTHONPATH=. python examples/vision_ai_detect.py --host 127.0.0.1 --ws-port 8765
```

## 環境變數

| 變數 | 預設 | 含義 |
|---|---|---|
| `QYSIM_HOST` | `127.0.0.1` | 模擬器主機 |
| `QYSIM_RPC_PORT` | `9760` | SDK RPC 埠 |
| `QYSIM_TIMEOUT` | `3.0` | 等待回覆秒數（逾時回 `ReceiveTimeout`） |
| `QYSIM_CAMERA_FPS` | `15` | `get_frame()` 上限幀率 |
| `QYSIM_SENSORS` | （空＝真實感測器） | 設為 `ideal` 時改為理想感測器（見下） |

## `QYSIM_SENSORS=ideal`

預設為**真實感測器層**（估計值、噪聲、失鎖、盲區）。在伺服器環境設
`QYSIM_SENSORS=ideal`（或 `Simulator(sensor_config=SensorConfig(ideal=True))`）會關掉所有不完美，
讀值回到感測器層加入前的真值行為（見 `simulator/tests/test_sensors.py` 位元級回歸）。

建議流程：寫控制演算法時先用 `ideal` 驗證邏輯，再切回預設真實感測器驗證失鎖、噪聲與盲區下的強健性。

## SDK 讀值來源（真實感測器預設）

下列「更新頻率」為感測器模型內部取樣／保持節奏，不是保證的牆鐘 RPC 頻率；RPC 何時讀到取決於你呼叫的節奏。
數值標籤：**〔真機／規格〕** 來自可比對感測器規格或研究報告引用；**〔假設〕** 為模擬器選定、尚非 X1 實測。
細節與來源見 `qysim/sensors.py`、`docs/reference/real-rov-research.md`、
`research_notes/感測器_揚沙_通訊/sensors_and_navigation.md`。

| SDK 表面 | 來源 | 約更新頻率 | 與真機／舊行為差異 |
|---|---|---|---|
| `get_rov_status().Depth` | 壓力深度**估計**（零點偏移、密度設定、量化、噪聲） | 50 Hz 取樣保持 〔假設／MS5837 轉換時間〕 | 非物理真值；理想模式＝真值 |
| `Compass` / `Rov_Attitude_Angle.Yaw` | 航向**估計**（陀螺＋磁力計融合、鋼構磁偏） | 融合連續；磁力計約 10 Hz 〔假設〕 | 近鋼構可能偏離或「重新對準」跳動 〔論壇案例〕 |
| `Rov_Attitude_Angle.Pitch/Roll` | 姿態估計（真實層）／真值（理想層） | 與姿態解算同步 | Pitch/Roll 誤差通常小於航向 〔規格級 AHRS〕 |
| HF `50hz` 四元數、`depth` | 同上估計 | 標稱 50 Hz 封包 | 深度為公分整數（×100） |
| HF `10hz` `velocity` | DVL 機體速度；**失鎖時為 0** | 標稱 10 Hz | 失鎖時速度歸零，非真值滑行速度 |
| HF `10hz` `latitude`/`longitude`/`yaw` | 位置／航向**估計** | 標稱 10 Hz | 非物理真值軌跡 |
| `Accessories_Status.DVL_Status` | 底鎖狀態 | 隨 DVL 模型 | `"OnLine"`＝有底鎖；`"OffLine"`＝失鎖 〔依 Q-DVL 高度窗等模型〕 |
| `QDVL`／`MicroDVL` 速度 | 同上 DVL 速度 | 同狀態封包 | 失鎖時 X/Y/Z 速度為 0.0 |
| `Distance`（前向） | 前向測距錐波 | 約 5 Hz 〔假設〕 | **無回波→最大量程 50 m**；**盲區內→ 0.3 m** 〔Ping2 最小量程〕 |
| `Altitude`（高度計） | 下視測距錐波 | 約 5 Hz 〔假設〕 | **無回波→ 100 m**；**盲區內→ 0.3 m** |
| `get_rov_data().rov` 深度／姿態／四元數／altitude | 估計值；altitude 優先 DVL 高度否則高度計 | 呼叫當下 | 形狀未改 |
| `get_rov_data().dvl` | 估計位置／速度；另含選填 `velocity_valid`、`lock` | 呼叫當下 | 失鎖：`velocity_valid=false`、`lock` 為狀態字串、`position_valid=false`；各波束無回波為 0.0 |
| `get_rov_data().gps` | 水面附近的地理座標 | 呼叫當下 | 見「後續／已知落差」；水深時 offline |
| `get_navigation_status` / `init_dr` 回傳 lat/lng/yaw | 估計值 | 呼叫當下 | 與協定「用估計」一致 |
| `Temp`、電力／電池欄位 | 簡化模型 | — | 非實測熱／電模型 |
| 相機 `get_frame()` | 客戶端依 `camera_view` 合成 BGR | 受 `QYSIM_CAMERA_FPS` 限制 | 與瀏覽器機載畫面／`vision_results` **未對齊** 〔協定〕 |
| `get_sim_detections()` | 讀取最近一次 viewer 上報的 `vision_results` | 報告 1 秒後失效 | **模擬器擴充，非原廠 SDK** |

物理真值（`state.pos`／`q`／`vel` 等）仍驅動渲染與回放；真實擬真預設下駕駛儀表顯示 `state.sensors`。
定點／速度輔助在 DVL `lost` 時退回手動，與舊高度窗行為一致。

### 哪些依真機資料、哪些是假設

- **依真機／可比規格〔真機／規格〕**：Q-DVL 高度窗約 0.1–100 m〔廠商〕；Ping2 類測距盲區 0.3 m、波束角約 25°〔datasheet〕；深度量化約 2 mm、轉換節奏對應約 50 Hz〔MS5837〕；DVL 失鎖時 SDK 速度與 `DVL_Status` 語意（本模擬器實作）。
- **假設〔假設〕**：多數噪聲幅度、融合時間常數、鋼構磁偶極強度、DVL 底質掉波機率、coast／重鎖遲滯、魚群假回波、前向／高度最大量程沿用舊遙測 50／100 m。皆非 X1 實測；待 `docs/reference/x1-measurement-checklist.md` 補齊。

## 行為備註

- 模擬器不可達時回傳 SDK 風格錯誤值（不丟例外），例如
  `{'status': 'error', 'status_code': '408', 'text': 'ConnectTimeout'}`，或
  `capture_video` 的 `"Please check the ROV connection"`。下次呼叫會自動重連。
- 連線旗標依物件保存：未 `connect_to_rov()` 就 `get_rov_status()` 會得到
  `'Please connect ROV first'`。高頻狀態約 60 packet/s 交替 `10hz`／`50hz`。
- 相機：`capture_video()` → `True`；`get_frame()` → `(True, BGR uint8)`（640×360／1280×720）；
  `get_w_h()` → `"640.0 * 360.0"`。
- `qysea.sdk.service`／`qysea.sdk.lib` 僅為相容 import。

測試：`cd simulator && python -m unittest tests.test_sdk_mock -v`；
沙盒範例：`python -m unittest tests.test_sdk_sandbox_examples -v`。

## 自動化範例（無頭 Env）

另見 [SDK／AI examples](../examples/README.md)：決定性步進、CSV、任務評測。那些是模擬器擴充，
不是原廠 SDK 表面。本目錄 `examples/` 則示範**經 TCP 連上執行中伺服器**的相容用法。

### 聲納（模擬器擴充）

`from qysea.sonar import get_latest_sonar`：讀最近一次已訂閱掃描；需先在瀏覽器開聲納。
非原廠 SDK 介面。影像範例：`PYTHONPATH=sdk_mock python examples/sonar_image.py`。
