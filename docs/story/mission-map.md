# 第一版任務對應表（序章～第二章）

對照 `research_notes/遊戲設計/real_rov_jobs_missions.md` §6 與既有情境 key。  
**不發明模擬器做不到的玩法**；需新功能者標在「缺口」欄。

情境白名單（本版）：`tutorial_pool`、`open_water`、`harbor_inspection`、`hull_inspection`、`sonar_search`、`aquaculture_pen`。

| 遊戲關卡 | 研究表 # | 標題 | 情境 | 既有 campaign 參考 | 缺口／新功能 |
|---|---|---|---|---|---|
| P1 | #1 | 水池檢查潛 | `tutorial_pool` | `prologue.json` | 預潛閘門若未全接，沿用現有解鎖流程 |
| P2 | #2 | 開放水域熟悉 | `open_water` | 無獨立 story JSON | 4 檢查點目標需 mission 節點；場景已有 |
| P3 | #3 | 碼頭第一張工單 | `harbor_inspection` | `harbor.json` | Level I 覆蓋率計分（呈現層）；纜線同側規則可先用張力／繞樁懲罰近似 |
| C1-1 | #4 | 碼頭 Level II | `harbor_inspection` | 可視為 harbor 變體 | **低能見度 1.5 m**（`environment`）；**雷射尺量測 UI**；軟／硬附著選項 |
| C1-2 | #5 | 貨輪船殼評級 | `hull_inspection` | `hull.json` | niche 分區模型／評級 0–4 UI；**LOTO 確認步驟**（對話或閘門） |
| C1-3 | #7 | 港內掉落物 | `sonar_search` | 無 story JSON | 聲納格網＋影像確認已有基礎；**夾爪掛繩**若無則改「標記交潛水員」 |
| C1-4 | #8 | 交班前趕工複查 | `harbor_inspection` | `harbor_signoff.json` | **同角度重拍**比對（可先用站點近似）；大事件過場為呈現層 |
| C2-1 | #9 | 網衣巡檢 | `aquaculture_pen` | J1 場景 | 環繞／破洞拍照已有方向；時鐘方位回報 UI |
| C2-2 | #10 | 死魚回收 | `aquaculture_pen` | J1 `pen_recover` | 夾爪＋收集籃；載具 Model V 或 R＋爪 **待決** |
| C2-3 | #9 緊急變體 | 破網逃魚 | `aquaculture_pen` | — | 動態優先破洞；魚群「逃」可先對白＋既有魚群；**堵網道具**若要做＝新功能（可砍） |

## 第一版刻意不做

| 研究表 # | 原因 |
|---|---|
| #6 擱淺後螺槳 | 需 **NEW 船尾細部**場景；標為第二章後／第一章 DLC |
| #11 颱風後錨繩 | 需繫泊路徑與近水面浪；改為自由合約候選 |
| #12 起 | 第三～六章，非搶先體驗範圍（game-plan §10） |

## 獎牌與中止（全關共通）

對齊研究 §5：銅＝可用報告；銀＝時間或纜線門檻；金＝零接觸／證據全合格；中止＝安全撤離＋部分報告，劇情可推進。

## 舊「潮間帶」章節

`offshore`／`reef`／`wreck`／`finale` 不在本版主線；故事聖經改 YX 後，舊台詞角色名（阿禾等）以 `bible.md` 對照表汰換，實作另開內容 PR。

## K1 正篇續接（劇本規劃）

| 章／關 | 研究與現有素材 | 本次劇本交件／待製作內容 |
|---|---|---|
| 三 | 公共服務 #12–14、既有風場倒敘 | 水庫與搜證工單沿研究表；用班簿接回風場實際結果。 |
| C4-1／C4-2 | 海纜目視、聲納後影像確認 | 斷端與拖痕比對、外圍物件原位照；需海床物件及交件畫面。 |
| C5-1／C5-2 | 修復第二視角、海床複查 | 通道與支承狀態，甲板及岸測由其他班組負責；需修復前後場景與停工演出。 |

逐關見[第三章](chapters/chapter3.md)、[第四章](chapters/chapter4.md)、[第五章](chapters/chapter5.md)。第六章以後的職涯或自由合約不影響本主線在第五章收束。
