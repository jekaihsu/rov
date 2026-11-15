# G7：沉船模型

將 `wreck_survey` 方塊替換為原創 40–60 m 近海貨船或漁船：半埋、側傾 10–20°、斷裂或甲板坍塌，
包含開口外板、肋骨、舷窗、絞車、倒伏桅杆、錨鏈、纏繞繩網與分帶鏽蝕／附著。

- 三級 LOD 三角形上限 150k / 50k / 10k；貼圖 GPU 記憶體預設 ≤32 MiB、高畫質 ≤96 MiB。
- 自製資產與貼圖，無商標或特定船隻複製；glTF-Transform meshopt + WebP。
- 無頭 Blender 建置腳本與既有打包流程；Korean Castle 同格式、同工具距離場。
- 輸出可映射 `world.SnagFeature` 的勾纏清單，不重複既有手放物件。
- 最小情境整合，四個巡檢目標保持可達；變動與假設明列。
- Python 全套、Node 全套及 browser_smoke / observation_smoke / browser_tether_smoke 通過。
- 同機位資產比較、real 機載開關燈圖與資產報告。

實作與驗證記錄：[沉礁資產文件](../design/scenes/chenjiao/README.md)。
分支 `task/G7-wreck-model`；draft PR「G7: 沉船模型」。
