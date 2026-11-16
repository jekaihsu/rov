# 模擬類／職業模擬遊戲的「遊戲層」設計研究，及 ROV 模擬器建議方案

閱讀標記：Fetched = 讀過原文頁面；Snippet = 搜尋摘要，未全文核對；推算 = 依公開資料推論；〔未查證〕= 本次沒有找到來源，憑一般認知，採用前要再查。日期基準：2026-11。

範圍：只談「遊戲層」，也就是選單、進度、經濟、職涯與故事、上手、回饋手感（juice）、設定與社群。物理與 SDK 語意不動（AGENTS.md）。超出真機能力的項目一律要註冊為 fidelity 項目，在 `real` 預設為關。

---

## 0. 結論先講

1. **成功的模擬遊戲都把寫實留在「動作」本身，好玩放在「動作的意義」上**。PowerWash 的噴水、ETS2 的開車、Hardspace 的切割都不簡化。遊戲層提供的是：清楚的目標（工單）、看得到的進度（星數、等級、證照）、拿到錢後能換到「讓同一件事做得更好」的工具，以及低壓力（不太會失敗，或失敗代價可控）。
2. **證照式進度是最貼合本案的骨架**。MSFS 2024 的證照要在模擬器裡實際考核（checkride），ETS2 的技能點用來開放 ADR、易碎等工作類型，Hardspace 有 30 級認證。真實 ROV 業界本來就有 Trainee → Pilot/Tech Grade II → Grade I → Senior → Supervisor 的階梯，加上以日誌累積時數的文化，等於現成的進度系統。
3. **經濟只賣「真實設備」與「外觀」**。可買的升級全部是真實 ROV 確實會加裝的配件，例如更亮的燈、雷射比例尺、成像聲納、DVL、抓手、CP 探棒、UT 測厚、USBL。這些只「開放能力」，不改物理參數。外觀用貼紙、塗裝、工作船旗幟。
4. **Steam 上的 ROV 利基幾乎空白，但口碑門檻已經存在**。subROV（約 90% 好評，樣本小）和 vROVpilot: TITANIC（86%，164 則）都證明玩家願意買單。評論的主要抱怨是上手難（按鈕太多）、節奏慢、內容少，而不是太寫實。Deep Diving Simulator 則因控制差、沒有教學、「不是真模擬」而落到 Mixed。
5. **最常見的負評來源是 bug、刷錢（grind）、說明不足與無法跳過的劇情**，見 MSFS 2024、Hardspace、Stormworks。P0 應該優先投資在「穩、說得清楚、可跳過」。

---

## 1. 參考作品逐一拆解

> 評分數字以抓取當下為準，會隨時間浮動。

### 1.1 PowerWash Simulator（1 與 2）

- **核心循環**：接工單 → 清洗場景（每個部件洗淨會有「叮」聲並打勾）→ 收錢 → 買更好的噴槍、噴嘴、延長管、清潔劑 → 接更大的工單（Snippet：[GameLuster](https://gameluster.com/review-powerwash-simulator-scrubs-up-well/)、[Geeks Under Grace](https://www.geeksundergrace.com/gaming/review-powerwash-simulator/)）。
- **進度**：每個工作有 5 顆星，隨清潔百分比填滿；累積星數解鎖新工作，生涯總星數解鎖更強的機器（Snippet）。
- **經濟**：一種貨幣。升級是「工具」，直接改變效率，評論認為回饋很實在（Snippet）。
- **故事**：用手機簡訊交代，可以完全忽略（Snippet）。
- **寫實與好玩怎麼平衡**：不計時、沒有水量限制、沒有生命值，幾乎不會失敗（Snippet）。
- **UX**：剩餘髒污高亮（髒污偵測），部件完成時有即時回饋，百分比進度條一直在畫面上〔未查證細節〕。
- **評價**：好評是放鬆、上癮、升級有感。負評是重複、大型關卡單調、後期關卡必須 100% 完成才解鎖（Snippet）。PowerWash Simulator 2（2025-10）約 91% 好評，Metacritic 82；評論說它是「精修而非突破」，新增的基地裝修被評為多餘（Snippet：[GameMeca](https://www.gamemeca.com/en/view.php?gid=1767495)、[Vaporlens PWS2](https://vaporlens.app/app/2968420/power_wash_simulator_2)）。
- **對本案的啟示**：檢查任務的「覆蓋率」可以直接做成 PowerWash 式的完成度條。例如樁柱每個面拍到、每段管線都看過就打勾。這是真實的檢查證據，同時也是最好的 juice。

### 1.2 Euro Truck Simulator 2／American Truck Simulator

- **核心循環**：在工作市場（Job Market）選貨 → 開車送達 → 拿錢與經驗 → 升級與擴張公司。
- **進度**：等級給技能點，點在 ADR（危險品，分類別）、長途、高價值、易碎、準時、節能等項目。技能決定「能接哪一類工作」與報酬（Snippet：[Truck Simulator Wiki](https://trucksimulator.wiki.gg/wiki/Skills)、[Gamepressure](https://gamepressure.com/eurotrucksimulator2/skills/ze45e0)）。初期只給 250 km 內的工作（Snippet）。
- **經濟**：先當「受雇司機」開公司的車（Quick Job），之後買車、貸款、買車庫、雇司機，司機也有自己的技能成長（Snippet：[racinggames.gg](https://racinggames.gg/article/how-to-hire-train-and-profit-from-fleet-drivers-in-euro-truck-simulator-2-and-ats)）。外觀改裝（塗裝、燈具、內裝配件）是重要的花錢處〔未查證細節〕。
- **社群**：World of Trucks 平台提供相片工作室（photo mode）與截圖上傳、社群活動（全服共同送貨目標），還有個人頭像與車牌（Fetched 摘要：[SCS World of Trucks](https://scssoft.com/projects/world-of-trucks)）。另有大量 mod〔未查證細節〕。
- **對本案的啟示**：(a) 先受雇、後自營。(b) 技能／證照開放「工作類型」，不提升數值。(c) 罰款與損壞造成的扣款有明確明細。(d) 相片模式與社群目標。

### 1.3 Microsoft Flight Simulator 2024（Career Mode）

- **進度**：證照路線依序是 PPL → CPL → 儀器飛行評等（IR）→ ATPL，另有噴射機評等、多引擎評等等。每一級都是在模擬器裡實際考核（PPL 考起降航線，IR 考雲中一次儀器進場）。部分證照要求最低時數或完成指定任務；PPL 之後是非線性的樹（Fetched：[SimTuts 職涯指南](https://simtuts.com/guides/msfs-2024-career-mode-guide)）。
- **聲望**：按類別分開計算（叢林、包機、貨運、航空公司）。每趟都會就落地品質、導航、計畫遵守、速度控制、滑行打分，聲望決定接得到什麼工作（Fetched）。
- **經濟**：報酬 = 距離 × 複雜度 × 載重 × 聲望倍率 + 表現獎金。修理與燃油是主要成本。「受雇」用雇主的飛機，安全但錢少；「自營」用自己的飛機，風險與成本都比較高。之後可以開公司、雇機組（Fetched；另見 [msfsaddons FAQ](https://msfsaddons.com/msfs-2024-faq/career-mode/)）。
- **評價**：好評是「讓模擬器有了目的」「很適合新手學不同機型」（Snippet：[Shacknews](https://shacknews.com/article/141437/microsoft-flight-simulator-2024-impressions)、[The AU Review](https://www.theaureview.com/games/microsoft-flight-simulator-2024-review/)）。負評包括：bug（落地後被判墜機、任務觸發失效）、前期經濟殘酷、修理費懲罰性、不能中途存檔、刷錢、說明不足，以及職涯只開放部分機型（Snippet：[Vaporlens](https://vaporlens.app/app/2537590/microsoft_flight_simulator_2024)、[SimTuts](https://simtuts.com/guides/msfs-2024-career-mode-guide)）。Steam 整體約 60% 好評，但上市初期的負評主要來自登入與下載排隊（Snippet）。
- **對本案的啟示**：「考照 = 在真實設定下完成一次標準檢測流程並達到門檻」是最貼切的範本。必須避開它的錯誤：判定錯誤會直接毀掉信任，所以判定要保守、可回放、可申訴（重看）。前期不能讓玩家破產。

### 1.4 Farming Simulator 25

- **核心循環**：耕作、收成、出售、買設備或土地。合約（替鄰居農場代工）是新手不需要土地就能賺錢的入口（Snippet：[Epic 新手指南](https://store.epicgames.com/news/prepare-to-plow-with-our-farming-simulator-25-beginners-guide)、[Gamepressure](https://www.gamepressure.com/farming-simulator-25/basics/z0116a7)）。
- **設定**：可調經濟難度、起始資金、貸款、是否從零開始，以及季節生長等規則（Snippet）。
- **真實設備**：大量真實品牌授權機具是核心賣點。本案依 AGENTS.md 品牌規則不能這樣做，只能用通用設備名。
- **評價**：上市初期合約系統有 bug（Snippet：[Gamepressure 新聞](https://www.gamepressure.com/newsroom/watch-out-for-contracts-not-working-in-farming-simulator-25-fs25/z4753e)）。
- **啟示**：合約板是新手的安全墊；開局時可選「新手（有錢、有基本設備）／標準／從零開始」。

### 1.5 Train Sim World 5

- **上手**：免費 Starter Pack 附「訓練中心」，是專門教基礎操作的場景。新車第一次進駕駛室會跳出教學。教學可隨時從路線選單重玩（Snippet：[Dovetail 支援](https://support.dovetailgames.com/hc/en-us/articles/35574942592658-How-to-set-up-Train-Sim-World)、[TSW 新手指南](https://live.dovetailgames.com/live/train-sim-world/articles/article/tsw-beginnersguide)）。
- **輔助**：開局選 Beginner／Standard／Expert，各自對應一組輔助（自動連結、提示、AI 車長行為），之後可在設定裡隨時改（Snippet）。
- **模式**：Off the Rails 讓任何車開在任何路線（沙盒），另有服務時刻表模式與情境任務（Snippet）。
- **啟示**：「開局一題問難度 → 對應一組可逐項覆寫的輔助」正好對應我們的 fidelity preset（`real`／`assisted`／`custom`）。教學必須可重玩。

### 1.6 Dredge

- **核心循環**：白天出海捕魚 → 回港賣魚 → 升級船（引擎、燈、網、貨艙格數）→ 去更遠、更深的海域。入夜後有恐慌值，持續施加壓力（Snippet：[NME](https://www.nme.com/reviews/dredge-review-3418763)、[GamesRadar](https://gamesradar.com/dredge-review)）。
- **進度**：船體升級擴充背包格數（俄羅斯方塊式背包）。每一級升級都直接打開新區域或新漁法。
- **故事**：淡淡的懸疑主線靠 NPC 委託推進，有圖鑑（Snippet）。
- **評價**：好評是循環黏人、升級化解早期摩擦、房貸給了目標但不催人。負評是循環後期不再演變、錢後期變得無用，以及移動「升級前很拖、升級後太順」（Snippet：[Slant](https://www.slantmagazine.com/games/dredge-review-stuck-in-the-shallow-end/)、[OpenCritic](https://www.opencritic.com/game/14348/dredge/reviews?page=2)）。
- **啟示**：(a) 燈光升級「打開新區域」，對應我們把濁水、深水、夜潛分級開放。(b) 圖鑑。(c) 後期要有花錢的地方，例如公司、船隊、外觀，否則錢會失去意義。

### 1.7 Subnautica

- **進度**：用掃描器掃描殘骸碎片取得藍圖，大多數裝備要掃 2–3 個碎片。進度和「能到哪裡」綁在一起，每張新藍圖就是一次可去範圍的擴張（Snippet：[thegameswiki 藍圖與掃描](https://thegameswiki.com/subnautica-2/wiki/blueprints-and-scanning)、[PCGamesN](https://www.pcgamesn.com/subnautica-2/blueprints)）。
- **上手**：PDA 語音與資料庫條目取代教學關卡，劇情藏在殘骸與 PDA 紀錄裡〔環境敘事的分析未找到一手來源〕。
- **啟示**：「拍照／掃描 → 圖鑑條目 → 解鎖」可以搬過來，但要改成真實語意。ROV 不會靠掃描得到藍圖，所以改成「拍到合格證據 → 完成調查項目 → 解鎖研究單位的委託」。殘骸調查章節（T12 第四章）適合用環境敘事。

### 1.8 Stormworks: Build and Rescue

- **職涯**：起初零件與建造空間有限，靠救援、消防、運送任務賺錢並解鎖零件；Classic 職涯另需研究點數（Snippet：[Wikipedia](https://en.wikipedia.org/wiki/Stormworks:_Build_and_Rescue)、[Cubed3](https://cubed3.com/preview/740/1/stormworks-build-and-rescue-pc.html)）。
- **評價**：Steam 約 41,000 則 Very Positive，但評論普遍認為職涯淺、多年需要重做，強項在建造與工作坊（Snippet：[Steam 討論](https://steamcommunity.com/app/573090/discussions/0/6406956248969128661)）。
- **啟示**：沙盒強、職涯弱也能成功，但職涯弱會被點名。Workshop（自訂場景與任務）是長尾的關鍵。

### 1.9 Hardspace: Shipbreaker

- **核心循環**：以班次為單位拆解太空船 → 把零件分送到正確的回收口 → 錢拿去還債（開局欠約 12.5 億）（Snippet：[Wikipedia](https://en.wikipedia.org/wiki/Hardspace:_Shipbreaker)、[gameplay.tips](https://gameplay.tips/guides/7900-hardspace-shipbreaker.html)）。
- **進度**：完成工單得到認證等級（共 30 級），等級解鎖更大的船和工具；LYNX Token 用來買升級（Snippet：[Worthplaying](https://worthplaying.com/article/2021/5/6/news/125785/)）。
- **經濟**：工具租金、居住費、克隆費（死亡成本）、維修費持續扣款，用荒謬的公司剝削來作為諷刺（Snippet）。
- **評價**：Steam 約 89% 好評。好評是物理拆解的滿足感、氛圍、音樂。負評是重複，以及劇情說教且無法跳過；也有評論說升級只是加數值，不讓人覺得被改變（Snippet：[Vaporlens](https://vaporlens.app/app/1161580/hardspace_shipbreaker)、[Steam 評論](https://steamcommunity.com/id/maudish/recommended/1161580/)、[PC Gamer](https://www.pcgamer.com/hardspace-shipbreaker-review)）。
- **啟示**：(a)「藍領職人」的認同感可以成為整個作品的情緒基調，與 ROV 工作很像（受天候左右、工時長、責任大）。(b) 劇情一定要能跳過。(c) 升級應該帶來「新的做事方式」（例如有了聲納可以在零能見度找目標），而不是 +10%。

### 1.10 Lawn Mowing Simulator

- **職涯**：建立公司（名稱、Logo、配色），接合約、擴建總部、買割草機、雇員工。聲望來自完成合約、少扣分與打廣告；經驗升級後可雇更多人、貸更多錢（Snippet：[TheSixthAxis](https://www.thesixthaxis.com/2021/08/09/lawn-mowing-simulator-review/)、[Pure Xbox](https://www.purexbox.com/reviews/xbox-series-x/lawn_mowing_simulator)）。
- **評價**：GameSpew 稱「上癮得不合理」。Kotaku 批評計時合約容易失敗，扣分（超速、割錯高度、漏草）很嚴（Snippet：[Kotaku](https://kotaku.com/1847496842)）。
- **啟示**：公司 Logo 和配色是便宜又討喜的自訂；罰則要明確，並讓玩家事前就看得到標準。

### 1.11 Tow Truck／Towing 類職業模擬

- 沒有找到具代表性、口碑好的拖車職涯作品。Towtruck Simulator 2015 是 Very Negative（98 則）（Snippet：[Steam](https://store.steampowered.com/app/273760)）。可以當反例：同名的「XX Simulator」量產作品，常見的低分原因是物理差、內容薄〔推算〕。

### 1.12 Kerbal Space Program（Career）

- **三種資源**：資金（造船發射）、科學（解科技樹）、聲望（決定合約品質）。合約失敗或逾期會扣資金與聲望；另有「策略」可在資源之間轉換（Snippet：[KSP Wiki Career](https://wiki.kerbalspaceprogram.com:443/wiki/Career)、[Strategies](https://wiki.kerbalspaceprogram.com/wiki/Strategies)）。
- **評價**：科技樹太快被解完，後期科學無用（Snippet：[KSP 論壇](https://forum.kerbalspaceprogram.com/topic/146756-disconnect-science-from-tech-research/page/2)）。社群模組 Career Reimagined 改成「里程碑合約解鎖科技節點」（Snippet：[SpaceDock](https://spacedock.info/mod/4249/Career%20Reimagined)）。
- **啟示**：資源種類不要太多；解鎖應該綁「做到了某件事」（里程碑），而不是單純囤積貨幣。

### 1.13 DCS World（訓練）

- **訓練**：每架模組附互動訓練任務（座艙內逐步指示），之後是 Instant Action 短任務與任務編輯器的重複演練；社群自製訓練任務補足缺口（Snippet：[Heatblur F-4 手冊](https://f4.manuals.heatblur.se/dcs/training_missions.html)、[FlyAway](https://flyawaysimulation.com/ask/answers/best-dcs-world-training-missions-resources/)）。
- **輔助**：輔助分散在遊戲設定、任務選項與各機特殊設定；多人伺服器或任務可以強制覆寫玩家的本地輔助（Snippet）。建議一次關一個輔助（Snippet）。
- **評價**：上手門檻極高，論壇長期有「讓 DCS 對新手更友善」的討論（Snippet：[DCS 論壇](https://forum.dcs.world/topic/239915-making-dcs-more-accessible-to-new-players/page/10)）。
- **啟示**：(a)「伺服器／任務強制擬真設定」直接對應「考照與內部訓練一律強制 `real`」。(b) 互動教學會隨版本更新而過時，要有自動化測試保住（T12 已要求序章可自動跑完）。

### 1.14 水下／ROV／潛水相關作品

| 作品 | 類型 | 遊戲層 | 口碑與重點 |
|---|---|---|---|
| **subROV: Underwater Discoveries**（2022-12 EA，$19.99） | 全海深科研 ROV | 研究船開到潛點 → 布放 ROV → 測繪、採樣、掃描生物、勘查沉船 → 資料進圖鑑（Gallery）；從 trainee 升到 Dive Master；設備有 AI 掃描、機械臂、感測器、Lander、沉積物取樣管 | 90% 好評（63 則）（Fetched：[Steam](https://store.steampowered.com/app/1648760)）。好評是不計時、順序自由、圖鑑有教育性。負評是控制複雜、教學冗長、早期任務慢且重複、ROV 移動慢（Snippet：[GameLuster](https://gameluster.com/review-subrov-underwater-discoveries-roving-in-the-deep/)）。考慮中的功能有甲板吊車、測試水池基地、損壞模型；2026-05 公告開發延遲 |
| **vROVpilot: TITANIC**（2024-12 EA，$24.99） | 沉船 ROV | 兩台 ROV，引導式掃描任務（錨吊車、救生艇吊架），約 20 分鐘，之後可自由探索；第一／第三人稱；計畫加入機械臂、推進器升級、生物掃描與更多任務 | 86% 好評（164 則）（Fetched：[Steam](https://store.steampowered.com/app/3397800)）。證明「真實地點 + 掃描任務」本身就有吸引力；內容極少仍能拿到好評，但頁面顯示超過 18 個月沒有更新 |
| **Deep Diving Simulator**（2019） | 休閒潛水 | 探索、海洋生物 | Mixed（約 59%）。負評是「是街機不是模擬」、控制差、沒有手冊與教學（Snippet：[Steam](https://store.steampowered.com/app/990030)、[GOG](https://www.gog.com/en/game/deep_diving_simulator)） |
| **Silent Depth** | 二戰潛艇模擬 | 長程巡邏 | Mixed（77 則），利基、粗糙（Snippet：[Steam](https://store.steampowered.com/app/846050)、[StatelyPlay](https://statelyplay.com/2016/12/14/review-silent-depth/)） |
| **Under the Waves** | 1970 年代北海飽和潛水員的敘事冒險 | 以敘事為主，有潛水器與修理工作 | Mostly Positive（約 1,500 則）；批評技術問題與 glitch（Snippet：[Steam](https://store.steampowered.com/app/1975440)、[Push Square](https://www.pushsquare.com/reviews/ps5/under-the-waves)）。證明離岸海事工作題材有敘事吸引力 |

**利基判讀〔推算〕**：目前沒有任何作品同時做到「真實操控 + 職涯經濟 + 纜線 + 好上手」。兩款 ROV 作品都靠「真實感、真實地點」拿到好評，評論量卻很小（幾十到一百多則），代表核心受眾小。要擴大客群，就要借 PowerWash／ETS2 式的職涯與放鬆感，吸引「職業模擬」這個大受眾。

---

## 2. 「寫實模擬 + 遊戲」的共通模式

| 模式 | 範例 | 做法重點 | 本案對應 |
|---|---|---|---|
| 可選輔助、逐項可覆寫 | TSW5 Beginner/Standard/Expert；DCS 遊戲設定與各機設定；MSFS 輔助選單 | 開局一題定預設，之後逐項可改；伺服器或任務可以強制 | fidelity preset。考照與內部訓練強制 `real` |
| 難度／經濟滑桿 | FS25 經濟難度、起始資金、貸款 | 只調經濟與規則，不碰物理 | 生涯開局選項：起始資金、維修成本、天候嚴苛度（只影響合約出現機率，不改洋流物理） |
| 證照式進度 | MSFS 證照與評等＋實機考核；ETS2 技能開放貨物類型；Hardspace 認證等級 | 證照開放「工作類型」，不加數值 | IMCA 式職等＋專項簽注（見 §5.2） |
| 合約板 | ETS2 Job Market；FS25 合約；MSFS 任務地圖；KSP 合約 | 顯示報酬、需求證照、時限、風險；可比較 | 合約板（見 §5.4） |
| 受雇 → 自營 → 公司 | ETS2、MSFS、Lawn Mowing | 先用公司裝備低風險起步，再自購裝備換高報酬 | 先當受雇駕駛，再成為自由接案者，最後經營小型 ROV 公司 |
| 真實設備升級 | Dredge 燈與引擎；PowerWash 噴嘴；Hardspace 工具 | 升級要帶來新玩法 | 只賣真實配件，開放能力（見 §5.3） |
| 相片模式 | ETS2 Photo Studio + World of Trucks 畫廊 | 暫停、自由相機、濾鏡、上傳 | 相片模式屬於「超出真機」，要註冊 fidelity 項目；任務用的「機載拍照」則照真實規格 |
| 日誌本 | MSFS 飛行日誌〔未查證細節〕；業界 ROV 日誌（IMarEST：建立 logbook 記錄駕駛時數與離岸天數） | 自動記錄時數與條件 | 個人 ROV 日誌，可匯出（內部訓練用） |
| 圖鑑 | subROV Gallery；Dredge；Subnautica | 收集慾、教育性 | 海洋生物、結構缺陷類型、沉船物件圖鑑 |
| 成就 | 幾乎所有作品；ETS2「每個城市都有車庫」 | 引導嘗試各種玩法 | Steam 成就（P0），內容以真實技能為主題 |
| 排行榜、每日／每週挑戰 | 〔本次未找到模擬類的具體實例來源〕 | 固定種子場景、同條件比較 | 每週固定條件挑戰（P2）；比的是檢查覆蓋率與平順度，不比速度 |
| 社群目標 | World of Trucks 社群活動 | 全服累積 | P2 |
| Workshop／Mod | Stormworks、ETS2 的長尾 | 場景與任務資料驅動 | T12 的 JSON 任務格式天然適合 Workshop（P2） |

---

## 3. 真實 ROV 產業職涯：可以照搬的結構

### 3.1 職等

- **IMCA C 005**（Remote Systems & ROV 能力保證與評估，最新 Rev 3.5，2025-04）是業界事實標準，定義各職等的能力要求；**R 002** 規範入門訓練課，且入門課本身不等於取得任何 C 005 職等（Snippet：[IMCA C 005](https://www.imca-int.com/resources/technical-library/document/3907f45c-c55b-ee11-8def-6045bdd2c7e3/)）。
- **IMCA 本身不發證**：IMCA 明言從未發過「IMCA Certification／Accreditation」，任何 ROV 技師能力證書也不應印 IMCA Logo（Snippet：[IMCA IN 1299](https://www.imca-int.com/information-notes/rov-technician-accreditation-guidance)）。**遊戲內不可宣稱「IMCA 證照」，也不可使用其標誌**，只能借用「職等名稱的一般用法」，並另取虛構的發證單位名稱。
- **IMarEST 職涯路徑**（Fetched PDF：[IMarEST ROV Pilot career pathway](https://www.imarest.org/asset/5ED67A8D-023F-4236-B678907060AC710A)）：
  1. **ROV Trainee／Apprentice**：協助資深人員、準備設備、例行保養、觀察作業。需要完成學徒或訓練課程，以及 BOSIET、HUET、急救等安全訓練。
  2. **Junior ROV Pilot／Technician**：在監督下操作較簡單的任務、協助排障、保養。升級條件是取得 Grade II、1–2 年受監督駕駛，並**開始建立日誌記錄駕駛時數與離岸天數**。
  3. **ROV Pilot／Technician（Grade II）**：獨立執行檢查、資料蒐集、修復。升級條件是取得 Grade I、3–5 年經驗，**以 Grade II 身分至少 100 駕駛時數 + 180 天離岸**。
  4. **Senior ROV Pilot（Grade I）**：帶領複雜任務、管理團隊。升級條件是取得 ROV Supervisor。
  5. **ROV Supervisor／Manager**（再往上是 Superintendent）。
- 實際徵才門檻的例子：Grade II 職缺要求至少 180 天離岸與 150 駕駛小時（Snippet：[OGV Energy 職缺](https://jobs.ogv.energy/job/rov-pilot-technician-51221)）。本專案的研究報告也有記錄「100 小時受監督飛行 + 180 天離岸」（`docs/reference/real-rov-research.md`）。

### 3.2 工作類型（以觀察級／輕作業級為主）

| 工作 | 真實內容 | 需要的設備或技能 | 遊戲化重點 |
|---|---|---|---|
| 船殼檢查 | 船底、螺槳、海底門檢查，評估附著與損傷；小型低成本 ROV 常用於快速船殼檢查（Snippet：[OST](https://www.oceansciencetechnology.com/feature/how-deep-trekker-rovs-enhance-offshore-inspections-maintenance/)） | 燈、相機、定深定向 | 新手工作。覆蓋率條（PowerWash 式） |
| 碼頭樁、橋墩檢查 | 垂直航次繞樁；航線間距依能見度決定（VideoRay SOP，見研究報告） | 雷射比例尺、CP 探棒 | 依 SOP 打分 |
| 養殖網箱檢查 | 檢查破洞、薄弱處、生物附著，繫泊檢查，推移死魚，環境採樣（Snippet：[DiveWorks](https://www.diveworks.com.au/aquaculture/)、[OST Aquaculture](https://www.oceansciencetechnology.com/suppliers/aquaculture-rov/)） | 抓手、強燈 | 找破洞，屬於限時的「搜尋」玩法；纜線容易勾網 |
| 離岸風場（單樁、導管架、海纜） | 施工前調查、基礎與海纜連接、定期檢查、除役；單樁的弧面鋼、斜坡拋石與洋流讓作業不容錯（Snippet：[Deep Trekker Offshore](https://www.deeptrekker.com/resources/offshore-operations)） | 強推力、DVL、成像聲納、UT 測厚 | 強流、平潮窗口，T12 第二章 |
| 管線、海纜調查 | 沿線目視與聲納檢查，記錄裸露、懸跨、損傷（Snippet：[Intertek](https://www.intertek.com/asset-integrity-management/underwater-rov)）〔管線檢查的飛行程序未找到公開 SOP〕 | 聲納、USBL、DVL | 長距離沿線，考纜線管理 |
| 搜索與回收 | 用聲納搜尋目標，掛回收繩（研究報告中的密西根湖案例：用第二台 ROV 以聲納 10 分鐘找回遺失的 ROV） | 成像聲納、抓手、USBL | 劇情事件 |
| 科研調查 | 生物普查、儀器布放與回收、採樣（subROV 的主題） | 機械臂、採樣器、雷射比例尺 | 圖鑑、委託 |
| 沉船勘查 | 考古與勘查記錄 | 全部 | T12 第四章 |

### 3.3 觀察級 ROV 可加裝的真實配件（升級商店的品項來源）

觀察／檢查級的典型配置是即時影像、靜態攝影、成像聲納、USBL 定位、CP 探棒、UT 測厚（Snippet：[ROV 一般定義](https://www.doc.surf/wiki/remotely-operated-underwater-vehicle)）。廠商目錄中的常見配件有：接觸式與近接式 CP 探棒、UT 測厚（附擺臂探頭座）、雷射比例尺、抓手與機械臂、切割器、USBL、掃描式或多波束成像聲納、DVL（Snippet：[VideoRay Pro 4 配件](https://kb.videoray.com/?p=230)、[Pro 4 Ultra 手冊](https://download.videoray.com/documentation/pro_4_ultra/html/accessories_manufacturer.html)、[Deep Trekker 配件](https://www.deeptrekker.com/products/underwater-rov/rov-add-ons)、[Hydromea EXRAY 規格](https://mfe-is.com/en_ca/hydromea-exray_technical-specifications/)）。**遊戲中一律使用通用名稱**，不使用以上品牌或型號（AGENTS.md 規則 8）。

---

## 4. Steam 頁面與第一小時

### 4.1 商店頁

- 主圖（capsule）要能一眼看出類型與調性，先以小尺寸 462×174 設計；點擊率低於約 3% 就該重做（Snippet：[Summer Engine](https://www.summerengine.com/ja/make-great-games/market-your-indie-game)、[Theory-Craft](https://www.theorycraftmarketing.com/the-complete-steam-marketing-guide-for-indie-developers-2026)）。
- Coming Soon 頁至少要在發售前 2 週公開，Valve 建議更早；Next Fest 每款遊戲只能參加一次，展期開始時 demo 必須已公開（Snippet）。展期中商店頁、主圖與預告片的影響比 demo 本身更大（Snippet）。
- 找不到市場的類型行銷救不回來，要先看標籤統計（Snippet：[How To Market A Game](https://howtomarketagame.com/courses/)）。
- **Steam 無障礙標示**（2025-06 上線）：開發者在 Steamworks 填問卷，結果出現在商店頁，也能被搜尋篩選；項目分為遊戲性、視覺、音訊、輸入四類（例如字級、字幕選項、可調難度、隨時存檔）（Snippet：[Steamworks 文件](https://partner.steamgames.com/doc/accessibility_features)、[PC Gamer](https://www.pcgamer.com/gaming-industry/steams-store-now-lets-you-search-for-games-by-accessibility-features-like-narrated-game-menus-and-adjustable-difficulty-and-more-than-5-000-games-have-already-added-their-accessibility-details-to-the-database)）。**上架時要填。**
- 職業模擬的商店頁慣例〔推算，來自上述作品頁的觀察〕：第一張截圖或 GIF 就是「工作中的畫面」（PowerWash 前後對比、ETS2 駕駛艙）。描述會列出真實工作類型與裝備。ROV 作品的頁面強調「與專家合作」（vROVpilot）與「改編真實探勘」（subROV），本案可以強調「操作員訓練用的同一套物理」。

### 4.2 第一個 10 分鐘（綜合評論中的痛點與好評）

- **第 0–2 分鐘**：一題選擇（「我是新手／我開過 ROV／我是專業操作員」），對應 fidelity preset 與教學深度。參考 TSW5 開局難度，以及 Train Sim World 的訓練中心。
- **第 2–8 分鐘**：一次只教一件事，偵測到玩家確實做到才往下（T12 已規定）。subROV 被批評「按鈕到處都是、教學要重玩」，Deep Diving Simulator 被批評「沒有手冊與教學」，這兩點都要避免。
- **8 分鐘內一定要有第一次「收成」**：拍到第一張合格證據照、完成度條跳到 100%、收到第一筆工資與督導一句讚許。PowerWash 第一關幾分鐘內就能洗完一台車〔未查證確切時間〕。
- **第一個小時內要拿到第一個解鎖**（例如第一張專項簽注，或第一件可買的配件），並看見下一個目標（合約板上灰掉的高薪工作，標著「需 Grade II」）。這就是 ETS2 與 MSFS 的做法。
- 教學與劇情一律可跳過、可重玩（Hardspace 因為劇情無法跳過而被罵）。

### 4.3 玩家預期的設定項

依 Game Accessibility Guidelines，最常被抱怨的四項是重新映射、文字大小、色盲、字幕呈現（Snippet：[GAG Basic](https://gameaccessibilityguidelines.com/basic/)）。色盲支援應該改變特定指示物的顏色或形狀，不要套全螢幕濾鏡；HUD、選單與字幕最好能分別縮放（Snippet）。完整清單見 §5.8。

---

## 5. 收斂：本案建議的遊戲層設計

優先級：**P0** = Steam 上市必備；**P1** = 上市後第一波；**P2** = 長尾。「來源」欄指出該設計參考哪個作品。

### 5.1 核心循環

```
合約板選工作（需求證照、報酬、天候窗口、風險）
  → 出航前準備：選載具配置與配件、看簡報、檢查清單（T23 預潛流程）
  → 下水作業：真實操控、纜線、洋流、能見度
  → 交付成果：照片／影片證據、覆蓋率、量測值、報告
  → 講評：評分明細＋回放（T17）
  → 報酬：錢、日誌時數、聲望、簽注進度
  → 升級：買真實配件、考下一張證照、接更難的工作
```

| 項目 | 來源 | 優先 |
|---|---|---|
| 「接工作 → 完成 → 錢 → 更好的工具 → 更難的工作」主循環 | PowerWash、ETS2、Dredge | P0 |
| 任務完成度條：覆蓋率、待拍清單逐項打勾，同時也是真實的檢查證據 | PowerWash | P0 |
| 單次任務 5–15 分鐘，可中途存檔或撤收 | T12；MSFS 不能中途存檔而被罵 | P0 |
| 不太會「失敗」：失敗是「拿到較少錢與評價」，不是死亡或強制重來；載具遺失才是真正的重大事故 | PowerWash 的低壓力、Hardspace 的成本可控 | P0 |
| 自由潛水、沙盒模式（任何地點、任何載具，不計分） | TSW Off the Rails、vROVpilot 結束後的自由探索 | P0 |

### 5.2 進度：認證階梯（對應真實職等）

**原則**：證照**開放工作類型與責任**，不提升操控數值。考照（checkride）一律在 `real` 預設下進行，參考 DCS 的「任務強制設定」；輔助開啟時一般合約照常付錢，但**時數記為「輔助時數」，不計入考照門檻**。這是給 Steam 玩家的誠實標示，也讓內部訓練版的日誌有意義。

| 遊戲內職等（虛構發證單位） | 真實對應 | 開放的工作 | 考照方式（實際操作） | 優先 |
|---|---|---|---|---|
| 0. 學員（Trainee） | ROV Trainee／Apprentice | 水池、港內船殼（受監督：督導可代為接管） | 序章水池教學 | P0 |
| 1. 初級駕駛（Junior Pilot） | Junior Pilot/Tech | 港灣樁柱、船殼、養殖網箱 | 港區 checkride：依 SOP 繞樁，碰撞與纜線張力在門檻內 | P0 |
| 2. 駕駛技師 Grade II | Pilot/Tech Grade II | 離岸風場、管線短段、科研委託 | 強流定點、纜線管理、能見度差時的作業。需要 N 小時 `real` 時數（數字暫定，**不可宣稱等於業界門檻**） | P0 |
| 3. 駕駛技師 Grade I | Pilot/Tech Grade I | 夜潛、深水、搜索回收、沉船 | 綜合 checkride，含故障注入（T22） | P1 |
| 4. 資深駕駛（Senior） | Senior Pilot | 帶隊（多人時擔任主駕）、指派 AI 隊員 | 多人或 AI 協作任務 | P1 |
| 5. 督導（Supervisor） | ROV Supervisor | 經營公司、評核他人（連到教官模式 T17） | 規劃與決策題：何時中止作業 | P2 |

**專項簽注**（MSFS 評等 + ETS2 技能，P0／P1）：每項都是一個短課程加一次考核，開放特定合約類別。

- 聲納判讀（P0）
- 機械臂、抓手操作（P0）
- DVL 定點作業（P0）
- CP／UT 量測（P1）
- 纜線手（甲板，多人，P1）
- 夜間或低能見度（P1）
- USBL 導航（P1）

**聲望**（P0，來源 MSFS 分類聲望、KSP）：按**客戶類別**分開，例如港務、養殖、能源、科研、打撈。高聲望帶來更好的合約與加成。失敗只扣該類聲望，避免 MSFS 的「聲望陷阱」：聲望再低，基礎合約也永遠接得到。

**個人日誌本**（P0，來源 IMarEST 的 logbook、研究報告 VideoRay 日誌欄位）：自動記錄駕駛時數（`real`／輔助分開）、潛次、最大深度、環境條件、角色（駕駛、纜線手、配件操作）。可匯出 JSON 或 PDF，給內部訓練用（對應 T17）。在遊戲中它就是「履歷」，是玩家身分認同的核心。

### 5.3 經濟與商店

**單一貨幣**（P0；KSP 的三資源被嫌複雜，PowerWash、ETS2 都只用一種貨幣）。聲望與時數不是貨幣，不能花。

**收入來源**：合約報酬 × 聲望倍率 + 品質獎金（覆蓋率、平順度、零碰撞）。報酬明細要逐項列出（ETS2、MSFS）。

**支出來源**（P0 只做前兩項）：

1. 配件與載具購買（一次買斷，不需要持續付費。MSFS 沒有月付，ETS2 有貸款）。
2. 維修：碰撞造成的損傷、纜線磨損與報廢（真實成本，鼓勵小心操作，數值必須溫和，避免 MSFS「前期懲罰性修理費」的負評）。
3. 工作船租用與燃油、人員（P1，公司經營）。

**升級商店：只賣真實設備，只開放能力**（P0 起），每個品項標明「真實用途」：

| 品項（通用名） | 開放的能力 | 物理影響 | fidelity |
|---|---|---|---|
| 高流明燈組 | 濁水與深水作業可見距離提升（依真實光學與背向散射模型） | 照實際規格 | 真機能力，不需註冊 |
| 雷射比例尺 | 拍照可量測尺寸，是部分檢查合約的必要條件 | 無 | 真機能力 |
| 單功能抓手 | 回收、掛繩合約 | 加質量與阻力（照實） | 真機能力 |
| CP 探棒／UT 測厚 | 陽極、壁厚量測合約 | 加質量與阻力 | 真機能力 |
| 成像聲納 | 零能見度搜索、導航；開放聲納簽注 | 加質量與阻力 | 真機能力（T15）；「聲納輔助疊圖」另外算，要註冊 |
| DVL | 開放定點（assist 2 的真實前提，AGENTS.md 已規定） | 照實 | 真機能力 |
| USBL | 母船端看到 ROV 位置；長距離管線合約 | — | 真機能力 |
| 加長纜線、中性浮力纜 | 更深、更遠的合約 | 纜線物理照實 | 真機能力 |
| 備品包 | 現場可修小故障 | — | 真機能力 |

**規則**：
- 不賣「推力 +10%」這類違反物理的數值升級。換一台推力更大的載具可以，但那是另一台載具，有自己的實測參數。這也避開了 Hardspace「升級只加數值、沒有改變感」的評論。
- 依 X1 規則，所有 X1 專屬數值仍是暫定。商店顯示的規格要能從資料表讀取，不要寫死在 UI。

**外觀商店**（P0 做少量，P1 擴充；來源 ETS2 改裝、Lawn Mowing 的公司 Logo 與配色）：載具塗裝與貼紙、公司 Logo 與配色、工作船旗幟與甲板配件、操作貨櫃（控制室）裝潢、駕駛員工作服。外觀用遊戲幣或成就解鎖，**沒有真錢商店，也不賣影響能力的東西**（no pay-to-win）。

**公司經營**（P1／P2，來源 ETS2、MSFS、Lawn Mowing）：買第二台載具、雇用 AI 駕駛去跑合約（被動收入，照 ETS2 的雇員系統）、升級工作船。要成為後期的錢坑，避免 Dredge 後期錢無用的問題。

### 5.4 合約板（P0）

每張合約卡片都要顯示：

- 客戶類別
- 工作類型
- 地點
- 水深
- **預報洋流與能見度**（引自研究報告：IMCA 事故檢討建議在駕駛介面加上洋流讀數）
- 平潮窗口
- 需求證照、簽注與配件（缺少的項目標紅，並寫明「去哪裡取得」，學 ETS2 灰掉的貨物）
- 報酬
- 時限：以「天候窗口」呈現，不做倒數計時，避免 Lawn Mowing 計時合約被罵
- 風險等級

另外三個重點：

- **受雇合約**（公司提供載具，錢少、安全）與**自營合約**（用自己的配置，錢多、成本自負）並列（MSFS）。P0 只做受雇合約與基本自營合約。
- 合約由「程序產生 + 手工劇情合約」混合構成。程序產生的部分沿用 `scenarios.py`／`mission_modes.py` 的判定。
- 永遠有一份低門檻的保底合約（船殼檢查），避免破產或卡關。

### 5.5 故事

沿用 T12 已訂的原創設定：小型海事工程公司「潮間帶工作隊」，以及序章（水池）→ 港灣 → 離岸 → 礁區 → 沉船 → 夜間回收。依本研究補充：

| 項目 | 來源 | 優先 |
|---|---|---|
| 職涯主線就是職等階梯：每章結尾是一次考照，劇情的高潮與進度的里程碑重疊 | MSFS 證照 + T12 章節 | P0 |
| 敘事只用無線電與簡報，**全部可跳過、可回看** | PowerWash 簡訊可忽略；Hardspace 無法跳過被罵 | P0 |
| 劇情章節結束後，該地點與工作類型進入合約板，成為可重複的合約 | ETS2、Dredge | P0 |
| 沉船章節的環境敘事：靠拍到的證據拼出真相 | Subnautica 殘骸敘事、Dredge 懸疑 | P1 |
| 藍領職人基調：天候、工時、甲板夥伴、督導的護短。不做諷刺性剝削，維持「專業受尊重」的感覺 | Hardspace 的基調（取其職人感，不取剝削諷刺） | P1 |

### 5.6 上手（Onboarding）

| 項目 | 來源 | 優先 |
|---|---|---|
| 開局一題「你的經驗」，對應 fidelity preset 與教學長度（Steam 版預設 `assisted`，內部版預設 `real`，與 AGENTS.md 一致） | TSW5 Beginner/Standard/Expert | P0 |
| 水池訓練中心：一次一件事、偵測完成、做錯不扣分、可重玩、可跳過（T12） | TSW 訓練中心、DCS 互動訓練 | P0 |
| 按鍵提示顯示目前裝置的圖示（T02 glyphs） | 一般慣例 | P0 |
| 8 分鐘內第一次收成（第一張合格照片 + 工資 + 讚許） | PowerWash | P0 |
| 新配件第一次裝上時，在水池給 60 秒的情境教學 | TSW「第一次進駕駛室教學」 | P1 |
| 輔助的漸進關閉建議：督導提示「要不要試試關掉定點？」，每次只建議關一項 | DCS「一次關一個輔助」 | P1 |
| 遊戲內手冊或百科：配件、程序、名詞 | Deep Diving Simulator 因為沒有手冊被罵 | P1 |
| 教學的自動化測試，防止更新後失效 | DCS 舊訓練任務過時的問題 | P0（T12 已要求） |

### 5.7 回饋手感（Juice）清單

原則：juice 屬於「前端呈現層」。凡是會改變真實畫面或資訊的，要註冊 fidelity 項目；純 UI 回饋（選單、結算畫面）不需要。

| 項目 | 來源 | 優先 | fidelity |
|---|---|---|---|
| 檢查點打勾聲加上清單逐項完成（覆蓋率） | PowerWash 部件完成 | P0 | 清單本身是真實的作業工具；畫面內高亮已檢區域屬超出真機 |
| 拍照快門聲、照片飛進「證據夾」，當場顯示是否合格（焦距、比例尺、清晰度） | 相機遊戲慣例 | P0 | 合格判定提示屬超出真機（`real` 中改成任務後講評才顯示） |
| 任務結算畫面：分項計分逐條跳出、報酬明細、日誌時數 +X、簽注進度條 | ETS2 交貨結算、MSFS 評分 | P0 | 不影響 |
| 證照取得儀式：證書畫面、督導語音、工作服胸章更換 | MSFS 證照、Hardspace 升等 | P0 | 不影響 |
| 推進器聲隨推力變化、纜線張力吱嘎聲、碰撞的悶響（T05） | Hardspace 物理音效 | P0 | 真實（機載麥克風或控制台告警屬真機能力範圍） |
| 手把震動：碰撞、纜線拉緊、抓取成功 | 一般慣例 | P1 | 超出真機（真機控制器多半沒有觸覺回饋〔未查證〕），要註冊 |
| 圖鑑新條目的「發現！」卡片 | subROV Gallery、Subnautica | P1 | 超出真機，要註冊 |
| 下水與回收的過場鏡頭（第三人稱） | ETS2 交貨過場〔未查證〕 | P1 | 第三人稱屬輔助，要註冊 |
| 相片模式：暫停、自由相機、景深、濾鏡 | ETS2 Photo Studio | P1 | 超出真機，要註冊 |
| 甲板夥伴與督導的即時語音反應（簡短） | Hardspace、T12 | P1 | 不影響 |

### 5.8 設定清單

| 類別 | 項目 | 優先 |
|---|---|---|
| 控制 | 鍵盤、手把、搖桿完整重新映射；每軸死區、曲線、反轉；靈敏度；輸入裝置圖示切換 | P0 |
| 擬真 | fidelity preset（`real`／`assisted`／`custom`）與逐項開關（由 `fidelity_panel.js` 自動列出） | P0 |
| 畫面 | FOV（機載相機 FOV 照真機，只開放第三人稱與相片模式的 FOV；機載 FOV 要改就屬超出真機）；解析度、視窗模式、畫質預設；畫面更新率上限；動態模糊與晃動開關 | P0 |
| 介面 | UI 縮放；HUD、選單、字幕分開縮放；HUD 密度（`presetNeutral`）；**單位制（公制／英制；深度 m／ft；速度 m/s／kn；溫度）** | P0 |
| 文字 | 語言（T09）；字幕開關、大小、背景、說話者名稱；對話自動前進 | P0 |
| 色彩 | 色盲支援：改變指示物的顏色並加上形狀，例如纜線張力、告警等級；高對比 HUD | P0 |
| 音訊 | 主音量、音效、語音、音樂、環境、UI 分開調整；單聲道 | P0 |
| 遊戲 | 生涯開局選項（資金、維修成本倍率）；教學重玩與跳過；提示頻率 | P0 |
| 存檔 | 雲端存檔（Steam Cloud）；多生涯存檔欄位 | P0 |
| 其他 | 按住改為切換（hold-to-toggle）；鏡頭晃動強度；暫停時背景靜音 | P1 |

商店頁的 Steam 無障礙問卷要依上表如實填寫（P0）。

### 5.9 社群與長尾

| 項目 | 來源 | 優先 |
|---|---|---|
| Steam 成就（以真實技能為主題，例如「零碰撞完成單樁檢查」「纜線從未超過張力門檻」） | 普遍做法 | P0 |
| Steam Cloud | subROV 因沒有雲端存檔而被列為缺點 | P0 |
| Steam Deck 可玩（介面、文字大小、效能） | subROV 在 Deck 上掉到 20 fps 被點名 | P1 |
| 截圖、相片模式分享到 Steam | ETS2 | P1 |
| 每週挑戰：固定種子、同條件，比覆蓋率與平順度，用 Steam 排行榜 | 〔模擬類實例未查證〕 | P2 |
| 社群共同目標（例如全服檢查 10,000 支樁柱） | World of Trucks | P2 |
| Workshop：自訂場景與合約（T12 JSON 格式） | Stormworks、ETS2 | P2 |
| 多人：主駕 + 纜線手 + 督導 | T12 終章、Under the Waves 題材 | P1／P2 |

---

## 6. 明確不做的事

- 不改物理來增加「爽感」：不提供推力數值升級，也不做違反真機的速度與機動。
- 不宣稱 IMCA 或任何機構的認證，不用其標誌；遊戲內的發證單位一律虛構（IMCA IN 1299）。
- 不用真實廠商或機型名稱、外觀（AGENTS.md 規則 8）。
- 不做真錢商店；外觀只用遊戲內方式取得。
- 不做無法跳過的劇情，不做硬性計時的合約。

## 7. 缺口與後續要補的研究

- 沒有讀到個別 Steam 評論的全文，大多來自評論彙整與媒體摘要（Snippet）；PowerWash、ETS2、Dredge、Subnautica 的 Steam 好評率本次沒有直接查證。
- MSFS 2024 的日誌本細節、PowerWash 第一關的時長、ETS2 的過場細節都標為〔未查證〕。
- IMCA C 005 各職等的能力表是會員限定，本研究只用了 IMarEST 的公開路徑與職缺數字；遊戲內門檻要標示為「遊戲設定，不等於業界要求」。
- 每日／每週挑戰在模擬類作品中的成效數據沒有找到。
- 拖車類職業模擬沒有找到好的範例。

## 來源

- PowerWash Simulator：[GameLuster](https://gameluster.com/review-powerwash-simulator-scrubs-up-well/)、[Geeks Under Grace](https://www.geeksundergrace.com/gaming/review-powerwash-simulator/)、[GameSpot](https://gamespot.com/reviews/powerwash-simulator-review-filthy-rich/1900-6417923/)、[Vaporlens PWS](https://vaporlens.app/app/1290000/power_wash_simulator)、[GameMeca PWS2](https://www.gamemeca.com/en/view.php?gid=1767495)、[Vaporlens PWS2](https://vaporlens.app/app/2968420/power_wash_simulator_2)、[WellPlayed PWS2](https://www.well-played.com.au/powerwash-simulator-2-review/)
- ETS2／ATS：[Truck Simulator Wiki 技能](https://trucksimulator.wiki.gg/wiki/Skills)、[Gamepressure 技能](https://gamepressure.com/eurotrucksimulator2/skills/ze45e0)、[racinggames.gg 雇員](https://racinggames.gg/article/how-to-hire-train-and-profit-from-fleet-drivers-in-euro-truck-simulator-2-and-ats)、[SCS World of Trucks](https://scssoft.com/projects/world-of-trucks)、[onlineracedriver WoT 更新](https://www.onlineracedriver.com/2013/10/22/world-trucks-euro-truck-sim-2-update/)
- MSFS 2024：[SimTuts 職涯指南](https://simtuts.com/guides/msfs-2024-career-mode-guide)、[msfsaddons FAQ](https://msfsaddons.com/msfs-2024-faq/career-mode/)、[Shacknews](https://shacknews.com/article/141437/microsoft-flight-simulator-2024-impressions)、[The AU Review](https://www.theaureview.com/games/microsoft-flight-simulator-2024-review/)、[PC Gamer](https://pcgamer.com/games/sim/microsoft-flight-simulator-2024-review)、[Vaporlens](https://vaporlens.app/app/2537590/microsoft_flight_simulator_2024)
- Farming Simulator 25：[Epic 新手指南](https://store.epicgames.com/news/prepare-to-plow-with-our-farming-simulator-25-beginners-guide)、[Gamepressure](https://www.gamepressure.com/farming-simulator-25/basics/z0116a7)、[Gamepressure 合約 bug](https://www.gamepressure.com/newsroom/watch-out-for-contracts-not-working-in-farming-simulator-25-fs25/z4753e)
- Train Sim World：[Dovetail 設定說明](https://support.dovetailgames.com/hc/en-us/articles/35574942592658-How-to-set-up-Train-Sim-World)、[TSW 新手指南](https://live.dovetailgames.com/live/train-sim-world/articles/article/tsw-beginnersguide)、[To The Trains TSW5 評測](https://tothetrains.uk/train-sim-world-5-review/)
- Dredge：[NME](https://www.nme.com/reviews/dredge-review-3418763)、[GamesRadar](https://gamesradar.com/dredge-review)、[Slant](https://www.slantmagazine.com/games/dredge-review-stuck-in-the-shallow-end/)、[OpenCritic](https://www.opencritic.com/game/14348/dredge/reviews?page=2)
- Subnautica：[thegameswiki](https://thegameswiki.com/subnautica-2/wiki/blueprints-and-scanning)、[PCGamesN](https://www.pcgamesn.com/subnautica-2/blueprints)
- Stormworks：[Wikipedia](https://en.wikipedia.org/wiki/Stormworks:_Build_and_Rescue)、[Cubed3](https://cubed3.com/preview/740/1/stormworks-build-and-rescue-pc.html)、[Steam 討論](https://steamcommunity.com/app/573090/discussions/0/6406956248969128661)
- Hardspace: Shipbreaker：[Wikipedia](https://en.wikipedia.org/wiki/Hardspace:_Shipbreaker)、[gameplay.tips](https://gameplay.tips/guides/7900-hardspace-shipbreaker.html)、[Worthplaying](https://worthplaying.com/article/2021/5/6/news/125785/)、[Vaporlens](https://vaporlens.app/app/1161580/hardspace_shipbreaker)、[PC Gamer](https://www.pcgamer.com/hardspace-shipbreaker-review)、[Steam 評論](https://steamcommunity.com/id/maudish/recommended/1161580/)
- Lawn Mowing Simulator：[TheSixthAxis](https://www.thesixthaxis.com/2021/08/09/lawn-mowing-simulator-review/)、[Pure Xbox](https://www.purexbox.com/reviews/xbox-series-x/lawn_mowing_simulator)、[Kotaku](https://kotaku.com/1847496842)、[GameSpew](https://www.gamespew.com/2022/04/lawn-mowing-simulator-review-ps5/)
- 拖車類：[Steam Towtruck Simulator 2015](https://store.steampowered.com/app/273760)
- KSP：[KSP Wiki Career](https://wiki.kerbalspaceprogram.com:443/wiki/Career)、[Strategies](https://wiki.kerbalspaceprogram.com/wiki/Strategies)、[KSP 論壇](https://forum.kerbalspaceprogram.com/topic/146756-disconnect-science-from-tech-research/page/2)、[Career Reimagined](https://spacedock.info/mod/4249/Career%20Reimagined)
- DCS：[Heatblur F-4 訓練任務](https://f4.manuals.heatblur.se/dcs/training_missions.html)、[FlyAway 訓練資源](https://flyawaysimulation.com/ask/answers/best-dcs-world-training-missions-resources/)、[FlyAway 簡易模式](https://flyawaysimulation.com/ask/answers/dcs-world-easy-mode/)、[DCS 論壇](https://forum.dcs.world/topic/239915-making-dcs-more-accessible-to-new-players/page/10)
- 水下／ROV：[Steam subROV](https://store.steampowered.com/app/1648760)、[GameLuster subROV](https://gameluster.com/review-subrov-underwater-discoveries-roving-in-the-deep/)、[Steam vROVpilot TITANIC](https://store.steampowered.com/app/3397800)、[Steam Deep Diving Simulator](https://store.steampowered.com/app/990030)、[GOG Deep Diving Simulator](https://www.gog.com/en/game/deep_diving_simulator)、[Steam Silent Depth](https://store.steampowered.com/app/846050)、[StatelyPlay Silent Depth](https://statelyplay.com/2016/12/14/review-silent-depth/)、[Steam Under the Waves](https://store.steampowered.com/app/1975440)、[Push Square Under the Waves](https://www.pushsquare.com/reviews/ps5/under-the-waves)
- ROV 產業：[IMCA C 005](https://www.imca-int.com/resources/technical-library/document/3907f45c-c55b-ee11-8def-6045bdd2c7e3/)、[IMCA IN 1299](https://www.imca-int.com/information-notes/rov-technician-accreditation-guidance)、[IMarEST ROV Pilot 職涯路徑 PDF](https://www.imarest.org/asset/5ED67A8D-023F-4236-B678907060AC710A)、[OGV Energy 職缺](https://jobs.ogv.energy/job/rov-pilot-technician-51221)、[DiveWorks 養殖](https://www.diveworks.com.au/aquaculture/)、[OST 養殖 ROV](https://www.oceansciencetechnology.com/suppliers/aquaculture-rov/)、[Deep Trekker 離岸作業](https://www.deeptrekker.com/resources/offshore-operations)、[OST 離岸檢查](https://www.oceansciencetechnology.com/feature/how-deep-trekker-rovs-enhance-offshore-inspections-maintenance/)、[Intertek ROV](https://www.intertek.com/asset-integrity-management/underwater-rov)、[Hydro International](https://www.hydro-international.com/content/article/rovs-as-versatile-workhorses)、[VideoRay Pro 4 配件](https://kb.videoray.com/?p=230)、[VideoRay Pro 4 Ultra 手冊](https://download.videoray.com/documentation/pro_4_ultra/html/accessories_manufacturer.html)、[Deep Trekker 配件](https://www.deeptrekker.com/products/underwater-rov/rov-add-ons)、[Hydromea EXRAY 規格](https://mfe-is.com/en_ca/hydromea-exray_technical-specifications/)、[Acteon NDT 感測器](https://acteon.com/equipment-sales-rental/electronics-tooling/rov-sensors/ndt-inspection-rov-sensors/)、本專案 `docs/reference/real-rov-research.md`
- Steam 與上手：[Steamworks 無障礙功能](https://partner.steamgames.com/doc/accessibility_features)、[PC Gamer Steam 無障礙搜尋](https://www.pcgamer.com/gaming-industry/steams-store-now-lets-you-search-for-games-by-accessibility-features-like-narrated-game-menus-and-adjustable-difficulty-and-more-than-5-000-games-have-already-added-their-accessibility-details-to-the-database)、[GamingOnLinux](https://www.gamingonlinux.com/2025/06/steam-adds-accessibility-features-to-store-pages-and-filters-for-searching)、[Game Accessibility Guidelines Basic](https://gameaccessibilityguidelines.com/basic/)、[Summer Engine 行銷指南](https://www.summerengine.com/ja/make-great-games/market-your-indie-game)、[Theory-Craft Steam 指南](https://www.theorycraftmarketing.com/the-complete-steam-marketing-guide-for-indie-developers-2026)、[How To Market A Game](https://howtomarketagame.com/courses/)
