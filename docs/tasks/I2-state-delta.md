# I2：狀態封包差量

基底：main。分支：`task/I2-state-delta`。

協商式、選填、完全相容的 `static_once` 能力：客戶端在 `join`／`hello`／
`instructor_join` 宣告 `"caps":["static_once"]` 後，伺服器才可省略未變動的
定義／戰役／world 鏡像欄位，以及低頻的 `power`／`thermal`／`flow_field` 等
（完整清單見 `simulator/PROTOCOL.md`）。未宣告的連線（舊前端、sdk_mock、
ROS 2 橋接）收到的內容與現在逐位元組相同。

前端合併集中在 `viewer/state_merge.js`。主畫面與教官主控台宣告能力並合併；
`StateBuffer` 只收已合併快照。錄製寫入完整合併快照，回放不宣告能力，舊回放
工具可直接讀。未改輸入 Worker、心跳或失聯保護。

驗證：全套 Python unittest（含 18 情境 × 600 tick 合併比對）、Node tests、
`tools/state_size_report.py` 有／無 caps 對照、指定瀏覽器 smoke。
