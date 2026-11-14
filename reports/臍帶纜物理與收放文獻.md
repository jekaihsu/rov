# 先修收放與接觸，再談纜線剛度

本專案 `simulator/qysim/tether.py` 用的方法沒有選錯。集中質量鏈、只受拉的彈簧、法向／切向 Morison 阻力、附加質量、濕重，正是文獻與 MoorDyn 主流用於 ROV 纜線的同一族模型。跟真實體驗差距最大的不是缺了高階物理，而是三處操作員每天會碰到的行為。**一是收放纜**：現在會把 40 段的靜長瞬間等比縮放，本報告重跑，在 10 m 纜上瞬收 2 m 產生約 1.4 kN 的假尖峰。**二是接觸**：只做節點接觸，長纜時段長達 8.75 m，會穿過樁柱。**三是剛度**：被軟化且隨纜長改變，短纜反而最「像橡皮筋」。文獻能提供的驗證基準相當具體，包括小型纜線的實測 EA、EI、GJ 與擬合 Cd（UVic 的 Buckham、Zand 論文）、集中質量法的穩定條件（MoorDyn）、BlueROV2 纜線基準情境（von Benzon 2022），以及工作級吊放急拉載荷約為 ROV 重量 2.4–3.1 倍（Deng 2024）。這些數字全部來自其他機型或研究纜線。依 AGENTS.md，不得寫死成 X1 事實。X1 目前公開可查的只有經銷商列的 **350 m、Ø9.5 mm、300 kgf**；空中線重、濕重、EA、阻力係數、接頭強度與線盤行為都要靠自有實測補齊。現有實測清單只有一項（第 14 項）涉及纜線，需要擴充。

**證據標記**：【核實】表示研究者讀過一手全文或原始頁面；【摘要】表示只見於搜尋摘要或論文摘要，未讀全文；【推算】表示由引用數據自行計算或推論，不是任何來源的原話。

## 小型纜線約 10 mm 粗、淡水中性，拉斷強度遠高於接頭

觀察級 ROV 纜線的構造相當一致：銅雙絞線或光纖做導體，克維拉（aramid）或 Vectran 做承力件，外層用發泡聚氨酯或聚乙烯護套，把整體密度調到接近水。Blue Robotics Fathom 標準纜 **Ø7.6 mm、空中 0.043 kg/m、拉斷 155 kgf、工作負載 35 kgf**（約為拉斷的 23%），最小工作彎曲直徑 75 mm。它標示為「淡水中性、海水略正浮」，並以阻水膠限制破口滲水【核實】([Blue Robotics](https://bluerobotics.com/store/cables-connectors/cables/fathom-rov-tether-by-the-meter/))。VideoRay 的中性纜 Ø11.18 mm、負浮纜 Ø8.51 mm，克維拉承力件額定都是 450 kg，最小彎曲半徑 82.5–114 mm，約為外徑的 10 倍。它明定工作負載不得超過拉斷的一半，但**接頭拉斷只有 80 kg、鎖環 35 kg**【核實】([VideoRay MSS](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html))。因此真實的失效點通常在接頭或格蘭頭，不在纜身中段。發泡是有代價的：同外徑下中性纜的導體較細（20 AWG 對負浮纜 16 AWG），長距離供電能力較差。業界因此常在 ROV 端接中性纜、水面端接負浮纜【核實】([VideoRay Pro4](https://download.videoray.com/documentation/pro_4/html/universal_tether.html))。

浮力的關鍵細節是「中性」幾乎都指淡水。【推算】Ø9.5 mm 纜在海水排開約 72.7 g/m，淡水約 70.9 g/m，相差約 2.5%。一條淡水恰好中性的 9.5 mm 纜，在海水約為 +1.8 g/m 正浮，350 m 合計約 0.6 kgf 向上。量級很小，但足以讓鬆弛段浮向水面與螺旋槳。本專案現在的參數在這裡自相矛盾：`mass_per_m = 0.12 kg/m`（慣性）與 `wet_weight_per_m = 0.004 kg/m`（重力）彼此獨立設定（`simulator/qysim/vehicles.py`）。以 9.5 mm 外徑計算，0.12 kg/m 的實心纜濕重應約 0.047 kg/m，而不是 0.004【推算】。合理做法是改由「空中線重＋外徑＋水密度」推導濕重，並讓水密度隨淡水／海水環境切換。

剛度方面，小型纜的直接量測非常少，而且都來自 13–19 mm 的研究用纜線。下表列出可作為數量級邊界的數據。

| 纜線 | 外徑 | EA | EI | GJ | 法向 Cd | 證據 |
|---|---|---|---|---|---|---|
| Buckham 水池纜 | 13.6 mm | 23.5 kN | 0.124 N·m² | — | 1.25（擬合，1.0–2.0 間差異小） | 【核實】([Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)) |
| Falmat TPE 纜（Buckham） | 19 mm | 217 kN | 0.25 N·m² | 0.11 N·m² | 1.649 | 【核實】同上 |
| Saab Falcon 纜（Zand） | 14 mm | 43 kN（由 EI 反推，作者警告可能不準） | 0.54 N·m²（0.40–0.67，遲滯大） | 約 0.5 N·m² | 1.65（海上拖曳傾角反推） | 【核實】([Zand](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf)) |
| ROPOS 鎧裝臍帶纜（重型，僅作對照） | 30 mm | 45.5 MN | — | — | 1.0；切向 0.02 | 【核實】([Driscoll 1999](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)) |

【推算】若承力件主導軸向載荷，且克維拉約在 2.4% 應變斷裂，則 EA ≈ 拉斷力／0.024。這樣 X1 的 300 kgf 對應約 1.2×10⁵ N，Fathom 約 6×10⁴ N。實際纜線還有結構伸長，真值應較低，與上表 2–20×10⁴ N 同一量級。專案現值 EA = 20 kN 落在偏軟的一端。Buckham 有一個重要觀察：Falmat 纜的 EI 與 GJ 只能用護套計算，因為內部導線會在護套內滑動。實機的 ROV 端接頭在扭轉上很軟，使行為更接近 GJ = 0【核實】。這直接影響扭轉要不要用連續體模型。

流體力方面，法向阻力係數的合理範圍是 **1.2（光滑圓柱理論）到 1.65–2.0（真實 ROV 纜線擬合或現場量測）**。Kojima 等人 1986 年在海上量測 MARCAS 纜，得到的值「遠大於 1.2」，約 2.0【摘要】([Springer](https://link.springer.com/chapter/10.1007/978-94-009-4207-3_5))。纜線發生渦激振動（strumming）時，有效 Cd 可達 1.5–3.5（[Wikipedia: Cable fairing](https://en.wikipedia.org/wiki/Cable_fairing)）。切向係數小兩個數量級，文獻常見 0.002–0.02，隨表面粗糙度而變【摘要】([ASCE](https://ascelibrary.com/doi/10.1061/JYCEAJ.0000873))，ROPOS 校正值為 0.02【核實】。法向附加質量係數取 1、切向取 0【核實】([Palm & Eskilsson 2020](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf))。要注意定義慣例：von Benzon 的切向阻力用「直徑×長度」，部分文獻用濕周 πd。混用時會差 π 倍【核實】([von Benzon 2022](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf))。

阻力的實際意義是纜線常常比載具本身更吃力。Zand 模擬 350 m 中性纜的 Falcon：流速 0.67 m/s 時，纜對 ROV 的縱向力達 255 N，已逼近該機 401 N 的推力上限；1.0 m/s 時為 568 N，是載具本體阻力 273 N 的兩倍【核實】([Zand](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf))。【推算】X1 纜 100 m 全段橫向迎流時，0.5 m/s 下約受 146 N，0.7 m/s 時就會吃掉 X1 前進推力 30 kgf（約 294 N）。這遠低於經銷商宣稱的「抗流 2.0 m/s」，後者想必假設纜線幾乎不在流中。這正是訓練應該讓學員體會的事。

急拉（snap load）在真實作業中有清楚的特徵：鬆弛段被突然拉緊時，張力以波的形式沿纜傳遞，波速 c = √(EA/m)，並在兩端反射。ROPOS 實測籠子被拉出 **0.5 g** 的垂直加速度，而且纜在籠端被彎到小於最小彎曲半徑【核實】([Driscoll 1999](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download))。

## 集中質量法仍是主流，即時模擬的關鍵是時間步長與阻尼

文獻中幾種數值方法的取捨相當明確。**有限差分法**（Ablow & Schechter 1983）把張力當未知數，纜線一進入鬆弛、張力歸零，代數方程就變成奇異。**集中質量法**的張力是節點位置的顯函數，鬆弛時張力就是零，數值上穩定，所以成為 ROV 纜線的主流方法。Kamman & Huston 等人發現，因為水下流體力遠大於慣性項，集中質量法的精度與有限段法相當，計算卻省得多【核實】([Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download))。高階方法也各有所長。Buckham 的三次樣條單元可把元素加大 35–50%，執行時間最多省 70%。Palm & Eskilsson 用不連續 Galerkin 法加入彎曲項，並指出低張力纜「普遍需要彎曲剛度」才能得到準確且穩定的形狀【核實】([Palm & Eskilsson 2020](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf))。他們重現 Koh 擺動纜實驗：EI = 0 時自由端會「甩鞭」，張力明顯高估；加入 EI 與彎曲阻尼後與實驗吻合。至於 ANCF，Chrono 的 `ChElementCableANCF` 是現成的快速纜線元素，但不含扭轉【核實】([Chrono](https://api.projectchrono.org/manual_fea_elements.html))。本研究沒有找到 ANCF 用在 ROV 纜線並經過驗證的案例。

即時模擬的穩定條件寫得很清楚。MoorDyn 指出，集中質量鏈最高的軸向模態為 ω_n = 2(N/L)√(EA/w)，顯式積分需要 Δt < 2π/ω_n。它建議每段的阻尼比接近臨界（ζ ≈ 1），並給出 BA = ζ(L/N)√(EA·w)【核實】([MoorDyn troubleshooting](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/troubleshooting.rst))。實際計算成本可參考 Buckham 的數據。6.55 m 纜用 RK4 時，5 段需 1.0 ms、30 段需 0.1 ms；Generalized-α 隱式法在同精度下可用 22.5 ms 到 5 ms 的步長。但到 30 段時，Jacobian 的成本就抵銷了這個優勢；在當年的 1 GHz CPU 上，只有約 10 段以內能即時【核實】。von Benzon 的 BlueROV2 Simulink 模型也因為方程剛性而建議用隱式解算器（ode15s）【核實】。遊戲引擎走另一條路。PBD/XPBD 繩子要靠 long-range attachment 約束，或三對角直接解，才能在長鏈上保持不可伸長（[Kim et al. 2012](https://matthias-research.github.io/pages/publications/sca2012cloth.pdf)、[Liu et al. 2022](https://arxiv.org/pdf/2202.09714)）。Stonefish 的 `stretch_factor` 則明說不是物理量，要依更新率調整【核實】([Stonefish](https://stonefish.readthedocs.io/en/latest/cables.html))。

驗證結果大致落在 10–20% 的誤差。ROPOS 1730 m 海上實測中，模型準確預測了籠子運動、船端張力與固有頻率，籠子運動只有約 11% 的落差；加入尾流記憶模型後，波浪頻帶內的轉移函數「幾乎一致」【核實】([Driscoll 1999](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download))。但急拉事件只占不到 1% 的運動週期，而且對激振幅度極度敏感：Driscoll 要把船舶運動放大 10%、Palm & Eskilsson 要放大 20%，才能重現急拉【核實】。Buckham 的小型纜水池試驗中，尾端軌跡與模擬「非常吻合」【核實】。相對地，von Benzon 只驗證了 BlueROV2 本體的流體動力（俯仰與偏航誤差 10%／12%），纜線模型本身**沒有實驗驗證**【核實】。商用訓練模擬器（GRi VROV、Forum VMAX、Fugro DeepWorks）都宣稱有動態纜線、碰撞與 TMS 耦合，但沒有公開任何方程、段數或驗證數據【摘要】。開源的 UUV Simulator「臍帶」只是一個施加在載具上的水平阻力，完全沒有纜線幾何【核實】([UUV Simulator 原始碼](https://raw.githubusercontent.com/uuvsimulator/uuv_simulator/master/uuv_gazebo_plugins/uuv_gazebo_plugins/src/UmbilicalModel.cc))。換句話說，本專案的模型已經比多數開源機器人模擬器完整。**小於 10 mm、100–300 m 長的觀察級纜線，目前沒有任何公開的實驗驗證**，X1 實測會是獨有資產。

## 小船靠人手收放，工作級靠絞車與 TMS，事故集中在端接與鬆緊轉換

小型 ROV 的水面設備多半是**帶 8 路滑環的手搖線盤**。Fathom 標準線盤可收 150 m（[RobotShop](https://www.robotshop.com/products/bluerobotics-fathom-spool-150m)【摘要】）。VideoRay Pro 4 的 TDS 可收 76 m 負浮纜、76 m 中性纜加 40 m PPT，擴充版可達 300 m【核實】([VideoRay TDS](https://download.videoray.com/documentation/pro_4/html/equip_tether_tds.html))。電動線盤的速度偏慢。QYSEA 的電動線盤標示 300 m 收纜「快檔 8 分鐘、慢檔 12 分鐘」【摘要】([Scuba.com](https://www.scuba.com/p-qyelecspool/qysea-electric-powered-spool-for-fifish-w6-version-drone))；【推算】約 0.63 與 0.42 m/s，比專案現在的自動放纜 1.0 m/s 慢。VideoRay Expeditionary Reel 有排纜器與放纜編碼器，可收 500 m，但沒有公布速度、拉力或剎車數據【核實】([VideoRay](https://videoray.com/wp-content/uploads/2025_SpecSheet_72743_Exp-Reel_2.0.0.pdf))。Deep Trekker 的 API 透露了小型電動線盤的放纜邏輯：放纜時線盤「脫離、不強制送出」，靠單向離合器（sprag bearing）讓載具把纜拉出，另有失速旗標、急停與長度編碼器【核實】([Deep Trekker API](https://docs.api.deeptrekker.com/types/PoweredReel.html))。也就是說，小型系統的「自動放纜」本質上是被動的，並不是恆張力伺服。

工作級系統把鎧裝吊放臍帶纜與軟性遊纜（excursion tether）分開。吊放臍帶纜走 LARS 絞車、A 字架或吊臂，過飛濺區常用遊標（cursor）；遊纜則收在水下的 TMS 滾筒。TMS 滾筒速度約 30–40 m/min，拉力上限 150–450 kgf 且可調，Imenco 還設有「防過拉的滾筒脫開離合器」【摘要】([FET Type 6](https://f-e-t.com/wp-content/uploads/2019/10/tms-type-6.pdf)、[Imenco](https://imenco.no/?p=9068))。主絞車約 30–60 m/min，拉力與速度依纜層而變【摘要】([MacArtney](https://www.macartney.com/media/5275/mermac-r.pdf))。主動升沉補償需要約 50–80 m/min 的纜速，才能抵銷 3–4 m 的船體運動；Scantrol 的控制模式包括防急拉（Anti-Snatch）與臍帶應變限制（Umbilical Manager）【核實】([Scantrol](https://www.scantrol.com/ahc-rov-operations))。被動補償在 ROPOS 的模擬中把籠子運動與張力的均方根降約一半，籠端補償器更消除了所有急拉【核實】([Driscoll 1999](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download))。

飛濺區與母船耦合的定量數據，最完整的是 Deng 等人 2024 年的研究。該研究以 38.9 m 的 OSV 用吊臂吊放工作級 ROV＋TMS，並用 1:10 水槽試驗驗證。結果顯示，峰值張力出現在**回收途中絞車或吊臂停止的瞬間**，回收峰值約為下放的 2.4 倍。在 Hs 0.6 m、絞車 0.5 m/s 的條件下，峰值約為 ROV 重量的 2.4 倍（船尾）到 3.1 倍（舷側），而鋼纜 MBL 只有 1.81 倍。改用船尾、外伸 1.0 m、上升 0.3 m/s 的新程序後，Hs 1.0 m 下的回收峰值減半，作業上限從 Hs 1.0 m 提高到 1.25 m【核實】([Deng et al. 2024](https://strathprints.strath.ac.uk/89731/1/Deng-etal-OE-2024-Launch-and-recovery-of-a-work-class-ROV-through-wave-zone.pdf))。小船手放觀察級 ROV 的海況上限，本研究找不到可引用的來源；業界口耳相傳的「三級海況」不能當成事實。

纜線手（tender）的作業規範主要來自廠商手冊。VideoRay 要求纜線手收放時「通常每 5 m」向駕駛報長度。放纜只放必要的長度，「太少影響操控，太多會勾掛、纏繞或被螺旋槳切斷」。多餘的纜「像帆一樣」。作業點要選在工作區上游且視線可及，纜線要遠離母船的螺旋槳與舵。纜線要以 over/under 或 8 字盤繞，因為單向盤繞會留下難以消除的扭轉。駕駛也要記錄載具繞了幾圈，因為每一圈都會增加作用在載具上的扭矩【核實】([VideoRay 強流 13 招](https://videoray.com/13-tips-for-operating-an-underwater-rov-in-strong-currents/)、[VideoRay 纜線管理](https://download.videoray.com/documentation/pro_4/html/oper_tether.html))。纜線勾掛時的第一條規則是「不要慌、不要拉纜」：先轉動相機找到纜，再沿纜飛回勾掛點【核實】([VideoRay 勾掛程序](https://download.videoray.com/documentation/mss/html/emergency_snag.html))。回收上船時要抓機架，不要拉纜【摘要】。滑環只能讓線盤轉動時不扭到水面引線，並不能消除載具旋轉造成的扭轉【核實】。

IMCA 的事故通報顯示，事故一再集中在幾個環節。第一類是端接、子彈頭與插座在閂鎖時斷裂，原因包括絞車拉力不受限（SF 13/14）。第二類是 TMS 閂鎖失敗，纜被剪斷、ROV 墜落（SF 13/24）。第三類是切換低張力模式、經過遊標軌道轉換段時斷纜（SF 11/25）。另有剎車失效，約 800 m 臍帶纜在 90 秒內放光；以及停電導致絞車失控收纜，造成死亡事故（SF 07/08）【均為摘要】([IMCA SF 13/14](https://imca-int.com/resources/safety/safety-flashes/1314-main-rov-lift-umbilical-parted)、[SF 07/08](https://www.imca-int.com/resources/safety/safety-flashes/0708-fatal-accident-in-connection-with-the-operation-of-an-a-frame-based-launch-and-recovery-system-lars-used-for-rov-operations/))。觀察級最相關的一案是 SF 02/23：纜線在導管架上磨損，先失去動力，隔天斷裂，ROV 遺失【摘要】([IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/))。

## tether.py 的八項差距與改進順序

現行模型固定 40 段。0 號節點釘在固定的線盤點，40 號節點運動學地跟隨 ROV 格蘭頭。每 10 ms 分成 10 個 1 ms 子步，用半隱式 Euler 積分。軸向勁度取 `min(EA/l0, 9000 N/m)`，阻尼比 0.6。超過 2943 N 斷纜，超過 250 N 警告。自動放纜在線盤端張力超過 45 N 時以 1 m/s 放出。沒有彎曲、扭轉、線段邊接觸、線盤動力學或母船運動（`simulator/qysim/tether.py`、`simulator/qysim/vehicles.py`）。以下排序以「學員實際會操作與感受到的行為」優先，其次才是力學精度。

**第一優先：收放語意。** `payout()` 直接改總長，所有段的靜長同時等比縮放（`tether.py` 第 82–83 行），手動按鈕一次 ±1 或 ±5 m。本報告在版本庫上重跑：懸掛纜在 ROV 固定下瞬收 2 m，10 m 纜張力峰值 **1443 N**（研究筆記另一組幾何為 1631 N），40 m 為 450 N，200 m 為 207 N【推算，本機重現】。真實世界沒有這種瞬間縮短。自動放纜也只是門檻加定速，沒有慣性、剎車或人的延遲，速率還寫死成 `0.01` 而不是 `dt`。改進方向【推算】：長度只在線盤端增減（線盤端那一段可變長，需要時插入或移除節點）。收放改為速率指令，加上一階延遲與加速度上限：手搖模式約 0.3–0.5 m/s，電動線盤快／慢檔參照 QYSEA 的 0.63／0.42 m/s【摘要】。被動放纜改成「線盤摩擦／剎車力矩」模型，取代 45 N 門檻。收纜拉力上限必須低於纜線與接頭強度，這條規則可直接對應 IMCA SF 13/14。依 AGENTS.md，±5 m 瞬放屬於可關閉的輔助層，真實模式預設應是有速率限制的纜線手模型。驗證方式：以固定速率收纜時，張力上升必須平滑且有界；長度讀數依 5 m 的報長粒度輸出。

**第二優先：接觸與勾掛。** 只做節點接觸，段數固定為 40，放到 350 m 時每段 8.75 m，可以整段穿過 1.6 m 直徑的樁柱。摩擦是速度折減規則，跟法向力與包角無關。纏繞偵測只看近乎垂直的圓柱。改進方向【推算】：改做線段對膠囊體的最近點接觸；在障礙物附近加密節點，或做適應性分段；摩擦改成正比於法向力的正則化庫侖摩擦。可參考 Palm & Eskilsson 用 tanh 正則化的海床摩擦式【核實】，以及 MoorDyn 的靜／動摩擦比參數【核實】([MoorDyn inputs](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst))。驗證方式：纜繞圓柱時，兩端張力比應趨近絞盤公式 e^{μθ}（一般力學，非 ROV 文獻數據）；在 350 m 長纜情境下，纜不得穿過樁柱。

**第三優先：軸向剛度。** 【推算】勁度上限 9000 N/m 在 L < 88.9 m 時生效，整條纜的串聯勁度固定為 225 N/m，等效 EA 只有 225·L，10 m 時僅 2.25 kN。這比文獻中的小型纜（23.5–217 kN）軟一到兩個數量級，結果是短纜最軟，與直覺正好相反。原因是顯式穩定條件。【推算】半隱式 Euler 在無阻尼時需要 h < l0/c，其中 c = √(EA/m')。以 m' ≈ 0.19 kg/m（含附加質量）計算，EA = 1.2×10⁵ N 時 c ≈ 790 m/s。在 h = 1 ms 下，段長必須大於約 0.8 m；10 m 纜分 40 段的 0.25 m 段長遠遠不夠。可行路線有兩條。一是軸向部分改用三對角隱式解（每個子步一次 Thomas 解；von Benzon 建議用隱式解算器【核實】，Liu 等人以三對角直接解保持繩長【核實】）。二是依 MoorDyn 規則把阻尼比提高到接近 1，並依 CFL 自動決定子步數【核實】。這兩條路都能讓 k_max 退場。驗證方式：用 c = √(EA/m) 檢查張力波從線盤傳到 ROV 的時間；用 MoorDyn 公式寫成單元測試，在不同纜長下確認穩定。軟化剛度會使急拉峰值偏低，這也是「斷纜」計分不準的根源。

**第四優先：參數一致性。** 空中線重與濕重互相矛盾。附加質量現在等向施加，包含軸向，但文獻一致取切向 Cm = 0【核實】。端點節點用了完整的阻力面積。阻尼比 0.6 低於 MoorDyn 建議。法向 Cd 1.2 與切向 0.02 落在文獻範圍內，不是主要問題，但「真實模式」可考慮把法向 Cd 提高到 1.5–1.65，以反映真實纜線的擬合值與輕度渦振（Zand、Buckham【核實】）。這一項成本最低，可以跟第三項一起做。

**第五優先：扭轉。** 目前沒有扭轉狀態。【推算】不需要 Cosserat 桿模型：積分 ROV 相對纜線的淨偏航圈數，施加一個小的回正偏航力矩，並在 HUD 顯示圈數即可。這樣就能重現 VideoRay「每一圈都增加扭矩」與「記錄圈數」的實務【核實】。Buckham 觀察到實機接頭在扭轉上很軟、行為近似 GJ = 0【核實】，支持只做輕量模型。

**第六優先：失效模式與門檻。** 現在只有單一的纜身斷裂值 2943 N。警告值 250 N 只有拉斷的 8.5%，同時遠低於 VideoRay「工作負載不超過拉斷一半」與 Fathom 23% 的作法【核實】。應補上：比纜身弱得多的接頭／格蘭頭強度（VideoRay 比例為 80 kg 對 450 kg）、接觸點按張力乘滑移量累積的磨損（對應 IMCA SF 02/23 的磨斷案例），以及彎曲半徑小於最小彎曲半徑時的事件。

**第七優先：母船、碼頭與水面。** 線盤點固定不動，水面以上的節點也照樣受浮力與阻力。von Benzon 的模型允許基點隨時間移動【核實】。加入母船升沉與漂移（小船），以及工作級模式的絞車停止急拉（Deng【核實】），可以產生真實的訓練情境。不過對碼頭放下的觀察級 ROV，價值低於前幾項。

**第八優先：彎曲。** 對約 10 mm 的軟纜，EI ≈ 0.1–0.5 N·m²，【推算】在張力 1 N 時，彎曲長度 √(EI/T) 約 0.3–0.7 m，只在格蘭頭附近與鬆弛線圈處有感。主要價值是外觀：鬆弛段不再在節點處折成多邊形。另外也能用來偵測彎曲半徑過小。

另有一項流程差距，應該與第一優先同時開工：現有測試沒有一項把張力或形狀跟解析解或文獻基準比對。

## 可用的驗證基準與必須由 X1 實測補齊的參數

下表把每項改進對應到可直接寫成自動化測試或驗收比對的文獻數據。凡是來自其他纜線的數值，只能作為「量級與趨勢」的邊界，不可當成 X1 的期望值。

| 改進項 | 驗證基準 | 數據 | 證據 |
|---|---|---|---|
| 整體模型健全性 | 靜水懸掛纜與懸鏈線解析解比對 | 懸鏈線方程（arXiv 2508.02264 式） | 【核實】([arXiv](https://arxiv.org/html/2508.02264v1)) |
| 阻力 | 均勻流中直纜的總橫向力等於 ½ρCd·d·L·v² | 解析 | 【推算】 |
| 整體耦合 | von Benzon 被動測試：15 m 纜、合成流速 0.5 m/s，約 30 s 拉直、約 100 s ROV 到水面、穩態約 30 N | 模擬對模擬 | 【核實】([von Benzon](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)) |
| 小纜動力 | Buckham 3.70 m／6.55 m 水池軌跡與參數表 | EA、EI、GJ、Cd 與時間步長 | 【核實】([Buckham](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)) |
| 長纜阻力量級 | Zand Falcon 350 m：0.2／0.67／1.0 m/s 時縱向力 23／255／568 N | 模擬，海上 Cd | 【核實】([Zand](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf)) |
| 彎曲 | Koh 擺動纜（EA 1541 N、EI 0.060 N·m²、2.022 m） | 實驗 | 【核實】([Palm & Eskilsson](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)) |
| 穩定性 | MoorDyn ω_n = 2(N/L)√(EA/w)、ζ ≈ 1 | 公式 | 【核實】([MoorDyn](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/troubleshooting.rst)) |
| 急拉 | 波速 √(EA/m) 與兩端反射；ROPOS 0.5 g；Deng 2.4–3.1× ROV 重 | 實測／水槽 | 【核實】 |
| 收放速率 | 電動線盤 0.42–0.63 m/s；TMS 30–40 m/min | 廠商 | 【摘要】 |
| 整體誤差目標 | 形狀與張力趨勢誤差在 10–20% 內 | ROPOS 約 11% | 【核實】／【推算】 |

必須由 X1 實測補齊的參數，依影響大小排列。第一組決定浮力與阻力：每公尺空中重量，用秤量一段已知長度即可；淡水與海水中的濕重或浮沉，可用一段纜掛小砝碼找中性點；實際外徑與公差。【推算】經銷商列的線盤連纜重 53 kg，與 350 m × 約 0.07 kg/m ≈ 25 kg 的纜重相容，但這只是相容，不是量測。第二組是軸向 EA：吊掛階梯載重量伸長，量到工作負載為止，不要拉到斷。另外要向原廠取得接頭與格蘭頭的強度，以及建議的工作負載。第三組是法向 Cd：仿照 Zand 用已知船速拖曳纜線、量傾角反推，或在現有實測清單第 14 項（放纜 20／50／100 m 時能否維持航向與前進）同步記錄流速與纜形。第四組是 EI 與最小彎曲半徑：三點彎曲或懸臂量測。第五組是線盤本身：手搖可持續的收纜速率與手感阻力、是否有剎車或離合、電動版的速度檔位、滑環與長度讀數方式。第六組是扭轉：原地偏航 N 圈後，量測載具在零指令下的回轉趨勢。現有 `docs/reference/x1-measurement-checklist.md` 只有第 14 項涉及纜線，以上項目應補進清單。補齊之前，`vehicles.py` 中這些值都應維持 `estimated` 標記。

## 結論

這次文獻整理改變了問題的重心。真實 ROV 纜線最有特色的物理，在模擬器裡通常不是主角：纜線在流中的阻力主導了載具的負擔，而失效點是接頭而不是纜身。操作員真正每天面對的是「誰在收放、多快、纜卡在哪裡」。本專案的力學核心已在正確的方法族；最值得投入的是讓收放與接觸變得可信，並把剛度從「為了穩定而軟化」改成「靠解算方式保持穩定」。後者同時解決短纜偏軟與急拉失真兩個問題。

更深一層的含意是：觀察級細纜在 100–300 m 尺度上沒有任何公開驗證。不論是學術模型還是商用模擬器，都拿不出能直接套用到 X1 的數字。因此最有價值的下一步，是一組成本很低的 X1 纜線實測：秤重、浮沉、吊掛伸長、拖曳傾角與線盤速率。有了它，模擬器的「真實模式」就能從「量級合理」提升到「可對照驗收」。這也是任何競品模擬器都還沒有公開做到的事。
