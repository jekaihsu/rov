# SDK 開發沙盒快速開始

在模擬器主機上執行既有 Python 工具，把它原先匯入的 SDK 換成儲存庫內的相容套件。先在儲存庫根目錄開一個終端機：

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r simulator/requirements.txt numba
cd simulator
python -m qysim.server --scenario harbor_inspection
```

瀏覽器可開啟 `http://127.0.0.1:8080/` 觀察，純 SDK 作業可加 `--no-http`。第二個終端機從儲存庫根目錄設定：

```sh
. .venv/bin/activate
export PYTHONPATH="$PWD/simulator/sdk_mock${PYTHONPATH:+:$PYTHONPATH}"
python -c "import qysea; print(qysea.__file__, qysea.IS_QYSIM_MOCK)"
python /path/to/my_tool.py
```

Windows PowerShell 的對應指令為 `.\.venv\Scripts\Activate.ps1`、`$env:PYTHONPATH = "$PWD\simulator\sdk_mock;$env:PYTHONPATH"`。
確認印出的路徑在本儲存庫內且旗標為 `True`。既有工具可沿用其 manage 類別與方法。

## 讀狀態、送控制

在預設的 `ROV_USA` 配置下，以下程式讀深度（公尺）與航向（度），接手控制、短暫前進，再交還控制。請使用剛啟動的獨立沙盒。

```python
import time
from qysea.sdk.manage.QY_Rov_Manage import QYRovRealTimeStatusManage
from qysea.sdk.manage.QY_RovController_Manage import QYRovControllerManage

status = QYRovRealTimeStatusManage()
rc = QYRovControllerManage()
reply = status.connect_to_rov()
if reply["status"] != "ok":
    raise RuntimeError(reply)
try:
    reading = status.get_rov_status()
    if reading["status"] != "ok":
        raise RuntimeError(reading)
    print(reading["Depth"], reading["Compass"])
    reply = rc.set_remote_control_status("ON")
    if reply["status"] != "ok":
        raise RuntimeError(reply)
    try:
        rc.set_rc_lock_button(0)
        rc.set_right_joystick_up_down(1600)
        time.sleep(0.5)
    finally:
        rc.set_right_joystick_up_down(1500)
        rc.set_rc_lock_button(1)
        rc.set_remote_control_status("OFF")
finally:
    status.disconnect_rov()
```

## 跑一次完整範例

在 `simulator/sdk_mock` 目錄執行下表指令。逐樁巡檢請使用新啟動的 `harbor_inspection`，維持預設操作配置；
巡航可在 `open_water` 執行。一次只執行一支取得控制權的程式；記錄器與即時曲線可以在另一個終端機旁聽。

| 任務 | 指令 | 如何讀結果 |
|---|---|---|
| 觀察深度 | `python examples/telemetry_plot.py` | 每 0.2 秒取樣，終端機保留最近 60 點。左方是目前視窗的最小／最大深度，曲線越高代表越深，右方是最新讀值。 |
| 定深定向巡航 | `python examples/depth_heading_cruise.py --target-depth 3` | 以壓力深度與羅盤回授維持目標深度及起始航向；DVL 失鎖時停止前進。摘要包含深度及航向誤差。 |
| 港口入口逐樁拍照 | `python examples/pile_photos.py` | 依巡檢圖走訪入口雙樁 Outer dolphin、Outer dolphin twin。在每根樁南側約 2 m 朝北拍一張，照片進入模擬 SD 卡，終端機列出拍攝時的 DVL 估位。失鎖或單站逾時即中止。 |
| 聲納找目標 | `python examples/sonar_target.py` | 以觀察者訂閱一次掃描，輸出最強有效第一回波的相對方位、斜距及強度。另用 `--scenario sonar_search` 啟動時可看到起點右前方約 18 m 的搜索目標。空水域可能回傳 null；回波可能來自結構、魚或纜線。 |
| 記錄及回放下潛 | `python examples/dive_log.py record dive.jsonl --seconds 30`，接著 `python examples/dive_log.py replay dive.jsonl --speed 2` | 在駕駛前開始記錄，把經過秒數與 SDK 原始狀態逐行存入新檔。離線回放依原間隔兩倍速送往標準輸出，可接入分析程式。 |
| 接上影像辨識 | `python examples/ai_frames.py --seconds 3` | 讀取 BGR uint8 影像，印出尺寸與空偵測清單。在 Python 搜尋路徑放入自有模組，傳入 `--detector my_module:detect`；函式接收一張影像，回傳可 JSON 序列化的 `[{cls, score, box}]`，box 為左上角起算的正規化 xywh。 |

連線範例預設使用執行中伺服器的場景。指定其他埠時，TCP 範例加 `--port`，聲納範例加 `--url ws://127.0.0.1:埠號`。
[協定概念](protocol.md) · [常見問題](faq.md) · [完整線上格式](../../simulator/PROTOCOL.md)
