# M3：小艇尾板下水

本任務依擁有者 2026-11-15 指示，為 YX Model R 的近岸、港內與風場委託增加可選的小艇尾板下水。
基底 main；交付 draft PR「M3: 小艇尾板下水（CC0 掃描材質）」。

- 照片僅供對照，不進入程式、貼圖或提交，不投影、不重現照片品牌；使用既有載具模型。
- **船身幾何自建**（已確認無授權可用的寫實小艇模型）；材質用 Poly Haven／ambientCG CC0 掃描
  （甲板止滑板、柚木、鏽蝕、船漆）；救生圈／浮標用 Poly Haven CC0 模型；來源寫入
  `simulator/viewer/models/CREDITS.md`。
- 日光、海面、風場直接沿用 main，不另建第二套地平線。
- 白色船體、柚木尾板、梯子、兩側艙蓋、雙機停放節點、捲纜、防磨護套與安全掛繩。
- 雙手提機架、放入水中、水面漂浮與放纜。
- 小艇 ≤60k 三角形、預設 GPU 貼圖 ≤24 MiB；meshopt＋WebP；可重建、不提交 .blend。
- 新模式以參數選用，預設不變，後端物理不變；提供選單相機錨點與委託選用表。
- 完整 Python／Node 測試，以及 menu、HUD、procedure、camera browser smoke。
- 附模擬器內俯視、四階段與浮纜截圖、資產報告與授權。

實作、重建、證據與限制：[交付報告](../design/support-assets/swim-platform/README.md)。
