# H5：實測資料分析工具

目的：讓 X1 量測清單的階躍／鬆桿、定深／定向及纜線資料能離線分析。
基底 main；分支 task/H5-x1-sysid；只產生建議，不改 vehicles.py 現值。

交付：own/ 資料規範、固定種子的合成範例、tools/sysid/ 分析與匯入器、PNG 與 JSON 報告、
已知參數誤差 <5% 的 unittest。獨立推力秤量解除附加質量與推力的尺度退化。

驗收：`cd simulator && python -m unittest discover -s tests`；draft PR 附合成報告。
限制與待量測項目詳見 `docs/reference/own/README.md`。
