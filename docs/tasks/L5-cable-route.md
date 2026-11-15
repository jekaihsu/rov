# L5 海底電纜場景

分支 `task/L5-cable-route`，基底 main。新增職涯海纜章節可使用的 `cable_survey` 場址；
不改職涯解鎖、既有載具物理或 SDK 控制語意。

交付：300 m 含埋設狀態的中心線、六種區段、四種異常、50 m 標牌、同源海床與碰撞、
三個任務目標、無頭 Blender 固定種子建置、meshopt＋WebP、CC0 授權、低畫質材質合併、
資產預算與真實模式機載截圖。LOD0 ≤200k、貼圖 ≤32 MiB。

驗證：完整 Python 與 Node 測試、場景一致性、browser_smoke／observation_smoke／
browser_tether_smoke／browser_menu_smoke，以及 browser_cable_onboard 全區段與異常拍攝。
成果、假設及未完成美術驗收見 [場景文件](../design/scenes/cable_route/README.md)。
