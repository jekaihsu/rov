# Steam 商店靜幀

在儲存庫根目錄執行。需要 Python 3.11+、模擬器依賴、Numba、Pillow、Playwright、Chromium、Inkscape CLI 與 Noto Sans Bold（Debian 套件 fonts-noto-core）。外部字型路徑可用 ROV_STORE_FONT 指定，重現字型指紋見 [CREDITS](../../../docs/store/steam/assets/CREDITS.md)。

```sh
python -m pip install -r simulator/requirements.txt numba pillow playwright
python -m playwright install chromium
bash simulator/tools/store_shots/generate.sh
```

可設 `ROV_CHROMIUM=/usr/bin/chromium` 選用系統 Chromium。各段會在本機空閒埠啟動及關閉模擬器。輸出見 [全部素材聯絡表](../../../docs/store/steam/assets/contact-sheet.jpg)、[四語圖說](../../../docs/store/steam/listing/captions.tsv)、[四語文案](../../../docs/store/steam/listing/)。

| 分鏡 | 實機來源與重製方法 |
|---|---|
| dive.json | trailer/run.py 烘焙固定種子 42 的物理回放，按分鏡鏡位取一格。使用 ultra、DPR 1、HUD 關閉。01–03 為外部攝影機，05 為機載視角。纜線圖使用 P1 樁的預纏繞場景。 |
| wide.json | 同一個導管架場址，原生 3840×1240 捕捉無字 hero。無損原圖位於 output/store/library-hero/hero.png。 |
| ui.json | 04 與 11 用效能工具已驗證的機載定姿回放，等場景模型載入後再拍沉船與珊瑚礁。06 以錄製時鐘拍甲板下水。其餘鏡頭在 Steam edition 的瀏覽器介面重走玩家流程，保留所介紹的介面。選單可選的最高檔為 high，潛航錄製使用 ultra。 |
| art.json | 膠囊指定來源圖、尺寸與裁切中心（水平與垂直）。照片與標題分區，保留自然水體色調，字標用安全橘作識別。背景與 hero 供平台疊字。 |
| symbols.svg | 成就符號逐一對照 desktop/steam/achievements.json 的 event，輸出檔名採 Steam API 名稱。 |

單一介面鏡頭可用 `python simulator/tools/store_shots/ui.py 09-results` 重拍。08 從已解鎖序章的存檔狀態進入自由潛水，以實際快門收錄圖鑑。09 用玩家按鍵飛完水池序章才擷取結果。10 連入一個標準映射的虛擬手把。12 透過同一手把 API 實際推動搖桿，等遊戲切換成搖桿操作提示後擷取開場。即時操控的計時、分數、魚群與粒子會因機器而異。

`python simulator/tools/store_shots/art.py` 從已拍攝的截圖與無損寬幅畫面重建膠囊、圖示及聯絡表。header、small、main、vertical 同時提供指定尺寸與商店規格文件所列雙倍尺寸（檔名 -2x）；library-header 單獨輸出。library-logo 為 1280 px 寬透明 PNG。每張成品上限 2,000,000 bytes。

效能說明依 [profiling 記錄](../../../docs/design/performance/README.md)。UHD 620 為目標筆電，該報告的實測環境是 SwiftShader。10 GB 是安裝空間預留值。短描述以 Unicode 字元含空白與標點計數。

另依商店規格文件產生兩張 Steam 用戶端圖示。使用 Node 22+ 匯入遊戲機庫實際使用的 Model R 符號，輸出 512×512 捷徑 PNG 與 184×184 清單 JPG。圖中只有符號。
