# 常見問題

**為什麼工具仍載入原本的 SDK？** 檢查工具使用的 Python 解譯器及 `qysea.__file__`。工具旁的同名套件或自行尋找原廠目錄的啟動器可能優先於 PYTHONPATH。將工具移到原廠樹外，或將 mock 套件放在工具旁，再確認 `qysea.IS_QYSIM_MOCK`。

**為什麼出現 ConnectTimeout 或 Please connect ROV first？** 前者請核對 RPC 埠與主機，預設是 127.0.0.1:9760。即使用 `--host 0.0.0.0` 開放 viewer，SDK 仍只監聽 loopback。後者請在讀值的同一個 status 物件先呼叫 `connect_to_rov()` 並檢查回覆。搖桿 setter 正常也會回傳 None，可用狀態讀值確認效果。

**需要 USB 橋接才能用 SDK 嗎？** SDK 直接使用 RPC。另有實體 USB 控制器的操作路徑：從 viewer 下載座席配對檔，在控制器電腦執行 `python -m qysim.qirc_bridge --config pairing.json` 並保持該 viewer 開啟。配對檔含私密座席憑證。

**聲納一直讀到空值？** `qysea.sonar.get_latest_sonar()` 是模擬器擴充，只讀取最新掃描。請保持 training 第一艘載具的聲納訂閱連線，等待第一幀。教學範例會自行訂閱並在結束時關閉連線。

**影像辨識框為什麼對不上瀏覽器？** SDK 的 BGR 幀在客戶端依相機狀態合成。將偵測框畫在傳給辨識器的同一幀；viewer 的 vision_results 來自另一條影像路徑，上報超過一秒即失效。
