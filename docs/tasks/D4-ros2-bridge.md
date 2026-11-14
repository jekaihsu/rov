# D4：ROS 2 橋接

SI 沙盒的獨立 ROS 2 Python 套件，放在 `simulator/integrations/ros2/`，
只使用既有 WebSocket / SDK RPC；不修改 `simulator/qysim` 或 `simulator/viewer`。
這是模擬器擴充，不是原廠 SDK 介面。

交付：Odometry / TF、深度、DVL、測距、纜線診斷；速度、深度、燈光與解鎖／上鎖控制；
Humble Docker / Compose、launch、RViz 設定、從零開始的 README 和訊息轉換單元測試。
主線沒有相機像素串流或聲納掃描，明確記錄限制，不產生假影像／假掃描。

控制必須保留原有心跳、失聯 latch 與明確重新解鎖，另處理 ROS 指令來源停止的情況。
SDK 遙測只屬於 training/v1，因此本版固定占用同一席位，拒絕混合不同載具的資料。

驗收：容器內實際啟動模擬器與橋接，以 ros2 topic echo/pub 驗證雙向通信；
驗證指令停止、進程停頓後上鎖，PR 貼上實際指令與結果。
執行橋接單元測試與倉庫既有 Python 回歸測試。
