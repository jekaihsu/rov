# SDK / AI 整合範例

安裝與第一個範例（Python 3.10+，從倉庫根目錄）：

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r simulator/requirements.txt
cd simulator
python -m examples.missions cruise --csv cruise.csv
```

所有命令從 simulator/ 執行，不需伺服器與瀏覽器。直接使用既有引擎固定 0.01 秒步長，
不等待牆鐘，可快於即時執行；實際倍率取決於機器。不保證跨平台浮點位元一致。

| 命令（前綴 python -m examples.missions） | 用途與預期輸出 |
|---|---|
| cruise | SDK DVL 矩形導航，定深定向閉迴路；reached: 4 |
| wall | 以前向測距保持起始離牆距離，向右掃描；輸出平均誤差 |
| camera | 機載姿態渲染 BGR，存 frame.ppm；shape: [180,320,3] |
| tether | 每 0.1 秒監看張力，超過 2 N 改後退推力；輸出峰值、退避次數 |
| inspection | 依序三站、低速懸停 3 秒拍照，既有任務引擎判定；completed: 3 |
| batch | 固定種子 18 抽取 20 個整數種子重跑矩形控制器；成功率與平均模擬時間 |
| read_csv --csv cruise.csv | 解碼紀錄；輸出筆數與最後時間 |

每個範例可獨立執行；--csv PATH 指定紀錄位置（預設覆寫 run.csv）。
PPM 是標準 RGB 影像格式，不需要額外編碼依賴。
渲染時間固定為 1 + sim.t，避免既有渲染器在零秒使用牆鐘。
輸出檔為本機產物，請勿提交。

## Python 環境：模擬器擴充

```python
from examples.env import Env, read_csv

env = Env(scenario="random", seed=42, ticks=10)
initial = env.reset(seed=42)
observation = env.step([1500, 1500, 1600, 1500, 1500, 1500])
snapshot = env.observe()
env.save_csv("run.csv")
rows = read_csv("run.csv")
```

六個 PWM 通道依序 left_ud、left_lr、right_ud、right_lr、left_wave、right_wave，
1000–2000，中心 1500。預設 ROV_USA 對應與既有推力語意，不是速度指令。
reset 會解鎖模擬載具。step 持續 ticks * 0.01 秒，observe 不推進時間。
姿態四元數 body FRD → world NED；位置 NED m、速度 body FRD m/s、深度向下正。
forward/right/down 測距是載具中心射線，單位 m，上限 50，未命中回傳 50；不是聲納模型。
纜線沿用協定欄位（張力 N）。觀測包含理想真值，不代表真機都有這些資訊。
CSV 每列為動作後的 t、action、observation；後兩者為 JSON。
SDK 模式記錄完整 RC 狀態，一般 step 記錄六個 PWM，並非完整 SDK 呼叫重播格式。

## 原廠 SDK 相容介面與模擬器擴充

**原廠 SDK 相容介面**：既有 manage 方法，例如 set_remote_control_status、
set_rc_lock_button、init_dr、start_h_navi、set_h_navi_settings、stop_h_navi，
以及拍照 take_photo_normal。沒有修改既有類別、回傳值或物理。

**模擬器擴充**：Env、local_manage 物件級同步傳輸綁定、固定步進、真值測距、
直接渲染、CSV、種子與任務評分。local_manage 只把該物件呼叫送往同一引擎，
不經 TCP、不修改全域 SDK 傳輸。這些功能不屬於原廠 SDK。

一般模擬 SDK TCP 使用方式（另一終端執行 SDK 程式）：

```sh
cd simulator
python -m qysim.server --scenario open_water --seed 1
# 另一終端，在 simulator/ 下
export PYTHONPATH="$PWD/sdk_mock"
python your_sdk_tool.py
```

換真機：移除 missions.py 強制加入 sdk_mock 的 sys.path 設定，安裝真機 SDK，
直接建構 manage 物件取代 local_manage；按硬體設定連線和 DVL 初始化。
用真機狀態回授與即時節拍取代 advance，不能在真機使用無等待迴圈。
測距接實體感測器；影像改用 SDK capture_video/get_frame/close_video。
真值、種子、任務判定留在模擬器，並非只換 import 就能部署。

控制增益、2 N 門檻、航線與測距皆為教學假設，未經實機量測。
批次成功表示在開放水域到達四個航點，不代表隨機障礙場景或真機可靠度。
後退推力不保證任意纜線幾何皆能減張，實務須另外制定安全策略。

驗證：python -m unittest tests.test_examples -v；python -m unittest discover -s tests。
