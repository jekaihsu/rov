# H3：狀態封包頻寬

基底：main（5c5dc4c）。分支：task/H3-state-bandwidth。

量測所有 catalogue 情境與 seed 42 的 random；每個情境比較單人與四條連線
（三位駕駛＋一位教官，現行房間容量仍是三個駕駛席）。工具位於根目錄
`tools/state_size_report.py`，逐則 CSV 與彙總 JSON 留在指定輸出目錄，不提交產生物。
另外以 `--sonar --scenario sonar_search --seconds 1` 量測選填聲納訂閱。

相容性稽核後依任務的例外條件保留完整快照：主畫面、StateBuffer、回放與教官
主控台未實作通用的省略欄位沿用；sdk_mock 是請求／回應且不合併快照。因此不對
flow_field、power、thermal 實作降頻，亦不送出會誤導客戶端的更新時間標記。
flow_field 既有的 0.5 秒取樣／插值不變。未改輸入 Worker、心跳或失聯保護。

精度只作用於 viewer snapshot 的複本，限制為六位有效數字（相對誤差不超過
5e-6），保留時計與精確選擇鍵；既有較低的姿態精度不變。SDK 方法與物理計算
不變。明確指定 WebSocket deflate；這也是 main 原本使用的 library 預設值。
這些精度預算是傳輸工程假設，不是任何真機的精度宣稱。已查閱研究報告；目前
main 沒有 AGENTS.md 提及的 `docs/reference/own/` 目錄。

驗證：全套 Python unittest、Node tests、browser_smoke、browser_hud_smoke、
browser_link_smoke、observation_smoke、browser_gameplay_smoke。新增測試涵蓋
裁切誤差、型別、不可變性、SDK 結果、完整欄位重送與有／無壓縮連線。
實際結果及前後所有情境的大小／頻寬表附於 draft PR。

後續：若需要顯著降低重複欄位，須另設協商式 delta 協定，同步處理各客戶端、
錄製與回放的欄位保留／刪除／重置，再對已確認支援的連線啟用降頻。
