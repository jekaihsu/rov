# 自有量測資料與離線辨識（H5）

目前只有 `synthetic/`，**全部為合成資料，不是 X1 實測證據**。工具不修改
`qysim/vehicles.py`，不提升參數的 evidence level；套用建議由審查者決定。

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
  本工具不自動平滑或補洞。影片時間先用同步事件轉成 SDK 時間。
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
