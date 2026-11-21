# 自有量測資料

目前儲存庫裡只有 `synthetic/`，**全部為合成資料，不是 X1 實測證據**。
`fit-x1` 與下面的 H5 分析都只寫建議，不修改 `qysim/vehicles.py`，也不會把目錄裡的暫定值升成 measured。

## 給記錄的人（水池、靜水）

一趟實驗一個資料夾：`docs/reference/own/YYYY-MM-DD-簡稱/`。原始表與影片連結留在裡面，不要覆蓋。
影片若尚未確認可以進儲存庫，就放公司自己的空間，資料夾裡只留檔名、SHA256 與連結。
座標與模擬器相同：surge 向前為正、sway 向右為正、heave 向下為正、偏航以右手定則、深度向下為正。

先寫 `manifest.json`。沒量到的尺度填 `null`，不要拿目錄裡的暫定質量、時間常數或浮力來填。

```json
{
  "schema_version": 1,
  "synthetic": false,
  "vehicle": "x1",
  "operator": "姓名",
  "date": "2026-11-17",
  "water": "靜水池，無流",
  "dry_mass_kg": null,
  "motor_tau_s": null,
  "bias_force_n": {"surge": 0.0, "sway": 0.0, "heave": 0.0},
  "open_loop_gear": "A",
  "notes": "淨浮力已配平才把 bias 填 0。tau 沒量到就維持 null。"
}
```

`open_loop_gear` 是 App 上「推桿直接對推力」的那一檔，預設 `A`。其他檔位（例如 `S`）照畫面原文記，工具只報告速度，不拿來擬合阻尼，因為那些檔可能是速度閉迴路。

### 計時表 `timing.csv`

滿桿、速度穩定之後，記錄通過兩個已知距離標記的時間。正反方向、每個要用的檔位各至少一趟。

| 欄 | 中文表頭也接受 | 單位 | 說明 |
|---|---|---|---|
| `axis` | 軸向 | — | `surge` / `sway` / `heave`。偏航不要寫在這裡 |
| `gear` | 檔位 | — | App 上的檔位原文，例如 `A`、`S` |
| `direction` | 方向 | — | `positive`／`正` 或 `negative`／`負` |
| `distance_m` | 距離 | m | 兩標記的距離，必須為正 |
| `time_s` | 時間 | s | 通過兩標記的時間，必須為正 |

```csv
axis,gear,direction,distance_m,time_s
surge,A,positive,5,2.16
surge,A,negative,5,2.41
surge,S,positive,5,3.10
sway,A,positive,3,2.33
heave,A,positive,1,1.30
```

速度 = 距離 / 時間，方向決定正負。這是穩態速度，不能單獨分開質量、阻尼與推力。

### 鬆桿標記 `coast.csv`

固定相機，尺和載具在同一平面。從靜止開始記，命令用已正規化的軸命令 `[-1, 1]`（本列保持到下一列），不要直接填 PWM。
松桿那一格的 `event` 寫 `release`。要能擬合質量與兩項阻尼，同一軸裡要有多個幅度的階躍和鬆桿，不能只有滿桿。

公尺位置與像素位置二擇一。像素時 `scale_px` 與 `scale_m` 都要為正，而且同一段影片的尺標比例要固定。

| 欄 | 中文表頭也接受 | 說明 |
|---|---|---|
| `axis` | 軸向 | `surge` / `sway` / `heave` |
| `time_s` | 時間 | 該軸自己的時間，嚴格遞增，建議約 0.1 s 一點 |
| `position_m` | 位置_m | 沿軸的位置，公尺，可帶正負 |
| `position_px` | 位置_px | 沒有公尺時改填像素 |
| `scale_px`, `scale_m` | 尺_px, 尺_m | 像素標記才需要 |
| `command` | 命令 | `[-1, 1]`，第一列必須是 `0`（從靜止開始） |
| `event` | 事件 | `release`、`command_change`，沒有就留空 |

```csv
axis,time_s,position_m,command,event
surge,0.0,0.000,0,
surge,0.1,0.020,1,command_change
surge,5.0,8.400,0,release
surge,5.1,8.610,0,
```

工具直接用這些點：滑行距離是鬆桿到這段結束的位移；時間常數是位移走到全程 63%（1−1/e）的時間。
線性阻尼時它等於時間常數；二次阻尼大時它只是等價的一階時間。質量、附加質量與兩項阻尼是後面的最小平方，不是這個 63% 時間本身。
最後 1 秒還移動超過 1.5 cm，報告會標成尚未停穩，那種距離不要當成「滑到停」。

### 原地旋轉 `yaw.csv`

滿桿、角速度穩定之後計時轉完的圈數。鬆桿之後多轉的角度填 `coast_deg`（沒有就留空）。

| 欄 | 中文表頭也接受 | 說明 |
|---|---|---|
| `gear` | 檔位 | 同上 |
| `direction` | 方向 | `positive` 或 `negative` |
| `revolutions` | 圈數 | 正數 |
| `time_s` | 時間 | 轉完這些圈的秒數 |
| `coast_deg` | 鬆桿角度 | 鬆桿後再轉過的角度，度，可空白 |

```csv
gear,direction,revolutions,time_s,coast_deg
A,positive,5,12.4,35
A,negative,5,12.6,-33
```

角速度 = 圈數 × 360° / 時間（報告同時給 rad/s）。這只是穩態偏航率。
一個鬆桿角度不能分開轉動慣量與阻尼，工具不會建議改 `inertia`。

### App 畫面的深度與航向

半自動：人先框數字，工具才讀。框要含一點黑底，只框數字，不要框到標籤；數字要亮、底要暗、字元之間有空隙。

`osd_roi.json`：

```json
{
  "schema_version": 1,
  "confirmed": true,
  "depth": {"x": 8, "y": 6, "width": 90, "height": 28},
  "heading": {"x": 140, "y": 6, "width": 90, "height": 28}
}
```

`confirmed` 必須是 JSON 布林 `true`。沒確認就拒絕讀，避免把框歪的結果當成數據。

幀的清單 `osd_index.csv`（`file,time_s`），圖放在 `osd/`。或者給一支 `osd.mp4`（需要已安裝的 opencv）。
讀完會在報告目錄放裁切圖與 `osd_readings.csv`。對不上就改那份表，放回資料夾再跑；有 `osd_readings.csv` 時以人工表為準。

欄位：`time_s,depth_m,heading_deg`。深度公尺、向下為正；航向度。

### 要擬合絕對參數時還要有的檔

質量、附加質量、線性阻尼、二次阻尼與推力上限沿用既有 sysid：先用獨立的靜態推力秤 `thrust.csv` 定力量尺，再用上面的軌跡做最小平方。
缺 `thrust.csv`、乾重、`motor_tau_s` 或 `bias_force_n` 任何一項，工具仍會交出速度、滑行距離、偏航率，但不會編造絕對阻尼。欄位定義見下方 H5 小節。
`bias_force_n.heave` 在已配平、靜水時才填 0；沒配平就不要用升降來擬合。

### 怎麼跑

在 `simulator/`：

```bash
python -m tools.sysid.synthetic --field /tmp/x1-field
python -m tools.sysid fit-x1 /tmp/x1-field --output /tmp/x1-field-report
```

第一行用目前的 `Vehicle()` 造一組假水池資料（計時、鬆桿標記、轉圈、OSD 圖），只為了測試管線。
第二行讀一個資料夾。`--output` 可省略，預設寫到該資料夾的 `fit-report/`。
報告是 `REPORT.md`、`report.json`、殘差圖，以及 `vehicles.py.suggestion`。建議稿標明來源等級：

- 合成資料一律 `estimated`，出處寫明不是實測。
- `synthetic: false` 的自有紀錄，速度、附加質量與阻尼可以標 `measured`，出處是這次的檔案。
- `thruster_max` 一律 `estimated`：它是軸向力除以目前的配置幾何，幾何本身還沒有實測。
- 不會標成 `published`，也不會把別的機型的數字寫進來。

旋轉阻尼、慣量、乾重、`motor_tau`、浮力與推進器配置都列在「維持不動」。乾重只當作你秤給工具的輸入，不會被自動寫回目錄。

## 階躍時間序列與離線辨識（H5）

每次實驗放 `own/YYYY-MM-DD-run-id/`，保留原始資料與處理版本，勿覆蓋原始紀錄。
影片存公司授權的外部空間，manifest 記連結、SHA256、操作者、環境、載重、配平、
水密度／流速、纜長、模式、韌體、感測器有效性及時間同步事件。不要提交未授權錄影。
原始 SDK 資料保留缺值，不能把失鎖當零速；分段剔除無效資料，另立 run，不跨缺口內插。

## 檔案與單位（schema_version = 1）

- `manifest.json`：`schema_version:1`、`synthetic` 布林、`dry_mass_kg` 實秤乾重、
  `motor_tau_s` 獨立測得的推進器時間常數、`bias_force_n`（surge/sway/heave 常數外力）。
  這三個尺度不得以暫定值冒充實測。靜水水平姿態時 heave 淨浮力為負值；
  合成隔離試驗抵銷浮力，故 bias 為零。另記 `conditions` 與校正來源／不確定性。
- `telemetry.jsonl`：UTF-8，每行一個 JSON；`time_s` 為共同單調時鐘的秒數。
  `get_rov_data` 原樣保存 SDK 回覆 `{status,status_code,text,data}`。
  `data.rov` 對應 depth（m，向下）、yaw/pitch/roll（度）、w/x/y/z 四元數、
  altitude、temperature、endurance、power；`data.dvl` 對應 x/y（NED m）、vx/vy
  （**世界座標** m/s）、online、position_valid、有效性與 beams。SDK 沒有 vz，不能捏造。
  `state` 保留記錄器正規化的 mode（A/S/C）、locked、keep_depth 與其原始狀態來源；
  `targets:{depth_m,yaw_deg}` 記目標值；命令與遙測的發送／接收時間應另存，不能混用。
  合成 JSONL 僅示範定深定向所需欄位，不宣稱是完整 SDK 回覆。
- `video.csv`：`axis,time_s,scale_px,scale_m,command,position_px,event`。
  尺標像素及公尺長度皆正值，位置是沿該軸帶正負號的像素投影；
  surge 向前、sway 向右、heave 向下為正。event 記階躍、鬆桿、同步閃光、遮蔽等事件。
  固定相機、尺與載具同平面；先修正透視／鏡頭畸變，移動相機須重新分段。
  匯入器以固定尺標換算位置並對時間求梯度；像素雜訊會放大，須檢查速度曲線，
  本工具不自動平滑或補洞。`fit-x1` 看到 `video.csv` 或 `coast.csv` 時，改對位置做同一套
  運動方程式的最小平方，不先把標記差分成速度。影片時間先用同步事件轉成 SDK 時間。
- `motion.csv`：`axis,time_s,velocity_m_s,command`。每軸一個連續 run，時間嚴格遞增，
  速度為機體 FRD 相對水速。DVL 世界速度須先用姿態轉回機體、扣除水流，或使用影片標註。
  command 是已正規化的軸命令 [-1,1]，本列保持到下一列，不是直接套入 PWM。
  起始推力必須已歸零；起始速度由首列取值。三軸都需要階躍與鬆桿、正反向及多個幅度。
- `thrust.csv`：`axis,command,force_n`，靜態推力秤量（帶正負號、扣除支架零點），
  每方向至少兩個不同非零幅度、至少四筆（建議 .25/.5/.75/1，各重複三次）。
  使用與 motion 相同的命令映射、供電與配置。缺少此獨立尺度無法同時辨識推力、阻力與附加質量，
  工具拒絕輸出絕對參數。乾重已知仍不能解除這個尺度退化。
- `control.csv`：`time_s,depth_m,yaw_deg,depth_target_m,yaw_target_deg`。
  定深與定向開啟、A 模式、無手動輸入的片段，目標本列保持到下一列。
  回放以首列深度／航向初始化，初始速度／角速度／馬達推力為零；取靜止起始片段。
  使用目前模擬器的預設參數與控制器，無纜線、水流、碰撞，並回報深度／航向 RMSE、
  實測對目標的追蹤 RMSE（依序 m、deg），航向誤差使用 ±180° 最短角差。
- `tether.csv`：`length_m,dry_mass_kg,wet_force_n,diameter_m,water_density_kg_m3`。
  至少三次獨立重複；濕重為完全浸水後帶正負號的支撐力 N，浮纜為負，須扣除夾具。
  濕重／長度 N/m；浮力 = (乾重×9.81 − 濕重)/長度；密度 = 乾重/圓柱體積 kg/m³。
  同時計算浮力與水密度×截面積×9.81 的殘差，檢查氣泡、直徑與秤量偏差。

## 執行

```bash
cd simulator
python -m pip install -r requirements.txt
# 重建合成資料（固定 seed=51，現有 Vehicle.step，0.01 s）
python -m tools.sysid.synthetic ../docs/reference/own/synthetic
# 原始資料轉成分析 CSV（可選；輸出路徑自行指定）
python -m tools.sysid.import_data telemetry ../docs/reference/own/synthetic/telemetry.jsonl /tmp/control.csv
python -m tools.sysid.import_data video ../docs/reference/own/synthetic/video.csv /tmp/motion.csv
# 完整分析，輸出與輸入使用不同目錄
python -m tools.sysid ../docs/reference/own/synthetic --output /tmp/x1-sysid-report
# 水池格式（計時表、鬆桿標記、轉圈、OSD）的建議稿，同樣不改 vehicles.py
python -m tools.sysid fit-x1 ../docs/reference/own/synthetic --output /tmp/x1-sysid-report
python -m unittest discover -s tests
```

`report.json` 包含建議值、95% 信賴區間、單位化 RMSE、控制器與纜線結果；
`*-residual.png` 是速度擬合殘差，`*-overlay.png` 是模擬／觀測時間序列。
示例見 [synthetic/report/report.json](synthetic/report/report.json) 與 [報告摘要](synthetic/REPORT.md)。

## 模型與適用限制

每軸以 `(乾重+附加質量) dv/dt = F + bias − L v − Q v |v|` 擬合，
推力先由秤量獨立擬合正反向 `F=a u+b u |u|`，再以已知一階 motor_tau 回放。
使用非負約束的時間序列最小平方，積分步長不超過 0.01 s，避免直接微分含雜訊速度。
它是隔離軸辨識：姿態固定、靜水、無纜線／碰撞／閉迴路控制力；完整六自由度耦合試驗
不能直接丟入此模型。實驗須先滿足條件或補做隔離試驗。

CI 為局部 Jacobian 的 Student-t 95% 區間，假設殘差獨立、同方差；動態 CI **以推力校正、
乾重、tau、bias 已知為條件**，不包含其誤差、時間偏移、相關雜訊或模型偏差。
纜線 CI 為重複試驗的平均值區間；真實資料須另檢查殘差與校正誤差，不能將小 CI 視為物理正確。

`vehicles_py_suggestions` 的 added_mass 為三軸，linear_drag／quadratic_drag 的旋轉三項
用 null 表示未辨識，**不能直接貼入 vehicles.py**。軸推力曲線不是單顆推進器參數；
`thruster_max_candidates_n` 以各軸滿桿推力除以目前幾何 authority 比例，列出等效單馬達候選值；
只有線性、同構型、對稱且各軸一致時才可能套用 thruster_max，不能從軸負向推力推論個別馬達反推比。非線性曲線目前不能由現有
vehicles.py 表達，保留報告供審查；不猜測慣量、旋轉阻力、單馬達反推比或纜線阻力。

合成資料由現有物理引擎的隔離軸試驗產生（抵銷浮力、限制旋轉、無纜線），
速度加 σ=0.001 m/s、秤量加 σ=0.01 N 的高斯雜訊。控制器資料另由現有六自由度引擎產生。
這驗證數值還原能力，不代表真機模型已獲驗證。T20 的 `fit_measurements.py` 與舊 CSV 契約維持原樣。
