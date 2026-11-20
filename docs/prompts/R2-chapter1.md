# R2：第一章（港口）拉到開場水準（Codex）

> 先完整讀 `docs/prompts/R0-common.md`。**等 R1 合併進 main 後再開始**（要用 `story/beat_director.js`）。
> 分支 `task/R2-chapter1`。

## 背景

第一章的草稿 PR #113（分支 `cursor/p3-chapter1-work-orders-4907`：雷射尺、評級、LOTO、大事件）停在 11/17。
第一章四關見 `docs/story/mission-map.md`（C1-1～C1-4，`harbor_inspection`、`hull_inspection`、`sonar_search`）。

## 要做的事

1. 合併 #113 的分支，讀它的 PR 描述與審查評論，吸收工具（雷射尺、評級 UI、LOTO 確認）；完成後註明「取代 #113」。
2. 四關全部改用劇情導演，逐關對照開場標準八條。每關要有：
   - 開場鏡頭＋地點字卡（港名用虛構名，見 bible §2.2）；
   - 一個客戶或船員角色的需求（葉理等，見 bible §3），讓玩家知道為什麼要做這件事；
   - **一個用既有物理做的轉折**，建議：C1-1 低能見度 1.5 m 要靠近又不能撞；C1-2 船殼附近有推進器吸流（用洋流場）、
     LOTO 沒確認就不能靠近；C1-3 聲納找到三個回波，只有一個是目標；C1-4 交班前趕時間，纜線繞樁。
     每個轉折都要寫場景資料讓它**可靠發生**，並附伺服器單元測試證明（照 `simulator/tests/test_cold_open.py` 的寫法）。
   - 收尾：報告卡（照片、量測、評級）＋角色評語＋獎牌（bible §8）。
3. 第一章結束：章節收尾卡，接第二章章節卡。

## 驗證

- 每關一支瀏覽器 smoke（可共用一支有參數的腳本），腳本駕駛飛完、每段截圖，連跑兩次通過。
- 加跑：`browser_campaign_smoke browser_career_smoke browser_results_smoke`。
- 截圖放 `docs/design/chapter1-r2/`，每關一張聯絡表。
