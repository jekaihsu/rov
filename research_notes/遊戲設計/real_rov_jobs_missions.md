# 真實 ROV 工作類型與「職涯」任務設計研究

> 目的：把遊戲主線做成「接案生涯」——玩家從水池檢查潛開始，一路接到港務、船東、養殖場、警方、水庫、離岸風電、海纜業主的工單，難度由淺入深，盡量照真實 ROV 駕駛的日常工作走。
>
> 依據：本文以公開網路資料為主（2026-11 查詢），並對照 `docs/reference/real-rov-research.md` 與 `research_notes/洋流與波浪對ROV作業/real_dive_footage.md`。
> 標記：〔廠商〕表示來源是廠商或經銷商的行銷資料，未經獨立驗證；〔假設〕表示查不到來源，是本文的推估或設計提案，實作時要在 PR 描述註明；〔二手〕表示來源是二手摘要或簡報，不是標準原文。
> **X1 專屬數字一律不在本文寫死**（見 AGENTS.md）。本文提到的工時、距離、門檻都是「任務參數」，不是 X1 的規格。
> 品牌：本文是內部研究筆記，引用了廠商名稱作為出處。遊戲內的任務文字、客戶名稱一律用虛構、去品牌化的名稱（AGENTS.md 硬性規則 8）。

---

## 0. 結論先講

1. **觀測級 ROV 的真實工作其實很「遊戲」**：工作內容就是照規定的路線飛、對準目標、拍到合格的照片、在正確的位置記事件、最後交報告。這些都能在模擬器裡量化（覆蓋率、距離、對準角、KP 誤差、照片是否帶疊字、是否碰撞）。不需要虛構戰鬥或收集要素，玩家的成就感來自「在洋流、濁水、纜線拖曳下仍交出乾淨的資料」。
2. **觀測級與作業級的分界很清楚**：切纜、修纜、噴沖埋設、重物吊放、扭力工具都是作業級（IMCA Class III 以上）的事；觀測級真的會做的是目視檢查（GVI/CVI）、陽極與海生物評估、沖刷調查、海纜目視追蹤、CP 接觸量測（需探針配件）、搜尋與確認、輕物回收（夾爪）。生涯可以設計成：觀測級做完前期調查 → 取得證照 → 在作業級任務中先當「第二視角／監看 ROV」 → 最後親自駕駛作業級。
3. **最該先蓋的新場景**：養殖箱網、海床上的海纜（含埋設／裸露／懸空／交越）、帶沖刷坑與海纜保護系統（CPS）的單樁、水庫進水口攔污柵、湖泊搜救（零能見度泥底）。
4. **心流設計重點**：每一關只加一個新變數；失敗後 10 秒內可從檢查點重試；即時回饋（覆蓋率圈、照片合格與否）；獎牌是可選的精熟目標，主線只要求「交得出可用的報告」。TRANSoM 研究的教訓是：硬性通關門檻會讓弱的學員卡死在強流、低能見度關卡，所以難關要能「降級完成、拿較低評等繼續」。

---

## 1. 載具分級：真實業界怎麼分，模擬器三台怎麼對應

IMCA R 004（現行 Rev. 6，2024-02）把 ROV 分級。以下是 Rev. 4 的分級摘要〔二手〕（[Hydro International](https://www.hydro-international.com/content/article/trends-and-new-technology-in-the-rov-industry)；舊版五級制見 [Offshore Energy](https://offshore-energy.biz/2015/08/07/imca-work-class-rovs-most-used-in-2014)）：

| 等級 | 內容 | 本模擬器對應 |
|---|---|---|
| Class I | 純觀測，GVI／CVI，便宜、好攜帶 | 觀測級 ROV（X1 類）基本配置 |
| Class IIA | 觀測級＋酬載選項（聲納、DVL、雷射尺、CP 探針、追蹤器） | X1 類加配件；BlueROV2 Heavy |
| Class IIB | 觀測級但具輕度介入、測量、施工能力，可掛輕型機械手 | BlueROV2 Heavy 加夾爪；「Falcon 類」輕作業級 |
| Class IIIA | 標準作業級，酬載 < 200 kg，框架吊重約 1,000 kg | 模擬器目前沒有；「Falcon 類」只能當輕作業級 |
| Class IIIB | 進階作業級，酬載 > 200 kg，框架吊重可達 3,000 kg | 沒有 |
| Class IV（舊制）| 拖曳式、海床履帶（埋設機、挖溝機） | 沒有 |

〔假設〕模擬器中「Falcon 類」的定位：真實 Seaeye Falcon 被用在養殖場吸死魚等輕作業〔廠商〕（[Bluezone Group](https://bluezonegroup.com.au/announcements/seaeye-falcon-for-aquaculture-support/)），屬於 Class II 的上緣。若要做「作業級切纜、噴沖埋設」，嚴格說需要一台新的 Class III 載具；短期可以讓玩家在這類任務中操作觀測級「監看 ROV」，作業級由 NPC 或第二玩家操作（見 §3.3、§6 Act 6）。

---

## 2. 工作類型目錄

每項工作的欄位：委託方｜真實程序｜交付物｜典型條件｜常見狀況｜工時〔多為假設〕｜裝備｜**觀測級能否做**。

> 判定符號：●＝觀測級（X1／BlueROV 類）實際在做；◐＝觀測級可做一部分，需配件或只能做調查；○＝需作業級。

### 2.1 船殼與螺槳檢查（Hull & propeller）● 

- **委託方**：船東／船舶管理公司（生物附著管理、油耗）、船級社驗船師（水下檢驗代替進塢，UWILD／IWS）、保險公證人（擱淺、碰撞後損傷評估）、港口國／海關（走私物、非法附掛物）〔假設：海關用途常見於報導，未查一手〕。
- **法規背景**：美國 46 CFR §115.615 允許以水下檢驗代替進塢，申請須說明檢驗程序、**潛水員或 ROV 相對船殼的定位方法**、穿殼配件與附屬物如何檢查、船殼防蝕系統（[46 CFR 115.610 封存版](https://webarchive.library.unt.edu/eot2008/20090509103623/http://edocket.access.gpo.gov/cfr_2002/octqtr/pdf/46cfr115.610.pdf)）。船級規範要求水下檢驗提供與乾塢檢驗同等的資訊，並特別確認舵的狀況〔二手〕（[In-Water Survey 簡報](https://www.scribd.com/presentation/618082491/In-Water-Survey)）。
- **生物附著**：IMO 2023 生物附著指引要求優先檢查「niche areas」（舵、螺槳、海底門等凹處），每一區給 **0–4 的附著評級**（0 無、1 微生物膜、2 輕度大型附著、3 中度、4 重度），目標維持 ≤1（[IIMS 摘要](https://www.iims.org.uk/imo-biofouling-guidelines-key-recommendations/)、[Gard](https://gard.no/articles/hull-biofouling-key-recommendations)、[BIMCO](https://bimco.org/Insights%20and%20information/Safety%20Security%20Environment/20231018%20biofouling%20guidelines)）。
- **真實程序**：
  1. 預潛：與船方確認**主機、螺槳、側推、海水泵、聲納、陰極防蝕外加電流（ICCP）已鎖定／停用**（上鎖掛牌，LOTO）〔假設：業界通則，本次未查到一手 ROV 程序〕；記錄吃水、船名、檢驗範圍。
  2. 下水，錄影開始，片頭拍「打板」（地點、人員、潛次）（[VideoRay PPI SOP](https://download.videoray.com/documentation/sop_ppi/html/_print.html)）。
  3. 依船殼分區（左右舷、平底、艏艉）以固定間距航線覆蓋；平底部分 ROV 在船下方，**沒有水面參考，纜線容易卡在舭龍骨或船底邊緣**（現有 `hull_inspection` 已做）。
  4. 依序檢查 niche areas：海底門格柵、舵（舵銷、舵承、間隙）、螺槳（葉緣損傷、空蝕、附著、螺距）、艉軸封、測深／測速換能器、陽極（[Deep Trekker UWILD 實務](https://www.deeptrekker.com/resources/uwild-best-practices)〔廠商〕）。
  5. 異常處拍特寫（帶疊字、比例尺），記錄位置（肋位號或船殼標記）。
- **交付物**：連續錄影、照片集（含疊字：船名、日期、位置）、逐區附著評級表、異常清單、陽極消耗估計、檢驗報告（附平面示意圖）。
- **條件**：港內，水深淺但船底下方暗；能見度常 1–5 m〔假設〕；碼頭邊有潮流；船可能在作業（他船螺槳流）。
- **常見狀況**：纜線卡在舭龍骨／螺槳；ROV 被吸向海底門〔假設：若泵未停〕；鋼船殼旁羅盤失準（現有 `incident_compass`）；船殼附著物讓定點困難。
- **工時**：小船 1–2 小時、大船半天到一天〔假設〕。
- **裝備**：觀測級 ROV、燈、雷射比例尺（量損傷尺寸）、可選的超音波測厚（接觸式，屬 CVI，觀測級需配件）、定位（USBL 或船殼爬行器）。

### 2.2 港埠樁柱與碼頭岸壁檢查（Pile / quay inspection）●

- **委託方**：港務局、碼頭營運商、交通部門（橋墩，FHWA 架構）、結構顧問公司。
- **檢查等級**：美國橋墩／碼頭水下檢查分三級。Level I 為目視、觸摸的「swim-by」，清除極少，涵蓋整個外露結構；Level II 為細部，在抽樣構件上清除約 10 英寸（約 25 cm）寬的海生物帶後近距檢查（[TRB Circular 498](https://onlinepubs.trb.org/Onlinepubs/trcircular/498V1/498V1-008.pdf)、[FHWA 技術公告](https://webarchive.library.unt.edu/eot2008/20090509104124/http://www.fhwa.dot.gov/legsregs/directives/techadvs/t514021.htm)）。一家顧問公司稱 Level II 抽樣約 10% 構件〔二手〕（[GEI](https://waterfront.geiconsultants.com/which-underwater-inspection-is-right-for-your-port-project-and-why-an-engineer-diver-is-best-for-the-job/)）。多個來源強調 ROV 是輔助，不能完全取代潛水員的觸摸檢查（同上）。
- **真實程序（VideoRay 樁柱 SOP）**（[VideoRay PPI SOP](https://download.videoray.com/documentation/sop_ppi/html/_print.html)）：
  1. 現場安全評估（控制台位置、電源、纜線路徑、下水點，避免面向太陽）。
  2. 預潛檢查到功能測試；開錄影，拍片頭「打板」。
  3. 下水、檢查配重、開自動定向／定深、初始化導航；在下水點設 Home 航點（深度 0）。
  4. 檢查樁柱：**垂直航次**為主（面對樁、垂直下降或上升一趟，繞到下一個方位，反向再一趟），下降時鏡頭略朝下、上升時略朝上；大直徑樁改用**環繞航次**（繞一圈、換深度、反向）。有斜撐時一側一側做。
  5. 離樁距離約 **0.7 × 能見度**；航次間距約 **1.3 × 能見度**（約 10% 重疊）；預設速度 0.5 m/s，低能見度要更慢。
  6. **纜線規則**：只放出最少纜線；纜線始終留在每根樁的同一側；換排換列時不要繞樁、不要穿過斜撐；從水面附近進出網格以避開看不見的斜撐；盡量從水面回到下水點。
  7. 紀錄已完成的樁，確認覆蓋完整；結束前先存任務、停錄影，再關機（避免檔案損毀）。SOP 原文警告：**沒錄到就等於不存在**。
- **交付物**：每樁錄影段、照片（疊字：專案、地點、人員、潛次）、樁況表（剝落、鋼筋外露、裂縫、斷面損失、海生物厚度與覆蓋率）、聲納影像（岸壁）、檢查報告。
- **條件**：淺水 3–15 m〔假設〕、港內濁水、碼頭邊潮流、船舶交通與螺槳流、碼頭下方暗且有大量斜撐。
- **常見狀況**：纜線繞樁（現有 `tether_untangle`）、穿斜撐卡住、他船進港須中止、揚起底泥。
- **工時**：一座碼頭數天；單樁 Level I 數分鐘到十幾分鐘〔假設〕。
- **裝備**：觀測級 ROV、燈、雷射比例尺、多波束成像聲納（岸壁與濁水）、可選 DVL／USBL、超音波測厚（CVI）。

### 2.3 養殖箱網：網衣檢查、死魚回收、繫泊檢查 ●（死魚回收 ◐）

- **委託方**：鮭魚／海鱺／石斑等海上箱網養殖場、保險公司（脫逃事故後）、主管機關（挪威 NYTEK23／NS 9415 防脫逃規範）。
- **法規背景**：挪威 NS 9415 是以「防止魚隻脫逃」為目的的浮動式養殖設施標準，涵蓋設計、建造與營運；NYTEK23 法規引用它（[Standards Norway](https://standard.no/en/sectors/fisheries-and-aquaculture/floating-aquaculture-farms/)、[Sands 律師事務所](https://www.sands.no/en/news/new-technical-requirements-for-aquaculture-facilities-in-the-sea-nytek23-and-ns-9415-2021/)）。本次**沒查到**條文中「何時須做 ROV 網衣檢查」的具體規定。網衣破洞會讓養殖場不合規〔廠商〕（[Deep Trekker](https://www.deeptrekker.com/news/preventing-aquaculture-fish-escapes)）。
- **工作內容**：
  - **網衣檢查**：找破洞、磨損、網衣變形（洋流造成網衣上浮使容積變小）、附著物堵塞網目、海獅／海豹咬痕。大型網衣可能每週至少檢查兩次〔廠商〕（[Bluezone](https://bluezonegroup.com.au/announcements/seaeye-falcon-for-aquaculture-support/)）。
  - **死魚（mort）回收**：把沉在網底的死魚推進抽吸系統，或夾起帶上水面〔廠商〕（[VideoRay 養殖](https://videoray.com/industries/aquaculture/)）。大型業者 Mowi 已有超過 25 台專用 ROV，下一步要處理水面瀕死魚（[Global Seafood Alliance](https://www.globalseafood.org/advocate/partnership-aims-to-boost-efficiency-and-fish-welfare-through-expanded-rov-use-in-salmon-farming/)）。有業者說他們已約 15 年沒派潛水員下水（[Deep Trekker 客戶案例](https://www.deeptrekker.com/learn/3-ways-kana-upton-and-aqua-cage-fisheries-use-their-rov)〔廠商〕）。
  - **繫泊檢查**：錨繩、浮標、錨鏈、連接卸扣、網底沉子環。
  - **魚群行為觀察**：攝食、異常游動、密度〔假設〕。
- **真實程序（網衣檢查）〔假設，綜合廠商說明〕**：
  1. 從工作平台或船邊下水；確認養殖場當日作業（投餵、換網、洗網機）。
  2. 以固定深度繞網衣內側一圈，再分段下降（類似樁柱的環繞航次）；網底以放射狀或格網巡過。
  3. 發現破洞：停住、對正、拍照（以雷射尺或網目尺寸估大小）、記錄**網格編號／方位（時鐘方位）／深度**。
  4. 回報；養殖場派人修補，修補後 ROV 複查。
- **交付物**：每口箱網的檢查錄影、破洞清單（編號、位置、大小、照片）、死魚數量、繫泊狀況表。
- **條件**：水深 10–50 m 網深〔假設〕；**大量魚群擋視線**、餌料與排泄物使能見度變差；潮流使網衣變形；近水面有浪。
- **常見狀況**：推進器把網衣吸進去（最危險，會纏住且可能弄破網）〔假設〕；纜線纏在網衣或繫泊繩；魚群撞擊、驚嚇魚群（福利問題）；在網外檢查時被流推向網衣。
- **工時**：一口箱網 20–60 分鐘〔假設〕；一個養殖場數小時。
- **裝備**：觀測級 ROV、廣角相機、燈（**燈要調暗以免驚嚇魚**〔假設〕）、雷射尺、夾爪或專用死魚收集器（◐：小夾爪能夾單尾，大量回收需抽吸系統）、可選網衣距離感測（聲納）。

### 2.4 離岸風電：單樁／導管架基礎 ●（CP 接觸量測 ◐、清除海生物 ○）

- **委託方**：風場營運商（O&M 團隊）、驗證機構、保險公司、風場運維承包商。
- **實際範圍**（Coastal Virginia Offshore Wind 試驗風場）：以**多波束**做海床、沖刷保護與泥沙移動調查；以**小型 ROV**做一般目視檢查（GVI）與陰極防蝕（CP）評估，看海生物、塗層、陽極消耗；重點區包括水平定向鑽（HDD）出口與海纜交越點；**ROV 從單樁平台既有的吊臂（davit）下水**，免派大船；水深 6–40 m，作業窗口很短（[Acteon CVOW 案例](https://acteon.com/insights/case-studies/surveys-and-inspections-for-coastal-virginia-offshore-wind-pilot-project)〔廠商〕）。
- **一份真實招標（Ørsted）的檢查項目**：海纜在 CPS 中的位置、海纜裸露、從海纜出口到海床的水平／垂直懸空（[Mercell 招標](https://www.mercell.com/permalink/174105658.aspx)〔二手〕）。
- **CP 量測**：以檢測級 ROV 搭 FiGS 場梯度感測器，在鋼構與陽極上量電位並從場梯度推算陽極電流（[FORCE Technology Baltic 2](https://forcetechnology.com/no/cases/baltic-2-wind-farm-survey)〔廠商〕）。接觸式探針（例如 Polatrak ROV II）用雙 Ag/AgCl 參考電極，量程 0 至 −1999 mV、準確度 ±5 mV，雙電極讀數差太多表示其中一支可能壞了（[MFE Polatrak ROV II](https://mfe-is.com/offshore/polatrak-ii-rov-probe/)〔廠商〕）。
- **CPS（海纜保護系統）**：位於海床到 J 型管／單樁開孔之間的「暴露區」，承受流與泥沙作用；常見失效是 CPS 在拋石保護層上反覆擺動磨損，嚴重時威脅海纜（[OWC CPS 白皮書](https://abl-group.com/wp-content/uploads/2022/10/OWC-White-Paper-Cable-Protection-Systems.pdf)、[Ashtead ROV3D](https://ashtead-technology.com/?p=21724)〔廠商〕）。CPS 一般分三段：單樁介面、動態段、靜態段（[Wikipedia: Bend stiffener](https://en.wikipedia.com/wiki/Bend_stiffener)〔二手〕）。
- **真實程序（單樁 GVI＋CP＋沖刷）〔假設，綜合以上〕**：
  1. 規劃：看潮汐表，**選平潮（slack water）窗口**；確認 CTV（人員運輸船）靠泊、吊臂可用、風機狀態。
  2. 下水：從平台吊臂或 CTV 放下；纜線從平台垂下（纜線不會在海床拖，但會被流吹成弧形）。
  3. 飛濺區到海床：沿單樁以環繞航次由上到下，記錄**海生物厚度、覆蓋率、軟／硬附著**（每個高程一筆）、塗層破損。
  4. 陽極：逐一拍照（正面＋側面），估消耗百分比；用 CP 探針接觸鋼構與陽極各量一筆讀數。
  5. 海床：沿樁底繞一圈，看沖刷坑深度、沖刷保護層（拋石、墊層）是否移位、邊緣沖刷（edge scour）。
  6. 海纜進樁段：從 J 型管／開孔一路追到 CPS 末端埋入海床處，記錄 CPS 狀態、裸露長度、懸空長度與高度、是否在石頭上磨。
  7. 回收，資料上傳到客戶的資產完整性平台（anomaly tracking、儀表板）。
- **交付物**：GVI 錄影、陽極照片與消耗估計、CP 讀數表（每點位置、mV 值、合格與否）、海生物剖面、沖刷深度圖、CPS 異常清單、海纜懸空量測。
- **條件**：北海／台灣海峽潮流強（> 1.5 kn 在 VideoRay 定義屬強流，見研究報告）；能見度差（台灣海峽常 < 3 m〔假設〕）；浪造成近水面晃動；平潮窗口可能只有 30–60 分鐘〔假設〕。
- **常見狀況**：漲退潮來得比預期快，ROV 被推向單樁或導管架內（IMCA SF 02/23，現有 `incident_jacket`）；纜線在導管架斜撐上磨；鋼構旁羅盤失準；DVL 在拋石層上高度跳動；揚起泥沙。
- **工時**：一支單樁 1–3 小時，受平潮限制常分多次〔假設〕。
- **裝備**：觀測級 ROV（具抗流能力）、雷射尺、CP 接觸探針或場梯度感測器（◐ 需配件）、成像／多波束聲納、DVL、USBL、可選 3D 雷射或攝影測量。**清除海生物**（水刀、刷子）通常是潛水員或作業級工作（○）。

### 2.5 海底電纜／管線調查 ●（追蹤器 ◐、切纜修復與埋設 ○）

- **委託方**：海纜業主（電信、電力：風場陣列纜與送出纜、跨海輸電）、管線業主、保險、海事主管機關（錨害事故）、要做交越的第三方（交越協議）。
- **工作內容**：
  - **路由目視調查**：ROV 沿海纜飛，記錄埋設／裸露、懸空、外物（錨、漁網）、損傷，每個事件標 **KP**（從起點量的公里數）。
  - **追蹤埋設段**：海纜被埋時看不到，用**脈衝感應式追蹤器**（如 TSS 440）量目標相對 ROV 的位置與**覆土深度**；它能偵測任何導電物，經 ROV 臍帶纜回傳（[Teledyne TSS 440 手冊](https://www.manualslib.com/manual/2915525/Teledyne-440.html?page=21)、[Unique Group 規格](https://www.uniquegroup.com/wp-content/uploads/2022/10/Teledyne_TSS-440_-Pipe_Tracker.pdf)〔廠商〕）。TSS 350 追蹤**通了音頻訊號（tone）的海纜**，輸出包含故障位置、載具偏斜角與前視資訊（同上）。
  - **交越點調查**：海纜跨過另一條海纜或管線處，檢查保護墊（mattress）、拋石、間距是否符合交越協議（ICPC 建議書 No. 2、No. 3；[ICPC 出版品](https://iscpc.org/publications/recommendations/)）。
  - **故障定位**：先從兩端以電氣方法（TDR、Murray 電橋）預估距離，再沿路由追蹤，最後以音頻追蹤或磁場變化精確定點（[Bawart 論文，Scribd](https://www.scribd.com/document/375790951/A-07528987)〔二手〕、[SINTEF](https://blog.sintef.com/energy/smart-fault-location-on-subsea-cables/)、[Megger Magtrack](https://www.megger.com/en/products/magtrack)〔廠商，設計給作業級 ROV〕）。
  - **管線**：路由調查、陽極、塗層、懸空（free span）、凹痕、外物；異常表以 KP＋時鐘方位＋尺寸記錄（[Rigzone](https://www.rigzone.com/insights/operational-questions-8/how-to-perform-integrity-checks-on-subsea-pipelines-1065)〔二手〕）。一份二手資料提到懸空篩選門檻約 10 m 或易發生渦激振動（VIV）處〔二手，未查到 DNV 原文〕。
- **修復與補救（作業級，○）**：
  - 埋深不足或裸露：常以保護墊、拋石（DP 落管船）補救，最糟要重新埋設；**較精確的埋深資料需要 ROV 調查**，水面調查只能看出明顯裸露（[Guide to Floating Offshore Wind](https://guidetofloatingoffshorewind.com/guide/o-operations-and-maintenance/o-2-maintenance/o-2-2-balance-of-plant-maintenance/o-2-2-3-cable-monitoring-inspection-and-minor-repair/)）。
  - 修復：通常要整套鋪纜船隊（CLV、犁或噴沖設備、保護最小彎曲半徑的導輪）；在甲板上切斷、插入新段並接頭；短的陣列纜可能整段換掉比較划算（同上）。
  - 實例：在 16–25 m 水深以抓切工具切斷並回收 165 mm 海纜兩處，客戶的 ROV 提供即時影像（[Ocean News](https://oceannews.com/?p=69375)〔廠商〕）；英國一條送出纜剝埋 7.5 km、多處切斷、回收、新纜鋪設並以噴沖埋到頂部 1.5 m（[Offshore Magazine](https://www.offshore-mag.com/subsea/article/14288662/rotech-completes-trenching-cable-cut-and-recovery-at-offshore-wind-farm)〔廠商〕）。**注意第一例：觀測級 ROV 在作業級工作中擔任「看的人」**。
- **真實程序（目視路由調查）〔假設，綜合以上〕**：
  1. 讀路由圖（RPL，路由位置清單）與上次調查的事件表；設好 KP 原點。
  2. 下水，到第一個 KP；以固定高度（離底約 1–2 m〔假設〕）、海纜在畫面中央、穩定速度前進。
  3. 狀態一變就記事件（eventing）：「KP 1.234 裸露開始」「KP 1.250 懸空開始，高度 0.4 m」「KP 1.262 埋設」……
  4. 異常處停下拍照（帶疊字：KP、深度、航向、時間）。
  5. 交越點、保護墊、拋石段另外細看。
- **交付物**：事件表（KP、事件碼、說明、照片編號）、連續錄影（疊字含 KP）、埋深剖面（追蹤器）、懸空清單、路線對照圖（alignment sheet）、異常登記表（[Rigzone](https://www.rigzone.com/insights/how-it-works-3/what-is-the-role-of-robotics-in-subsea-pipeline-inspections-555)〔二手〕）。
- **條件**：開闊海床、潮流、沙波移動使海纜時埋時露；泥底揚沙；能見度不一。
- **常見狀況**：海纜消失在沙下（要靠追蹤器或依路由推估重新找到）；揚沙；DVL 在沙波上漂；在管線上方羅盤失準；纜線越拖越長（長距離調查時臍帶纜拖曳很大，通常由船跟著 ROV 走〔假設〕）。
- **工時**：觀測級從岸邊或小船做時每天數百公尺到數公里〔假設〕；長距離通常用作業級或 AUV。
- **裝備**：觀測級：攝影機、燈、DVL、USBL、可選追蹤器（◐，真實追蹤器多裝在作業級上）；作業級：追蹤器、抓切工具、噴沖機、吊索。

### 2.6 搜尋與回收（Search & recovery）●（重物吊放 ○）

- **委託方**：警方／消防（溺水者、證物、車輛）、海巡、港務（掉落物、錨）、工程公司（掉落工具、儀器）、研究單位（儀器回收）、保險。
- **真實程序（湖泊搜救，加拿大 RCMP 等）**：先定義搜尋範圍（例如鎖定約 500 m²），以側掃或**放到湖底的三腳架掃描聲納**掃描；出現目標就標定位置，再派 ROV 確認或潛水員回收（[Castanet / RCMP](https://www.castanetkamloops.net/news/Oliver-Osoyoos/378014/RCMP-dive-team-arrive-at-Osoyoos-Lake-to-find-missing-Oliver-man-who-drowned)、[RCMP Gazette](https://rcmp-grc.gc.ca/en/gazette/deepwater-detection)）。在零能見度下沒有聲納就派人下水被視為不安全；危險包括強流、零能見度、湖底人造雜物；潛水員用假人訓練分辨樹樁、石頭與目標（[Hydro International](https://www.hydro-international.com/content/news/underwater-search-by-police-and-dive-teams)）。ROV 讓團隊快速確認聲納目標，把時間花在回收上（[Firehouse](https://www.firehouse.com/technology/news/55314167/nc-rescuers-use-remotely-underwater-vehicle-for-lake-recoveries)、[VideoRay 案例](https://videoray.com/may-25-2016-videoray-pro-4-rov-used-to-recover-drowning-victim/)）。
- **交付物**：搜尋區域與航線紀錄、聲納目標清單（方位、距離、座標）、確認影像、證物位置（證據鏈：誰、何時、在哪裡發現；在原位拍照後才移動）〔假設〕。
- **條件**：淡水湖、河、港；**零到 1 m 能見度**、冷、泥底；水深可能很深（溺水者常在深處）。
- **常見狀況**：揚沙毀掉能見度；纜線纏樹枝、廢棄漁網；把石頭誤判為目標；河流強流。
- **裝備**：成像聲納（必要）、ROV、夾爪或回收鉤（輕物可由 ROV 回收；人體通常由潛水員回收，或以 ROV 掛鉤）〔假設〕。
- **遊戲化注意**：遺體搜尋題材敏感。建議遊戲中用「失蹤者遺留物」「證物（手機、背包、汽車）」或「訓練用假人」，畫面上不呈現遺體，維持尊重〔設計建議〕。

### 2.7 水庫與水力電廠：進水口、攔污柵、閘門 ●

- **委託方**：水庫管理單位、水力電廠、自來水公司、壩安全主管機關。
- **工作內容**：攔污柵（trash rack）擋漂流木與垃圾，堆積會堵水降低發電；進水口與控制閘門檢查堵塞與結構狀況；壓力鋼管（penstock）檢查堵塞與損壞；淤積量（[Deep Trekker 水力](https://www.deeptrekker.com/news/hydroelectric-rov-inspections)〔廠商〕）。實例：一次 ROV 檢查在**不洩空機組**的情況下檢查混凝土進水口、閘門與攔污柵，找到碎屑堆、變形的封水件、混凝土剝落、裂縫、閘門導槽缺陷（[Renewable Energy World / PSE Lower Baker](https://www.renewableenergyworld.com/?p=728924365)）；BC Hydro 在**發電機停機維修期間**以 ROV 檢查 27 m 深的攔污柵（[SEAMOR BC Hydro](https://seamor.com/bchydro/)〔廠商〕）；另一案例搜尋掉落的閘門封水壓板，確認它不在攔污柵、壓力鋼管或蝸殼內（[VideoRay USBR](https://videoray.com/wp-content/uploads/2021/09/Hyd_USBR.pdf)〔廠商〕）。
- **真實程序〔假設，綜合〕**：
  1. **機組停機、閘門關閉、上鎖掛牌**——這是安全前提（進水口吸力會把 ROV 和纜線吸進去）。
  2. 從壩頂或浮台下水，纜線沿壩面垂下。
  3. 攔污柵以格網方式逐格檢查，記錄堵塞率、斷柵、變形；閘門檢查封水件與導槽。
  4. 若要進入壓力鋼管：長纜線、無自然光、只有一條路回來。
- **交付物**：每片攔污柵的狀況與堵塞率、異常照片、混凝土缺陷清單、淤積深度。
- **條件**：淡水、冷、深（數十公尺）、能見度差、壩面無特徵；若機組沒有完全停，有吸入流。
- **常見狀況**：纜線纏漂流木；在無特徵混凝土面上迷失方位；淤泥揚起；在管道內纜線摩擦。
- **裝備**：觀測級 ROV、燈、成像聲納、可選長纜（壓力鋼管）。

### 2.8 沉船與水下考古調查 ●

- **委託方**：文化資產主管機關、大學與博物館、沉船業主或保險（打撈評估）、環保單位（沉船油料洩漏）、紀錄片團隊。
- **工作內容**：非接觸式紀錄（**不碰、不揚沙、不拿走東西**）；照片測量（photogrammetry）建立 3D 模型與平面圖。低成本 ROV＋GoPro 已被用來做沉船 3D 模型與 2D 平面圖（[ECU 論文](https://thescholarship.ecu.edu/handle/10342/6524)）；有方法在 328 m 深沉船上以 10 Hz 同步拍照並即時檢查覆蓋均勻度（[ROV 3D 計畫，CNR](https://chloe.cnr.it/s/DHeLO/item/12111)）；NOAA 說明 photogrammetry 用 2D 照片建立 3D 模型或照片鑲嵌圖（[NOAA](https://oceanexplorer.noaa.gov/fact-sheet/maritime-heritage-tools-fact-sheet)）。
- **程序〔假設，綜合〕**：先以聲納建立概略形狀與危險物（漁網、桅桿、纜繩）；規劃割草機式（lawnmower）航線，高重疊（常見 60–80%〔假設〕）；固定高度與速度；關鍵部位（船名、鐘、砲、錨、斷裂面）特寫；紀錄附著與劣化。
- **條件**：已在現有 `wreck_survey`、`korean_castle` 中涵蓋：30 m 左右、能見度 4 m、殘骸細線、泥底。
- **常見狀況**：勾纏（現有 `incident_wreck`）、揚沙、在鋼殼旁羅盤失準、進入艙內（禁止）。
- **裝備**：觀測級 ROV、高畫質相機、定位（USBL）、可選雷射尺與成像聲納。

### 2.9 科學調查與採樣 ●（目視、樣線）／◐（簡單採樣）／○（多數深海採樣）

- **委託方**：大學、海洋研究所、國家公園、漁業單位、環評顧問。
- **工作內容**：生態樣線（transect：沿捲尺或預設航線等高度、等速錄影計數）、棲地製圖、物種紀錄、水質剖面（CTD）、採樣。
- **採樣工具**（大型研究 ROV）：推管式岩芯（push core，最常見的沉積物工具，機械手握住壓入海床）、抽吸採樣器（slurp）、Niskin 採水瓶（機械手拉觸發線關閉）、抓斗、珊瑚剪；NOAA 強調**只在絕對必要時才採樣**（[NOAA 深海採樣說明](https://oceanexplorer.noaa.gov/edu/materials/deep-sea-sampling-fact-sheet.pdf)、[OET 採樣程序](https://nautiluslive.org/science/sampling-procedures)、[WHOI Jason](https://ndsf.whoi.edu/jason/systems-jason)）。觀測級 ROV 可用夾爪取小型樣本或放置小型儀器〔假設〕。
- **現有場景**：`coral_reef`、`seagrass_meadow`、expedition 模式的 `deploy` 任務（觀測儀部署）已涵蓋一部分。
- **條件**：保護區、不可碰觸生物、要慢、離底距離要穩。
- **常見狀況**：推進器揚沙毀掉樣線影像、碰到珊瑚、光線驚嚇生物。

### 2.10 冰下作業 ◐

- **委託方**：極地研究計畫、冰湖研究、北方港口（冬季）、冰下搜救。
- **實際做法**：小型載具可從冰上鑽孔下去：SCINI 可穿過 20 cm 冰孔、400 m 雙線纜、300 m 深；另一案例可穿過 15 cm 冰孔；多數 ROV 需要約 1 m 的冰洞（[NSF 計畫摘要](https://demo.bco-dmo.org/project/743648)、[Marine Technology News / Icefin](https://www.marinetechnologynews.com/news/antarctic-researchers-prepare-space-518095)）。從船在冰緣下水後鑽入冰下調查到纜長上限；冰緣附近需要先布設聲學導航（[Whitcomb PTC 2013](https://sundowner.colorado.edu/seefeldt/ptc-2005_2016/2013_pdf/PTC_2013_Whitcomb.pdf)）。Icefin 的光纖纜同時負責通訊、資料與緊急回收（同 Icefin 連結）。
- **遊戲重點**：**頭頂是冰，沒有「往上浮就安全」**；唯一的回家路是那個冰洞，纜線是導航線；高緯度羅盤不可靠〔假設〕；冷水電池與纜線變硬〔假設〕；冰下光線極暗、但水通常很清。
- **觀測級能否做**：小型觀測級可以，但需要能穿過冰孔的機體與冰上下水設備；X1 類尺寸是否能過特定冰孔需查證，**不要寫死**。

### 2.11 其他（不必單獨成關，可做支線）

- **橋墩沖刷**（河流，強流＋濁水）〔FHWA 架構，同 2.2〕。
- **水族館／海洋公園水槽**（清潔確認、觀察）〔假設〕。
- **船隻失事後油料洩漏點調查**〔假設〕。
- **漁具、廢棄漁網（幽靈網）調查與移除**——觀測級可調查，移除常需潛水員或作業級〔假設〕。
- **核電廠／工業水槽與取水口**〔假設：常見於廠商案例，本次未查〕。

---

## 3. 海纜與離岸風電專章

### 3.1 觀測級 ROV 在風場與海纜的真實工作

| 工作 | 觀測級做什麼 | 量什麼／交什麼 | 依據 |
|---|---|---|---|
| 單樁／導管架 GVI | 由上到下環繞、看塗層、海生物、陽極、結構損傷 | 錄影、照片、海生物剖面、陽極消耗 % | Acteon CVOW、Cwind |
| CP 調查 | 接觸式探針在鋼構與陽極上讀電位；或場梯度感測器 | mV 讀數表（vs Ag/AgCl）、陽極電流估計 | FORCE、MFE |
| 沖刷調查 | 沿樁底繞圈、量沖刷坑深度、看拋石移位 | 沖刷深度（多點）、保護層狀況 | Acteon CVOW（多波束為主） |
| 海纜進樁段（CPS） | 從 J 型管口追到 CPS 末端 | CPS 擺動磨損、裸露、懸空長度與高度 | Ørsted 招標、OWC 白皮書 |
| J 型管 | 喇叭口（bellmouth）、封口、外部支架 | 照片、密封狀態（洩漏影響腐蝕） | Intertek |
| 陣列纜目視路由 | 沿海纜飛，記錄 KP 事件 | 事件表、照片、裸露／懸空清單 | 一般調查實務 |
| 交越點 | 看保護墊、拋石、間距 | 交越點狀況報告 | ICPC |
| 作業級工作的監看 | 提供第二視角、監看切割與回收 | 即時影像 | Rotech 案例「客戶 ROV 提供即時影像」 |

〔廠商〕Cwind 以高畫質 ROV 做單樁、沖刷保護與海纜檢查（[Windtech](https://www.windtech-international.com/projects-and-contracts/cwind-provides-rov-subsea-inspections-for-e-on-at-amrumbank-west)）。

### 3.2 作業級 ROV 在風場與海纜的工作（觀測級做不到）

- 切纜（抓切工具、鑽石線鋸）、把纜頭吊上船；
- 剝埋（de-burial）與重新埋設（噴沖埋設機、犁）；
- 安裝保護墊、拋石引導、更換 CPS；
- 以磁場或音頻追蹤器精確定位故障（多裝在作業級上）；
- 清除海生物（水刀、刷）、扭力工具操作閥門、熱刺（hot stab）液壓介面；
- 吊放重物（> 數十公斤）、連接吊索。

### 3.3 生涯：從觀測級到作業級

建議把「升級」做成**證照＋裝備＋角色**三條線，而不是單純換一台更強的車：

1. **觀測級駕駛（Class I）**：港口、船殼、養殖、小型搜尋。學會纜線管理、看懂濁水影像、拍出合格照片。
2. **觀測級＋配件（Class IIA）**：解鎖雷射尺、DVL、成像聲納、CP 探針、海纜追蹤器、夾爪。開始接風場 GVI、CP、沖刷、海纜路由調查。
3. **作業級監看員**：在作業級切纜、回收、埋設任務中操作觀測級 ROV 提供第二視角——**這是真實存在的角色**（Rotech 案例中由客戶的 ROV 提供即時影像）。玩家要負責：保持安全距離、不讓自己的纜線與作業級的纜線／吊索纏在一起、在對方被泥沙遮住時告訴對方位置（多人協作可由第二玩家駕駛作業級）。
4. **輕作業級駕駛（Class IIB，Falcon 類）**：吸死魚、輕型夾取、放置小型儀器、扶住吊索。
5. **作業級駕駛（Class III）**：切纜、回收、噴沖埋設、保護墊安裝。需要新的載具與機械手模型（目前模擬器沒有，見 §7）。

真實業界的對應：IMCA R 002 規定 ROV 入門課程，2024–2025 年起開始把模擬器時數納入制度（見研究報告「業界考核以證據為本」一節）。遊戲中的「證照」可以參考這套：**入門 → 駕駛／技術員（Pilot Technician）Grade II → Grade I → 監督（Supervisor）**〔二手：IMCA 職級名稱為業界常見用法，本次未查原文〕。

---

## 4. 真實作業術語與交付物（給玩家看得懂的版本）

> 遊戲內顯示時用中文為主，英文縮寫放括號。新字串依 AGENTS.md 放 `STRINGS`／T09 字串表。

| 術語 | 真實意義 | 給玩家的說法／遊戲裡怎麼用 |
|---|---|---|
| GVI（General Visual Inspection）| 一般目視檢查：整體狀況、大範圍掃過 | 「巡一遍」：以覆蓋率計分 |
| CVI（Close Visual Inspection）| 近距細部檢查，常需先清除附著物、用量具 | 「貼近細看」：要求距離 < 0.5 m、對正、照片帶比例尺（[Deep Trekker](https://www.deeptrekker.com/news/difference-between-gvi-cvi)〔廠商〕） |
| Level I／II／III | 美國碼頭／橋墩水下檢查分級（I 巡視、II 清帶細看抽樣、III 非破壞檢測） | 工單上寫「Level I」＝只要覆蓋；「Level II」＝指定幾根樁要量海生物與拍特寫（Level III 定義本次未查到原文） |
| 事件紀錄（Eventing／Event log）| 調查時每遇到狀態變化就按鍵記一筆：時間、位置、事件碼、說明 | 遊戲按一鍵「記事件」，選事件碼；準確度與 KP 誤差計分 |
| KP（Kilometre Point）| 沿管線／海纜從起點量的距離 | HUD 顯示 KP；事件要記在正確 KP ±（容許誤差） |
| 時鐘方位（Clock position）| 管線截面上缺陷的位置，以 12 點為頂部 | 管線異常回報時選 12／3／6／9 點 |
| 異常（Anomaly）| 偏離設計或上次調查狀態的發現 | 任務目標：找到並標記 N 個異常；漏報、誤報都扣分 |
| 異常等級 | 一般分「立即處理／下次維修／監測」三級左右〔假設：各業主規格不同，無統一碼〕 | 玩家判斷嚴重度，客戶依此給回饋 |
| 裸露／埋設／懸空（Exposure／Burial／Free span）| 海纜或管線的狀態 | 三種路段在場景中可見；懸空要量長度與離底高度 |
| 覆土深度（Depth of cover／DoB）| 海纜頂部到海床的深度 | 用追蹤器讀數；HUD 顯示「埋深 0.8 m」 |
| CP 讀數 | 結構對 Ag/AgCl 參考電極的電位。常見準則：比 −800 mV 更負表示受保護，比 −800 mV 正則保護不足；過負（約 −1050 mV 以下）可能過保護〔二手：[Scribd 調查服務文件](https://www.scribd.com/document/427504377/corrosion)；另一來源給 −850 至 −950 mV，以業主規格為準〕 | 探針接觸穩定 2–3 秒才讀到；顯示 mV；玩家判定合格與否 |
| 陽極消耗 % | 犧牲陽極剩餘量的目視估計 | 照片上選 0／25／50／75／100% |
| 海生物（Marine growth）| 分硬附著（貽貝、藤壺、管蟲）與軟附著（海鞘、海藻、海葵），記錄厚度、組成、覆蓋率；一份規格的清除門檻是硬 0.1 m、軟 1 m〔二手：[Bentley APM 規格](https://help-apm.bentley.com/7/en/eam/1040129341_Specifications_marin.html)、[MDPI](https://www.mdpi.com/2077-1312/6/1/2)〕 | 以雷射尺量厚度；選硬／軟、覆蓋率 |
| 附著評級 0–4 | IMO 2023 生物附著指引的船殼評級 | 船殼任務的計分表 |
| 沖刷（Scour）| 結構物周圍海床被流掏空 | 量樁邊 4 個方位的沖刷深度 |
| CPS（Cable Protection System）| 海纜進樁段的保護套管 | 檢查磨損、擺動、末端埋入狀況 |
| J 型管（J-tube）／喇叭口（bellmouth）| 海纜進入導管架的導管 | 拍喇叭口、看封口 |
| 疊字（Overlay）| 影像上的日期、時間、深度、航向、KP、專案名 | 照片要有疊字才算有效證據 |
| 打板（Clapper／Slate）| 錄影開頭拍下地點、人員、潛次 | 任務開場步驟，忘了扣報告分 |
| 潛次紀錄（Dive log）| 每次下潛的時間、人員、目的、結果 | 自動產生，玩家補填備註 |
| 預潛檢查表（Pre-dive checklist）| 每項 pass／fail／N/A，可記錄執行人（[VideoRay](https://download.videoray.com/documentation/pro_4/html/service_predive.html)） | 已有下水閘門；生涯中逐步擴充 |
| 纜線手（Tether handler／Tender）| 在甲板上放收纜線的人 | NPC 或第二玩家；「放纜」「收纜」指令 |
| 平潮（Slack water）| 漲退潮轉換時流速最小的時段 | 風場任務的倒數計時窗口 |
| LOTO（上鎖掛牌）| 確認危險設備（螺槳、泵、進水口）已停用上鎖 | 任務前確認步驟；跳過即失敗（安全違規） |
| 交越（Crossing）| 海纜跨越另一條海纜／管線 | 一種特殊場景與檢查表 |
| RPL（Route Position List）| 海纜路由座標表 | 任務簡報中的路由圖 |
| ROV 分級 Class I–III | IMCA R 004 | 生涯證照等級 |

---

## 5. 心流（Flow）設計原則：怎麼套到這個生涯

依據：Csikszentmihalyi 的心流概念被 Jenova Chen 套到遊戲上——挑戰超過能力會焦慮，能力遠超挑戰會無聊，要讓玩家留在「心流區」，並讓不同程度的玩家都能找到自己的區間（[Chen, CACM 2007](https://cacmb4.acm.org/magazines/2007/4/5692-flow-in-games-and-everything-else/fulltext)、[Chen 論文 PDF](https://khoury.northeastern.edu/~lieber/courses/csu670/f08/materials/p31-chen-flow-in-games.pdf)）。也有研究指出「平衡」不一定決定體驗，平衡與正面體驗之間未必是倒 U 形（[ACM 2023](https://unpaywall.org/10.1145%2F3611065)），所以平衡只是起點，還要靠回饋與選擇權。

本專案的具體規則：

1. **一次只加一個新變數**。每關表格中的「新元素」欄只有一項；其他條件沿用已學過的。例外是章末「綜合考核」，只組合已學過的元素。
2. **先在安全環境學，再在壓力下用**。每個新變數先出現在一個低風險版本（例如低能見度先在無結構物的開放水域），下一次才和結構物、纜線組合。
3. **快速重試**：每個任務 3–6 分鐘可完成核心目標〔假設〕；失敗後從最近的檢查點重來（現有 campaign 有 `checkpoint` 節點），不重播長對話。
4. **清楚的即時回饋**：
   - 覆蓋率：樁柱／網衣上已看過的區域淡色標示（屬「超出真機」的輔助，需註冊 fidelity 項目，`real` 預設關；真實模式改成任務結束後在講評中才顯示）。
   - 照片：拍下後立刻顯示「合格／不合格（距離太遠、沒對正、沒疊字、模糊）」。
   - 事件：記錄時立刻顯示 KP 誤差。
5. **主線要求「可用」，獎牌是精熟目標**：
   - 銅：交出客戶可接受的報告（必要目標完成、無嚴重碰撞、載具回收）。
   - 銀：加上時間或纜線管理門檻。
   - 金：零接觸、照片全合格、事件 KP 誤差小、在平潮窗口內完成。
   - 隱藏挑戰：例如「不用定深完成」「燈光只開一檔完成揚沙關」。
6. **不要硬鎖**。TRANSoM 研究中，通關式進度讓 8 人中有 3 人到不了最難關卡（強流、低能見度），而自由練習組把時間花在較難情境上（見研究報告）。所以：
   - 每關可以「降級完成」：中途中止、安全撤離並交出部分報告，拿到較低評等，劇情照樣推進（真實業界中「判斷中止」本身就是正確答案，現有 `incident_*` 已採此精神）。
   - 失敗 2–3 次後，客戶 NPC 主動提議「改天平潮再試」（=降低流速）或「先去練習場」，不強迫。
   - 所有已解鎖場景都能自由練習。
7. **擬真模式與輔助**：生涯任務的驗收基準是 `real` 預設；Steam 版可預設 `assisted`。評分時可記錄是否使用超出真機的輔助（例如加註「輔助模式」標章），但不擋進度。**不得為了難度曲線改物理**——難度只能來自任務條件（流速、能見度、纜長、時間窗口、目標數量）。
8. **敘事節奏**：每章 3–5 個任務，最後一個是「綜合考核」或事故；章與章之間有「休息關」（低壓力、好看的場景，例如礁區生態觀察），讓玩家在挑戰之後恢復。
9. **報告即獎勵**：任務結束時產生一份像真的檢查報告（疊字照片、事件表、評級），玩家看到自己的成果被「交出去」。這是本模擬器相較一般遊戲的獨特賣點，也與內部訓練的講評需求一致（見 `research_notes/訓練/debrief.md`）。

---

## 6. 生涯任務階梯（28 關提案）

### 6.1 共通欄位說明

- **場景**：現有 `scenarios.py` key（若適用）；`NEW:` 表示需要新場景（見 §7）。
- **計分維度**（共通，各關權重不同）：
  - 準確（照片合格率、事件 KP 誤差、量測誤差、異常判讀正確率）
  - 時間（相對工時預算；有平潮窗口的關卡為硬限制）
  - 纜線管理（峰值張力、繞樁圈數、是否卡纜、放出長度是否最少）
  - 無接觸（碰撞次數與嚴重度，沿用現有 `PENALTY = touch/hard/severe`）
  - 報告品質（必填欄位、打板、錄影是否全程、照片有疊字）
  - 安全（LOTO、中止判斷、回收程序）
- **共通失敗條件**：載具遺失（纜線斷）、嚴重碰撞（養殖網破、撞進進水口）、安全違規（未確認 LOTO 就靠近螺槳／進水口）、錄影未開（「沒錄到就不存在」：任務仍可完成但報告不及格）。
- **獎勵**：報酬（遊戲貨幣）、聲譽（客戶別）、證照、裝備或載具解鎖。

### 6.2 序章：取得執照（現有 campaign 序章與 B 課程可直接沿用）

| # | 標題 | 客戶 | 場景 | 目標（可量化） | 新元素 | 失敗／成功 | 主計分 | 獎勵 | 對應真實程序 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 水池檢查潛 | 自家公司 | `tutorial_pool` | 完成預潛檢查表；解鎖；懸停 30 s 偏移 < 0.5 m；拍 3 張帶疊字的照片；回收前鎖定並停錄 | 預潛閘門、拍照疊字 | 成功：全部完成／失敗：在水面外解鎖 | 程序正確 | 入門證、觀測級 ROV | VideoRay／Blue Robotics 預潛檢查、FIFISH 下水程序 |
| 2 | 開放水域熟悉 | 自家公司 | `open_water` | 通過 4 檢查點；定深 ±0.3 m；鬆桿後停住並觀察漂移 | 鬆桿漂移（推力≠速度） | 超時 | 航線偏差 | 解鎖 DVL 說明 | 研究報告「推桿是推力」 |
| 3 | 碼頭外的第一張工單 | 小漁港管理處 | `harbor_inspection` | Level I：6 根樁各一趟垂直航次（覆蓋 ≥ 80%）；每樁 1 張疊字照；纜線不繞樁 | 覆蓋率與「纜線同側」規則 | 繞樁 ≥ 1 圈即需解纏（不直接失敗） | 覆蓋率、纜線 | 港務聲譽 | VideoRay PPI SOP |

### 6.3 第一章：港口與船舶（觀測級 Class I）

| # | 標題 | 客戶 | 場景 | 目標 | 新元素 | 失敗／成功 | 主計分 | 獎勵 | 真實程序 |
|---|---|---|---|---|---|---|---|---|---|
| 4 | 碼頭 Level II 抽樣 | 港務局 | `harbor_inspection`（低能見度 1.5 m 變體） | 指定 3 根樁 × 3 高程量海生物厚度（雷射尺誤差 ±2 cm）並選軟／硬；離樁距離維持 0.7×能見度 ±0.3 m | **低能見度** | 漏量任一點不能交件 | 量測準確、距離 | 解鎖雷射比例尺 | TRB Level II、VideoRay 距離規則 |
| 5 | 貨輪船殼附著評級 | 船舶管理公司 | `hull_inspection` | 5 個 niche areas（2 海底門、舵、螺槳、測深換能器）各拍 1 張並給 0–4 評級；平底兩條航線 | **在船底下方沒有水面參考**；卡在舭龍骨 | 未做 LOTO 確認即靠近螺槳＝失敗 | 評級正確、纜線 | 船東聲譽 | IMO 2023 生物附著指引 |
| 6 | 擱淺後的螺槳 | 保險公證人 | NEW：船尾細部（螺槳、舵、艉軸）| 4 片葉緣各 1 張近照（距離 < 0.5 m、對正 < 15°）；量最大缺口尺寸；舵銷 2 張 | **CVI 近距對正**＋船尾**他船螺槳流**（陣風型擾動） | 碰螺槳 hard 以上＝失敗 | 照片合格、尺寸誤差 | 解鎖「保險」客戶線 | 船級 IWS 對舵與螺槳的要求 |
| 7 | 港內掉落物 | 工程船隊 | `sonar_search` | 以聲納在 50×50 m 內找到掉落的測量儀並以影像確認；用夾爪掛上回收繩（或標記給潛水員） | **成像聲納** | 30 分鐘內未找到＝可中止交「搜尋紀錄」（銅） | 搜尋效率 | 解鎖成像聲納、夾爪 | RCMP 先聲納後確認流程 |
| 8 | 章末：交班前複查 | 港務局 | `harbor_inspection`（現有 `harbor_signoff` 章節）| 複查上次的 3 個異常是否惡化；每個異常與上次照片同角度重拍 | **與歷史資料比對**（重現同一視角） | — | 重現精度 | 證照：Class I 駕駛 | 定期檢查的趨勢比對 |

### 6.4 第二章：養殖場（觀測級＋夾爪）

| # | 標題 | 客戶 | 場景 | 目標 | 新元素 | 失敗／成功 | 主計分 | 獎勵 | 真實程序 |
|---|---|---|---|---|---|---|---|---|---|
| 9 | 網衣巡檢 | 海上箱網養殖場 | NEW：箱網（含魚群） | 網內側 3 個深度環繞一圈＋網底放射 4 條；找到 2 個破洞，回報方位（時鐘）、深度 ±1 m、大小 ±5 cm | **魚群遮擋視線＋柔性網衣**（靠太近推進器吸網） | 網衣被吸入推進器＝失敗；驚嚇魚群（高速接近魚群）扣分 | 破洞找全、定位精度 | 養殖場聲譽 | 廠商描述的網衣檢查；NS 9415 防脫逃 |
| 10 | 死魚回收 | 同上 | NEW：箱網網底 | 以夾爪回收 5 尾死魚放入收集籃；不碰網底 | **夾爪＋負浮力物件**（夾住後配平改變） | 掉落可重夾；碰網＞3 次扣分 | 回收數、時間 | 解鎖夾爪升級 | 廠商死魚回收描述 |
| 11 | 颱風過後的錨繩 | 同上 | NEW：箱網繫泊系統（錨繩、浮標、錨） | 沿 2 條錨繩從浮標到錨（各約 60 m）並記錄 3 個異常（磨損、纏繞物、移位錨）；纜線不可跨過錨繩 | **近水面波浪**（湧浪使 ROV 上下晃）＋長距離沿繩 | 纜線纏在錨繩＝需解纏 | 異常、纜線 | 證照：Class IIA（配件操作） | 繫泊檢查〔假設〕 |

### 6.5 第三章：公共服務（搜救與水庫）

| # | 標題 | 客戶 | 場景 | 目標 | 新元素 | 失敗／成功 | 主計分 | 獎勵 | 真實程序 |
|---|---|---|---|---|---|---|---|---|---|
| 12 | 水庫進水口攔污柵 | 水庫管理處 | NEW：混凝土壩面＋進水口＋攔污柵 | 確認 LOTO（閘門關、機組停）；6 片攔污柵逐片拍照並給堵塞率 0／25／50／75／100%；找出 1 根斷柵 | **淡水、冷、無特徵壁面**（方位感） | 未確認 LOTO 就下水＝失敗 | 判讀、覆蓋 | 公部門聲譽 | PSE Lower Baker、BC Hydro 案例 |
| 13 | 湖底證物搜尋 | 警察局 | NEW：湖泊泥底（零能見度、樹枝） | 在 30×30 m 搜尋區以聲納建立格網；找到 1 件證物（背包）並在原位拍照、記座標後才回收；排除 3 個假目標（石頭、樹樁） | **零能見度：只能靠聲納**＋揚沙 | 未在原位拍照即移動證物＝報告不合格 | 搜尋效率、證據鏈 | 解鎖警方客戶線 | RCMP 湖泊搜索流程 |
| 14 | 壓力鋼管入口找異物 | 水力電廠 | NEW：進水口內部、壓力鋼管入口 | 進入閘門後方 40 m 管段找掉落的封水壓板；全程纜線無磨擦超限 | **封閉空間：只有一條路回來** | 纜線磨損值超過門檻＝中止 | 纜線、時間 | 證照：特殊環境 | USBR 封水壓板案例 |

### 6.6 第四章：離岸風電（觀測級＋配件）

| # | 標題 | 客戶 | 場景 | 目標 | 新元素 | 失敗／成功 | 主計分 | 獎勵 | 真實程序 |
|---|---|---|---|---|---|---|---|---|---|
| 15 | 第一支單樁 | 風場營運商 | `monopile_current`（加陽極、海生物、平台吊臂下水） | GVI：由飛濺區到海床 4 個高程環繞；6 個陽極各拍正面照並估消耗 % | **平潮窗口倒數**（流速隨時間上升） | 窗口結束仍在水下：流速超限→須撤離（現有 `incident_current` 邏輯） | 時間、照片 | 風場聲譽 | Acteon CVOW |
| 16 | CP 量測 | 同上 | 同上 | 用 CP 探針在 4 個鋼構點＋6 個陽極各取穩定讀數（接觸 ≥ 3 s，探針雙電極差 < 10 mV〔假設門檻〕）；判定哪一點保護不足 | **受控接觸**（以往接觸都扣分，這裡要「輕輕頂住」） | 撞擊力超過門檻＝扣分且讀數無效 | 讀數有效率、判定 | 解鎖 CP 探針 | FORCE、MFE Polatrak |
| 17 | 沖刷調查 | 同上 | NEW：單樁＋沖刷坑＋拋石保護層 | 樁邊 N/E/S/W 4 點量沖刷深度（誤差 ±0.2 m）；找出 1 處拋石移位 | **DVL 在拋石上跳動／短暫失鎖** | — | 量測、判讀 | 解鎖 DVL 說明頁 | Acteon CVOW 沖刷保護 |
| 18 | 海纜進樁段 | 同上 | NEW：CPS＋J 型管口＋懸空段 | 從開孔追到 CPS 末端埋入點；量懸空長度（±0.5 m）與最大離底高度（±0.1 m）；判定 CPS 是否在石頭上磨 | **近底揚沙＋自己的纜線與海纜並行**（不可纏） | 碰到海纜 hard 以上＝失敗 | 量測、無接觸 | 海纜業主聲譽 | Ørsted 招標、OWC CPS 白皮書 |
| 19 | 導管架 J 型管 | 同上 | `jacket_inspection`（加 J 型管、喇叭口） | 3 個 J 型管喇叭口各 2 張照（正面、側面）；3 個高程量海生物 | **在結構內部的纜線管理**（斜撐） | 卡纜不解＝中止 | 纜線、照片 | 證照：風場 GVI | IMCA SF 02/23（反例） |
| 20 | 章末：平潮兩支樁 | 同上 | `jacket_inspection`＋`monopile_current` 綜合 | 一個平潮窗口內完成兩支基礎的陽極與 CPS 簡查；流速上升時自己判斷是否中止 | **綜合（無新元素）** | 判斷中止並安全回收＝銀 | 綜合 | 風場長期合約 | — |

### 6.7 第五章：海纜

| # | 標題 | 客戶 | 場景 | 目標 | 新元素 | 失敗／成功 | 主計分 | 獎勵 | 真實程序 |
|---|---|---|---|---|---|---|---|---|---|
| 21 | 陣列纜路由調查 | 海纜業主 | NEW：海床上的海纜（埋設／裸露／懸空交替） | 沿纜 200 m，海纜保持在畫面中央（側偏 < 2 m 的時間 ≥ 90%）；記錄所有狀態變化事件（KP 誤差 ±2 m） | **KP 事件紀錄** | 漏記 > 2 個事件＝報告不合格 | 事件準確、航線偏差 | 解鎖事件碼表 | 一般路由調查 |
| 22 | 看不見的海纜 | 同上 | 同上（埋設段延長） | 用追蹤器沿埋設段 150 m；每 10 m 記一次埋深；找出埋深 < 0.6 m〔假設門檻〕的區段 | **只靠儀表追看不見的目標** | 偏離海纜 > 5 m 超過 20 s＝需回到上個事件點 | 埋深紀錄、偏離 | 解鎖追蹤器 | TSS 440 |
| 23 | 交越點 | 同上 | NEW：海纜跨越鋼管線，保護墊與拋石 | 檢查 4 塊保護墊位置與狀況、量交越淨距；在管線上方完成而不使用自動航向 | **鋼管線旁羅盤失準＋保護墊邊緣揚沙** | — | 判讀、穩定性 | 解鎖交越檢查表 | ICPC 交越建議 |
| 24 | 錨害故障定位 | 海纜業主＋保險 | NEW：海纜路由＋錨拖痕＋損傷點 | 依音頻追蹤從預估 KP 往兩側搜尋；找到錨拖痕並沿痕找到損傷點；拍 3 張帶疊字證據照 | **通訊品質下降**（影像間歇卡頓／延遲增加，依 comms 研究） | 找到損傷點即成功 | 時間、證據 | 證照：海纜調查 | Bawart 故障定位流程、TSS 350 |

### 6.8 第六章：進階與作業級

| # | 標題 | 客戶 | 場景 | 目標 | 新元素 | 失敗／成功 | 主計分 | 獎勵 | 真實程序 |
|---|---|---|---|---|---|---|---|---|---|
| 25 | 沉船 3D 紀錄 | 文化資產主管機關 | `korean_castle` 或 `wreck_survey` | 以割草機航線完成照片測量覆蓋 ≥ 85%（重疊 ≥ 60%）；零接觸；不揚沙（揚沙量低於門檻） | **零接觸＋覆蓋均勻**（高重疊） | 任一次接觸＝無法金牌；進入貨艙＝失敗 | 覆蓋、無接觸 | 文化資產聲譽 | ECU 低成本 ROV 照片測量 |
| 26 | 冰下取樣 | 極地研究站 | NEW：冰層＋冰孔＋冰下海床 | 從冰孔下水；沿預定樣線 80 m 錄影；放置 1 個溫度記錄器；回到冰孔回收 | **頭頂是冰：唯一出口是冰孔**；高緯羅盤不可靠 | 迷失＞纜長；無法回到冰孔＝失敗 | 導航、纜線 | 科研聲譽 | SCINI、Icefin |
| 27 | 切纜監看 | 風場營運商 | NEW：海纜修復現場（作業級 NPC／第二玩家） | 操作觀測級 ROV 為作業級提供第二視角：保持 3–5 m 監看距離；切割期間鏡頭不離切點；自己的纜線不與作業級臍帶纜或吊索交叉 | **多載具與多條纜線** | 纜線互纏＝失敗 | 監看品質、纜線 | 證照：作業級見習 | Rotech 案例（客戶 ROV 提供即時影像） |
| 28 | 終章：風暴後的緊急巡檢 | 風場營運商 | 綜合：單樁＋海纜（夜間） | 夜間、有限平潮、兩支樁的 CPS 快查＋海纜裸露段複查；資源有限下排優先順序，交出「立即處理」清單 | **夜間＋優先順序判斷**（綜合） | 安全回收並交出清單即成功；異常漏判扣分 | 綜合 | 結局：升任 Supervisor 或轉作業級駕駛 | 綜合 |

〔可延伸〕Falcon 類輕作業級的支線：大量死魚抽吸、扶吊索放置觀測儀（現有 expedition `deploy`）；Class III 作業級（切纜、噴沖埋設）需新載具，列為未來 DLC 等級工作。

### 6.9 與現有內容的對應（避免重複）

| 現有 | 本提案 |
|---|---|
| 序章（`tutorial_pool`）、B01–B04 | #1–#3；B 課程保留為「公司內訓」 |
| 第一章港灣／船殼／交班複查 | #3–#8 的骨架；需加 Level II、IMO 評級、螺槳細部 |
| 第二章離岸（`jacket_inspection`） | #19；新增單樁系列 #15–#18、#20 |
| 第三章礁區（`coral_reef`） | 作為第二章與第三章之間的「休息關」，或科研支線 |
| 第四章沉船（`wreck_survey`） | #25 |
| 終章夜間回收 | #28 夜間元素沿用 |
| `incident_*`、A01–A04、I01–I04 | 保留為「事故訓練」；生涯中客戶任務失敗時可推薦對應訓練 |
| `sonar_search` | #7、#13 的基礎 |
| `seagrass_meadow` | 科研支線（樣線調查） |
| expedition 模式（inspect／recover／deploy） | #10（recover）、#26（deploy）可沿用 |

---

## 7. 需要的新場景與資產

難度：低＝現有幾何組合即可；中＝新模型＋少量新邏輯；高＝新物理或大型模型。

| 場景／資產 | 用於 | 擬真重點 | 參考影像描述（不存圖） | 難度 |
|---|---|---|---|---|
| **養殖箱網**（圓形 HDPE 浮框，直徑 30–50 m〔假設〕，網深 10–30 m，網底沉子環；魚群） | #9–#11 | 網衣是柔性的，隨流變形、近處網目清楚、遠處像霧；魚群繞網逆時針或順時針巡游〔假設〕，會避開 ROV；餌料使水濁；破洞是網目斷裂的不規則缺口 | 水下從網內望向網壁：一面細網格向下延伸到黑暗，魚群像銀色牆在面前流過；網外有綠色懸浮物 | 高（柔性網、魚群 boids、網與推進器吸入互動） |
| **繫泊系統**（錨繩、浮標、錨、卸扣） | #11 | 繩子懸鏈線形狀、附著海藻；湧浪近水面 | 一條長著海藻的粗繩斜斜消失在綠色深處 | 中 |
| **海床上的海纜**（埋設、裸露、懸空、沙波） | #21–#24、#27 | 直徑約 10–25 cm〔假設〕；裸露段有附著、懸空段跨在沙波凹處；埋設段只看到一條淺溝或完全看不到；錨拖痕是長條溝 | 灰褐色沙底上一條黑色粗纜，一端從沙裡冒出，前方跨過一個小坑懸在半空 | 中（程序化路徑＋高度場） |
| **交越點**（鋼管線、混凝土保護墊、拋石） | #23 | 保護墊是一塊塊連結的混凝土塊；管線會造成羅盤偏差（沿用 `incident_compass` 邏輯） | 一排灰色混凝土塊壓在管線上，海纜從上面跨過 | 中 |
| **單樁＋沖刷坑＋拋石保護層＋CPS＋J 型管口** | #15–#18、#20、#28 | 樁徑 6–8 m（現有 6 m）；海生物分帶（近水面海藻、往下貽貝與海葵）；沖刷坑在樁邊最深；拋石大小不一會讓 DVL 跳；CPS 是黃色或黑色分節套管從樁側開孔斜出到海床 | 巨大的黃色鋼柱長滿白色海葵，底部一圈亂石，一條分節的黑色套管從樁身伸出鑽進石堆 | 中 |
| **陽極、CP 探針互動**（樁與導管架上的陽極塊；探針接觸讀數） | #15–#16 | 陽極有消耗程度的視覺差異；探針需穩定接觸才讀數 | 鋁色方塊陽極被白色腐蝕產物包覆，一側已明顯變薄 | 低（模型）＋中（接觸邏輯） |
| **J 型管喇叭口**（導管架上） | #19 | 喇叭口朝下、海纜從中穿出 | 一個向下張開的喇叭形鋼管口，海纜從中垂下 | 低 |
| **船尾細部**（螺槳、舵、舵銷、艉軸封；葉緣缺口） | #6 | 螺槳葉緣損傷（缺口、彎曲）、空蝕麻點、附著 | 青銅色四葉大螺槳，一片葉緣有缺口；旁邊是巨大的舵板 | 中 |
| **船殼 niche areas**（海底門格柵、測深換能器、舭龍骨） | #5 | 0–4 附著程度的貼圖變化 | 船底一個長方形格柵，格柵後面長滿管蟲 | 低–中 |
| **水庫壩面＋進水口＋攔污柵＋閘門** | #12、#14 | 淡水色（偏褐綠）、冷、壩面無特徵、攔污柵上掛漂流木與塑膠袋；閘門後方的進水口隧道 | 一面看不到盡頭的灰色混凝土牆，一排粗鋼條柵欄上卡著樹枝與垃圾 | 中 |
| **湖泊泥底搜救場**（樹枝、石頭、樹樁、證物、可選汽車） | #13 | 零到 1 m 能見度、極易揚沙（沿用 `incident_silt`）、聲納上石頭與目標難分 | 聲納畫面上扇形的灰色海底，幾個亮點與長條陰影；攝影機裡只有咖啡色的懸浮物 | 中 |
| **冰層＋冰孔＋冰下海床** | #26 | 冰底下表面不平、透光呈藍綠；冰孔是唯一亮點；水清但暗 | 從下往上看：一片起伏的淡藍白天花板，中間一個亮圓洞 | 中–高（頂部碰撞、光照） |
| **作業級 ROV（Class III）與切纜工具、吊索** | #27 | 大型框架、機械手、臍帶纜與 TMS；纜線間互動 | 黃色大型框架式 ROV，兩隻機械手，下方掛著切割工具 | 高（新載具與多纜互動；可先以 NPC 腳本化） |
| **夜間環境**（已有終章夜間元素） | #28 | 水面無光、只有燈 | — | 低 |
| **報告產生器**（疊字照片＋事件表＋評級 → 類真實檢查報告） | 全部 | 依 §4 欄位；可延伸既有講評 | — | 中 |
| **事件紀錄 UI 與 KP 顯示** | #21–#24 | 一鍵記事件＋事件碼選單 | — | 低–中 |

### 7.1 擬真注意事項

- 所有參數（網衣尺寸、海纜直徑、沖刷深度、CP 門檻）都是任務設定值，標示為〔假設〕，不代表任何特定場址或 X1 能力。
- 覆蓋率疊圖、目標標記、聲納輔助判讀等「超出真機」的顯示，必須註冊 fidelity 項目並在 `real` 預設關。
- 新場景要沿用現有水色、能見度、揚沙模型（見 `real_dive_footage.md` 的實測色值與能見度）。淡水水庫與湖應有自己的水色（偏褐綠），冰下應偏清澈藍綠〔假設〕。

---

## 8. 優先順序建議

**先做的 10 關**（新場景少、驗證核心玩法，括號為新增需求）：

1. #1 水池檢查潛（現有）
2. #3 碼頭第一張工單（現有場景＋覆蓋率計分）
3. #4 碼頭 Level II 抽樣（雷射尺）
4. #5 貨輪船殼附著評級（niche area 模型）
5. #7 港內掉落物（現有 `sonar_search`＋夾爪回收）
6. #9 網衣巡檢（新：箱網）
7. #15 第一支單樁（平潮窗口、陽極）
8. #17 沖刷調查（新：沖刷坑與拋石）
9. #18 海纜進樁段（新：CPS）
10. #21 陣列纜路由調查（新：海纜＋事件紀錄）

**先做的 5 個新場景**：

1. 海床上的海纜（埋設／裸露／懸空，可延伸交越與錨害）
2. 單樁基礎套件（沖刷坑、拋石、CPS、陽極、海生物分帶）
3. 養殖箱網（網衣＋魚群）
4. 水庫進水口與攔污柵
5. 湖泊泥底搜救場

---

## 9. 缺口與未查證項目

- IMCA R 004 Rev. 6 原文分級定義未取得（只有 Rev. 4 二手摘要）。
- 管線／海纜調查的**事件碼**沒有公開的統一標準，各業主自訂；本文的事件碼為設計提案。
- CP 合格準則各來源不一（−800 mV 或 −850 至 −950 mV vs Ag/AgCl），應以 DNV-RP-B401／ISO 15589-2 等標準原文確認（本次未取得）。
- 懸空篩選門檻（10 m）、海生物清除門檻（硬 0.1 m／軟 1 m）為二手資料。
- NS 9415 對網衣檢查頻率的具體條文未取得。
- Level III 的定義（ASCE MOP 130、TRB Circular 330）未取得原文。
- 各工作的工時多為推估。
- 船殼檢查的 LOTO 程序、海關用途、網衣檢查流程細節沒有一手 SOP。
- X1 類載具在各工作中的實際能力（抗流、夾爪尺寸、能否穿過冰孔）需依 `docs/reference/x1-measurement-checklist.md` 實測。

---

## 來源

- IMCA 分級：[Hydro International](https://www.hydro-international.com/content/article/trends-and-new-technology-in-the-rov-industry)、[Offshore Energy](https://offshore-energy.biz/2015/08/07/imca-work-class-rovs-most-used-in-2014)
- 船殼：[46 CFR 115.610 封存](https://webarchive.library.unt.edu/eot2008/20090509103623/http://edocket.access.gpo.gov/cfr_2002/octqtr/pdf/46cfr115.610.pdf)、[In-Water Survey 簡報](https://www.scribd.com/presentation/618082491/In-Water-Survey)、[Deep Trekker UWILD](https://www.deeptrekker.com/resources/uwild-best-practices)、[IIMS IMO 生物附著摘要](https://www.iims.org.uk/imo-biofouling-guidelines-key-recommendations/)、[Gard](https://gard.no/articles/hull-biofouling-key-recommendations)、[BIMCO](https://bimco.org/Insights%20and%20information/Safety%20Security%20Environment/20231018%20biofouling%20guidelines)、[IMO MEPC.1/Circ.918](https://wwwcdn.imo.org/localresources/en/OurWork/Environment/Documents/Biofouling%20pages/MEPC.1-Circ.918%20-%20Guidance%20On%20In-Water%20Cleaning%20Of%20Ships'%20Biofouling%20(Secretariat).pdf)
- 碼頭樁柱：[VideoRay PPI SOP](https://download.videoray.com/documentation/sop_ppi/html/_print.html)、[TRB Circular 498](https://onlinepubs.trb.org/Onlinepubs/trcircular/498V1/498V1-008.pdf)、[FHWA](https://webarchive.library.unt.edu/eot2008/20090509104124/http://www.fhwa.dot.gov/legsregs/directives/techadvs/t514021.htm)、[GEI](https://waterfront.geiconsultants.com/which-underwater-inspection-is-right-for-your-port-project-and-why-an-engineer-diver-is-best-for-the-job/)
- 養殖：[VideoRay 養殖](https://videoray.com/industries/aquaculture/)、[Global Seafood Alliance](https://www.globalseafood.org/advocate/partnership-aims-to-boost-efficiency-and-fish-welfare-through-expanded-rov-use-in-salmon-farming/)、[Bluezone Falcon](https://bluezonegroup.com.au/announcements/seaeye-falcon-for-aquaculture-support/)、[Deep Trekker 案例](https://www.deeptrekker.com/learn/3-ways-kana-upton-and-aqua-cage-fisheries-use-their-rov)、[Deep Trekker 脫逃](https://www.deeptrekker.com/news/preventing-aquaculture-fish-escapes)、[Standards Norway NS 9415](https://standard.no/en/sectors/fisheries-and-aquaculture/floating-aquaculture-farms/)、[Sands NYTEK23](https://www.sands.no/en/news/new-technical-requirements-for-aquaculture-facilities-in-the-sea-nytek23-and-ns-9415-2021/)
- 離岸風電：[Acteon CVOW](https://acteon.com/insights/case-studies/surveys-and-inspections-for-coastal-virginia-offshore-wind-pilot-project)、[FORCE Baltic 2](https://forcetechnology.com/no/cases/baltic-2-wind-farm-survey)、[Mercell／Ørsted 招標](https://www.mercell.com/permalink/174105658.aspx)、[Intertek MIC](https://www.intertek.com/wind/microbiologically-influenced-corrosion-offshore-wind-farm-foundations/)、[OWC CPS 白皮書](https://abl-group.com/wp-content/uploads/2022/10/OWC-White-Paper-Cable-Protection-Systems.pdf)、[Ashtead ROV3D](https://ashtead-technology.com/?p=21724)、[Windtech / Cwind](https://www.windtech-international.com/projects-and-contracts/cwind-provides-rov-subsea-inspections-for-e-on-at-amrumbank-west)、[Wikipedia Bend stiffener / CPS](https://en.wikipedia.com/wiki/Bend_stiffener)
- CP：[MFE Polatrak ROV II](https://mfe-is.com/offshore/polatrak-ii-rov-probe/)、[Scribd 腐蝕調查文件](https://www.scribd.com/document/427504377/corrosion)、[Justia 專利](https://patents.justia.com/patent/10961630)
- 海生物：[Deep Trekker GVI/CVI](https://www.deeptrekker.com/news/difference-between-gvi-cvi)、[Bentley APM 海生物規格](https://help-apm.bentley.com/7/en/eam/1040129341_Specifications_marin.html)、[MDPI](https://www.mdpi.com/2077-1312/6/1/2)、[AAU IEEE Oceans](https://vbn.aau.dk/ws/portalfiles/portal/770636287/IEEE_Oceans_Marine_Fouling_Thickness_and_Composition_Estimation.pdf)
- 海纜與管線：[TSS 440 手冊](https://www.manualslib.com/manual/2915525/Teledyne-440.html?page=21)、[TSS 440 規格](https://www.uniquegroup.com/wp-content/uploads/2022/10/Teledyne_TSS-440_-Pipe_Tracker.pdf)、[Acteon 追蹤](https://acteon.com/equipment-sales-rental/electronics-tooling/rov-sensors/pipe-and-cable-tracking/)、[Guide to Floating Offshore Wind](https://guidetofloatingoffshorewind.com/guide/o-operations-and-maintenance/o-2-maintenance/o-2-2-balance-of-plant-maintenance/o-2-2-3-cable-monitoring-inspection-and-minor-repair/)、[Ocean News / Rotech](https://oceannews.com/?p=69375)、[Offshore Magazine / Rotech](https://www.offshore-mag.com/subsea/article/14288662/rotech-completes-trenching-cable-cut-and-recovery-at-offshore-wind-farm)、[Bawart 故障定位](https://www.scribd.com/document/375790951/A-07528987)、[SINTEF](https://blog.sintef.com/energy/smart-fault-location-on-subsea-cables/)、[Megger Magtrack](https://www.megger.com/en/products/magtrack)、[ICPC 建議書](https://iscpc.org/publications/recommendations/)、[Gassco 交越要求](https://gassco.eu/wp-content/uploads/2023/09/Appendix-D-Gassco-Technical-Requirement-for-Offshore-Crossings-1.pdf)、[Rigzone 完整性檢查](https://www.rigzone.com/insights/operational-questions-8/how-to-perform-integrity-checks-on-subsea-pipelines-1065)、[Rigzone 機器人](https://www.rigzone.com/insights/how-it-works-3/what-is-the-role-of-robotics-in-subsea-pipeline-inspections-555)
- 搜救：[RCMP Gazette](https://rcmp-grc.gc.ca/en/gazette/deepwater-detection)、[Castanet / RCMP](https://www.castanetkamloops.net/news/Oliver-Osoyoos/378014/RCMP-dive-team-arrive-at-Osoyoos-Lake-to-find-missing-Oliver-man-who-drowned)、[Hydro International](https://www.hydro-international.com/content/news/underwater-search-by-police-and-dive-teams)、[Firehouse](https://www.firehouse.com/technology/news/55314167/nc-rescuers-use-remotely-underwater-vehicle-for-lake-recoveries)、[VideoRay 案例](https://videoray.com/may-25-2016-videoray-pro-4-rov-used-to-recover-drowning-victim/)
- 水庫：[Deep Trekker 水力](https://www.deeptrekker.com/news/hydroelectric-rov-inspections)、[Renewable Energy World / PSE](https://www.renewableenergyworld.com/?p=728924365)、[SEAMOR BC Hydro](https://seamor.com/bchydro/)、[VideoRay USBR](https://videoray.com/wp-content/uploads/2021/09/Hyd_USBR.pdf)
- 考古：[ECU 論文](https://thescholarship.ecu.edu/handle/10342/6524)、[CNR ROV 3D](https://chloe.cnr.it/s/DHeLO/item/12111)、[NOAA 文化資產工具](https://oceanexplorer.noaa.gov/fact-sheet/maritime-heritage-tools-fact-sheet)
- 科研：[NOAA 深海採樣](https://oceanexplorer.noaa.gov/edu/materials/deep-sea-sampling-fact-sheet.pdf)、[OET 採樣程序](https://nautiluslive.org/science/sampling-procedures)、[WHOI Jason](https://ndsf.whoi.edu/jason/systems-jason)
- 冰下：[NSF 計畫](https://demo.bco-dmo.org/project/743648)、[Icefin](https://www.marinetechnologynews.com/news/antarctic-researchers-prepare-space-518095)、[Whitcomb PTC 2013](https://sundowner.colorado.edu/seefeldt/ptc-2005_2016/2013_pdf/PTC_2013_Whitcomb.pdf)、[WHOI NUI](https://website.whoi.edu/gfd/wp-content/uploads/sites/14/2018/10/2014_Oceans_NUI_compressed_232664.pdf)
- 程序與角色：[VideoRay 預潛](https://download.videoray.com/documentation/pro_4/html/service_predive.html)、[VideoRay 現場作業](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)、[Deep Trekker 入門](https://www.support.deeptrekker.com/vehicles/rovs/pivot/getting-started)、[美國海軍 ROV 遺失安全通報](https://navalsafetycommand.navy.mil/Portals/100/SA%2022-12%20Loss%20of%20Remotely%20Operated%20Vehicle.pdf)
- 心流：[Chen, CACM 2007](https://cacmb4.acm.org/magazines/2007/4/5692-flow-in-games-and-everything-else/fulltext)、[Chen 論文](https://khoury.northeastern.edu/~lieber/courses/csu670/f08/materials/p31-chen-flow-in-games.pdf)、[ACM 2023 平衡研究](https://unpaywall.org/10.1145%2F3611065)
- 本專案內部：`docs/reference/real-rov-research.md`（TRANSoM、IMCA SF 02/23、VideoRay 強流定義）、`research_notes/洋流與波浪對ROV作業/real_dive_footage.md`、`simulator/qysim/scenarios.py`、`simulator/campaign/*.json`
