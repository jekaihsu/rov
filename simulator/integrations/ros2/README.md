# ROS 2 橋接（模擬器擴充）

這是 SI 開發沙盒的 **模擬器擴充，不是原廠 SDK 介面，也不是實機驅動**。
獨立的 `ament_python` / `rclpy` 套件，不 import 模擬器、不修改物理或協定。
控制走既有 WebSocket v2；DVL 與測距走既有只讀 SDK RPC。

## 從零開始：Docker / ROS 2 Humble

安裝 Git、Docker Engine 和 Compose v2（Linux），然後：

```bash
git clone https://github.com/jekaihsu/rov.git
cd rov
docker compose -f simulator/integrations/ros2/compose.yaml up --build -d
docker compose -f simulator/integrations/ros2/compose.yaml logs bridge
# 開啟相同網路與 ROS_DOMAIN_ID=42 的終端
docker compose -f simulator/integrations/ros2/compose.yaml exec bridge bash
source /ros_ws/install/setup.bash
ros2 topic list
ros2 topic echo /odom --once
ros2 topic echo /dvl/velocity --once
ros2 topic echo /range/forward --once
```

先讓橋接加入，再開 http://localhost:8080/，避免其他駕駛占用第一席。
**固定使用 training/v1**：SDK RPC 只能提供這台載具的遙測。
第一席被占用時橋接會拒絕運作；關閉其他駕駛、等待 30 秒席位保留期過後重啟橋接。
重連使用記憶體內的 resume token，不寫入日誌。
RPC 仍只監聽 loopback；Compose 共享 simulator network namespace，不公開 RPC 埠。
外部部署也應共用伺服器網路 namespace，勿混用不同伺服器的 WS 與 RPC。

每個終端都先執行上面的 exec 與 source。先持續送指令，再明確解鎖：

```bash
# 終端 A；停止發送超過 0.4 秒就自動上鎖
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.2}}'
# 終端 B
ros2 topic pub --once /arm std_msgs/msg/Bool '{data: true}'
ros2 topic echo /odom --once --field twist.twist.linear
ros2 topic pub --once /lights std_msgs/msg/UInt8 '{data: 2}'
ros2 topic echo /diagnostics --once
ros2 topic pub --once /arm std_msgs/msg/Bool '{data: false}'
```

定深時先停止 cmd_vel，持續送 depth/setpoint，再解鎖。最新的速度／深度命令會切換模式，
**不要同時發布兩者**；深度模式會清除舊速度，速度模式會取消深度設定。

```bash
ros2 topic pub -r 10 /depth/setpoint std_msgs/msg/Float64 '{data: 3.0}'
# 另一終端
ros2 topic pub --once /arm std_msgs/msg/Bool '{data: true}'
ros2 topic echo /depth --once
ros2 bag record /odom /tf /tf_static /depth /dvl/velocity /range/forward /range/down /diagnostics
```

結束：`docker compose -f simulator/integrations/ros2/compose.yaml down`。
容器含 rviz2，但 GUI 需要自己的 DISPLAY / Wayland 轉接；也可原生執行（下節）。
DDS 跨容器／主機需要可達 multicast 網路；上述 exec 是最簡單的驗證方式。
若環境有企業 TLS 代理，可先建置同名 image：

```bash
docker build --secret id=pip_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t rov-ros2:humble -f simulator/integrations/ros2/Dockerfile .
docker compose -f simulator/integrations/ros2/compose.yaml up -d --no-build
```

## 原生安裝、launch、RViz

Ubuntu 22.04，先依 ROS 官方指南安裝 ROS 2 Humble。在倉庫根目錄：

```bash
sudo apt-get install python3-colcon-common-extensions python3-websocket python3-pytest ros-humble-rviz2
source /opt/ros/humble/setup.bash
mkdir -p /tmp/rov_ros_ws/src
ln -s "$PWD/simulator/integrations/ros2" /tmp/rov_ros_ws/src/rov_sim_bridge
cd /tmp/rov_ros_ws
colcon build --packages-select rov_sim_bridge
source install/setup.bash
# 另一終端按 simulator/README.md 啟動伺服器
ros2 launch rov_sim_bridge bridge.launch.py rviz:=true
```

Launch 參數：ws_url、rpc_host、rviz。節點另有 rpc_port（9760）、command_timeout
（0.4 s，允許 0.1–0.5）、odom_frame、base_frame、publish_truth（預設 false）。Topic 都可用標準 ROS remapping 改名。

## Topic 與座標

| 方向 | Topic | 訊息 | 語意 |
|---|---|---|---|
| 發布 | odom、/tf | nav_msgs/Odometry、TF | odom ENU → base_link FLU，感測器估計（見下） |
| 發布 | ground_truth/odom | nav_msgs/Odometry | 僅 publish_truth:=true；物理真值，超出真機，供評估估測器 |
| 發布 | depth | std_msgs/Float64 | 壓力深度估計，水面以下正值，m |
| 發布 | dvl/velocity | geometry_msgs/TwistStamped | SDK DVL 線速度，FLU，m/s；失鎖時為 0；角速度未提供 |
| 發布 | range/forward、range/down | sensor_msgs/Range | SDK 測距，m；25° 錐、盲區 0.3 m；無回波 +Inf、盲區內 −Inf |
| 發布 | diagnostics | diagnostic_msgs/DiagnosticArray | 纜長 m、張力 N、纏繞、斷纜、鎖定、RC 回讀 |
| 訂閱 | cmd_vel | geometry_msgs/Twist | 機體 FLU 線速度 m/s、角速度 rad/s |
| 訂閱 | depth/setpoint | std_msgs/Float64 | 非負深度 m；啟用既有定深迴路 |
| 訂閱 | lights | std_msgs/UInt8 | 0 關、1 低、2 高；其他值忽略 |
| 訂閱 | arm | std_msgs/Bool | true 解鎖，false 上鎖；預設鎖定 |

NED `[n,e,d]` → ENU `[e,n,-d]`，FRD `[f,r,d]` → FLU `[f,-r,-d]`。
四元數同時轉換世界與機體基底並正規化。Range 原點為機體前方 0.4 m、下方 0.2 m，
由 tf_static 提供，各感測 frame 的 +X 軸沿量測方向。
Range 的視角與盲區依主機感測器層（`PROTOCOL.md`「Optional sensor layer」）。

主機送出選填 `state.sensors` 時，odom 位置為航位推算 `pos_est`（垂直改用壓力深度），
航向為融合估計，roll/pitch 照串流；線速度與角速度不填（covariance=1e6），速度請用 dvl/velocity。
舊主機沒有感測器層時退回真值並在 diagnostics 標示 `truth`。`QYSIM_SENSORS=ideal` 時估計等於真值。
pose covariance 未估計（填 0），不可當成定位品質。
時間戳是接收時的 ROS 系統時間，**沒有 /clock，勿設 use_sim_time=true**。
模擬時間可能慢於牆鐘，重置時 pose 可能跳變，需重新初始化定位。
WS 遙測約 10 Hz，SDK 約 5 Hz；可靠 QoS、keep-last 10，指令 keep-last 1。

## 控制與失聯保護

* 每次 session 重新開始 seq、清空控制，設定 ROV_USA、S 模式和線性 RC shaping。
  cmd_vel 使用既有 assist=1 / normal 速度輔助，依 speed_limit 反轉 1.5 次方曲線，
  不是把 m/s 當推力。轉速對應主線 90/60/70 deg/s 尺度，偏航另受 profile 限制。
  PWM 限制 1000–2000；受推力、負載與加速度限制，不保證達標。
* 定深透過 keep_depth / heave 以最高 0.6 m/s 移動既有目標，並受伺服器海床限制。
  這是模擬器控制器映射，不是實機參數。目前倉庫缺少 docs/reference/own/ 量測資料。
* ROS 指令需持續更新（建議 10 Hz）；0.4 s 無速度或深度命令則清空並上鎖。
  lights、arm 不刷新有效期。解鎖需先有新鮮命令；恢復指令不會自動解鎖。
* 每 0.1 s 發 RC，沒有另外重送舊命令的執行緒。節點卡住或斷線時，
  伺服器原有 0.6 s watchdog 仍生效。input_latched / control_generation 改變時
  清空控制並以 locked RC 確認；等待 latch 清除後才接受新的明確 arm。
* 遙測過期 0.3 s、暫停、斷纜、SDK 接管、缺 assistance、DVL 失鎖（`state.sensors.dvl.status == lost`；
  舊主機為離底超出 0.1–100 m）均鎖定：伺服器在失鎖時會退回手動推力，速度指令將不再是速度。
  不呼叫 remote takeover/release，不停用任何保護。勿同時接 USB 控制器或其他控制程式。

## 相機、聲納與 nav2 邊界

目前 WS / RPC 沒有影像像素流。camera_view 是場景描述，SDK mock 需在客戶端合成 BGR；
此獨立套件不攜帶渲染器，因此**不發布 Image**。
主線已有選填前視聲納（`state.sonar`，需 `sonar_subscribe`），本套件尚未橋接，因此**不發布聲納影像／LaserScan**。
Range 不是聲納掃描。

rviz2、rosbag2 和自訂節點可直接連接。nav2 可接 odom / TF / cmd_vel，但需自行提供
map→odom、定位、costmap 資料源及平面運動限制；本套件不是完整 nav2 導航 stack。

## 測試

```bash
# 倉庫根目錄，不需 ROS
PYTHONPATH=simulator/integrations/ros2 python3 -m unittest discover -s simulator/integrations/ros2/test -v
# ROS workspace
colcon test --packages-select rov_sim_bridge
colcon test-result --verbose
# simulator/ 目錄
python3 -m unittest discover -s tests
```

實際容器雙向驗證指令與輸出見任務 PR。

兩個 Compose service 啟動後，可執行可重現的端到端檢查（會移動載具、切換燈光與定深）：

```bash
docker compose -f simulator/integrations/ros2/compose.yaml exec -T bridge \
  bash /ros_ws/src/rov_sim_bridge/test/smoke.sh
```

腳本使用真實 ros2 topic echo/pub，並以只讀 RPC 檢查伺服器的 RC 與鎖定狀態。
包含停止 ROS 指令後的上鎖、恢復指令不自動解鎖，以及 SIGSTOP 橋接 1 秒的伺服器
watchdog 測試；SIGCONT 後確認 latch 已確認但仍保持上鎖。
