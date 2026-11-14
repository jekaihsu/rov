# 臍帶纜與受限視野決定真實 ROV 手感

真實觀測級 ROV 的操作體驗，核心不是「水下無人機」，而是「透過一支延遲 0.15–0.2 秒、視角狹窄、被懸浮物與色偏劣化的鏡頭，駕駛一台推桿等於推力、鬆桿後靠阻力在約 0.3 m 內停住然後隨流漂走、並且一路被臍帶纜拖著的載具」。公開資料足以把這個體驗的**通用骨架**做對：BlueROV2 Heavy 有一套經水池實測驗證的完整水動力係數，ArduSub 的模式語意、VideoRay 的纜線與強流操作準則、Blue Robotics 的 22 步下水檢查、IMCA 的事故通報與 TRANSoM 的評分矩陣都是可直接引用的一手資料。但 **FIFISH X1 本身幾乎沒有可用的公開操作資料**：官方規格書 PDF 被 403 擋下、使用手冊僅能申請索取、Q-iRC 的預設鍵位未公開、X1 版 App 的畫面配置沒有任何帶標註的截圖、也找不到任何獨立的 X1 操作員評測或實測數據。X1 是 ≤30 kg、350 m、纜線供電、標配前向與下向 Q-DVL 的機型，質量約為 V6 Expert 的 6–7 倍，拿 V6 等級（3 節、4–5 kg）的數字調出來的手感對 X1 是錯的。因此「體驗與真實 ROV 一致」要分兩層達成：通用層（光學、延遲、力控制語意、纜線力、聲納、流程、事故情境、評分）用公開數據即可對齊；X1 專屬層（各軸速度與加減速、鬆桿與定點行為、鍵位、HUD 截圖、影像延遲、上電與下水程序）**只能靠自有 X1 實機量測與截圖補齊**。唯一一項有對照實驗支持的模擬器研究也指出，轉移到真機的關鍵是穩態動力學、軸間耦合、相同的實體控制器與畫面更新率，而不是照片級畫質。

> **證據標記**：未加標記的敘述，表示研究者實際開啟並讀過該頁面或文件（注意「讀過」不等於獨立驗證，廠商宣稱仍是廠商宣稱，文中以〔廠商〕提示）。〔摘要〕表示僅來自搜尋結果摘要、原頁面未開啟或無法開啟，可信度較低。〔推算〕表示由已引用數字做的計算或推論，原始來源並未如此陳述。研究筆記中沒有來源連結的「領域常識」一律未納入正文，只在缺口處點名為待查項目。

## X1 的公開資料只夠畫出輪廓：30 kg、纜線供電、標配 DVL，其餘靠 V6 文件類推

### 已知規格顯示 X1 與 V6 家族是不同級距的載具

QYSEA 官方頁面確認的 X1 數字有限：六推進器向量佈局（Q-Motor Pro，可快拆）、**最高 4.5 節、抗流懸停 4.0 節**、姿態控制 ±0.1°、作業深度 350 m、重量 ≤30 kg、1–2 人可部署、纜線直接供電（標榜 24h×7）、雙 4K 相機（1/1.8" CMOS，「超廣角」但未給角度）、2 × 6,000 lm 燈（120°）、前向加下向 Q-DVL、三向避障聲納（避障距離可調）、最大酬載 15 kg 與四個 Q-interface 供電埠〔廠商〕（[QYSEA X1 頁面](https://www.qysea.com/fifish-x1/)）。更細的數字只出現在一家經銷商頁面：**前進 4.5 節、後退 3.5 節、側移 2.5 節、垂直 1.5 節**，「前進推力最高 30 kg」，外形 770 × 560 × 400 mm，纜線 350 m、直徑 9.5 mm、抗拉 300 kgf、手動線盤，1080p 最高 120 fps、EIS、每台相機 128 GB，套件內含 Q-iRC 遙控器且不含電池（[Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)）。這些分軸速度沒有在任何 QYSEA 官方頁面得到確認，官方型錄的用語是「4.0 knots Max. Forward Current Holding」〔摘要，PDF 回傳 403〕（[NauticExpo X1 規格書](https://pdf.nauticexpo.com/pdf/shenzhen-qi-yuan-science/fifish-x1-technical-specifications/70155-137888.html)）。FIFISH App 在 4.9.7 版（2025-09-20）才加入 X1 支援（[App Store FIFISH](https://apps.apple.com/ly/app/fifish/id1364364991)），這也解釋了為何找不到獨立評測。

對照之下，V6 / V6s 的一手文件完整得多：383 × 331 × 143 mm、3.9 kg、4 向量加 2 水平共六推進器、靜水最高 3 節（1.5 m/s）、深度 100 m、定深 ±1 cm、姿態鎖定 ±0.1°、相機 166° FOV、燈 2 × 2,000 lm / 5500 K（[FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)）；V6 Expert 為 4.6 kg、鏡頭水中 FOV 96°、纜線 100/200 m × 4.6 mm × 100 kgf（[QYSEA 商店 V6 Expert](https://store.qysea.com/products/fifish-v6-expert)）。由此可得三個對模擬器有直接後果的判斷〔推算〕：X1 質量約為 V6 Expert 的 6.5 倍；X1 各軸速度高度不對稱（前進約 2.3 m/s、側移約 1.3 m/s、垂直約 0.77 m/s）；X1 標準配置下操作員的限制資源不是電量而是 350 m × 9.5 mm 纜線的長度與阻力。

### Q-iRC 的硬體清單公開，但預設鍵位沒有任何來源

Q-iRC 是一體式遙控器：**2 支搖桿、2 個旋鈕、2 個三段開關、1 個五向鍵、12 個按鍵**，其中 L1/L2/R1/R2/K1/K2 為單一功能自訂鍵，K3/K4 為切換操作視窗的組合鍵；內建 7 吋 1920 × 1200、峰值 1500 nits 螢幕直接執行 FIFISH App，10,400 mAh 電池續航 8 小時，具 HDMI、乙太網、USB、TF 卡與 ROV 埠，IP54（[QYSEA 商店 Q-iRC](https://store.qysea.com/products/q-irc-remote-controller)）。HDMI 可把即時 FPV 輸出到外接螢幕，不需手機或平板（[Q-iRC 使用指引](https://store.qysea.com/pages/user-guide-q-irc)）。其軟體提供多視窗任務介面（影像、航向、感測器資料、系統狀態）、相機／聲納／地圖一鍵切換，以及定點、潛水員追蹤、避障的一鍵捷徑〔廠商〕。經銷商稱 Q-iRC 上可做搖桿與滾輪校正，並有 Attitude / Sport / Combination 模式選項〔摘要〕（[Blue Skies Q-iRC](https://www.blueskiesdroneshop.com/products/qysea-industrial-remote-control)）。

**每支搖桿軸、旋鈕、三段開關、五向鍵與各自訂鍵的預設功能，在任何能開啟的頁面上都沒有公布。** 最佳替代參考是 V6 標準遙控器，它的編號佈局有完整文件：電源、定深開關、鎖定／解鎖、左右搖桿、左右滾輪、錄影、控制模式開關（Attitude / Sport / Combine）、燈光亮度（OFF/1/2）、拍照。搖桿模式在 App 內選擇「ROV Modes (USA/JPN/CHN)」或「UAV Modes (USA/JPN/CHN)」；手冊對照表中同一組搖桿軸在 ROV 模式是上浮／下潛／左／右，在 UAV 模式是俯仰上／下與左右橫滾，但完整對照表是圖片，文字抽取只保住這一組（[FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)）。搖桿響應可在 App 內調整：「curvature」（0 為線性，越大則大桿量處斜率越陡）與「attenuation」（推進器最大輸出，50 即滿桿 50%），且「移動」與「旋轉」分開設定（[FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)）。把 Q-iRC 的兩個三段開關對應到模式與燈光、兩個旋鈕對應到左右滾輪，是合理猜測但沒有來源支持〔推算〕。

### 模式語意：無 DVL 只定深定姿，X1 靠 Q-DVL 才能定點

文件化的 FIFISH 飛行模式是 A（Attitude，初學者用，不橫滾；定深開啟時即使帶俯仰角移動也維持同一深度）、S（Sport，開放橫滾成為完整六自由度；定深只在沒有指令輸入時才保持深度）、C（Combination，啟用 VR 眼鏡頭部追蹤），另有獨立的定深按鍵與姿態鎖定（[FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)）。這個差異很實質〔推算〕：A 模式下帶俯仰角推前桿仍是世界座標的等深平移，S 模式則是機體座標平移。文件只描述深度與姿態的保持，定點功能都綁在 Q-DVL 或視覺鎖定上：Q-DVL 提供 0.1–100 m 高度範圍內的定點懸停、距離鎖定與高度鎖定，精度只寫「公分級」而無數字〔廠商〕（[QYSEA Q-DVL](https://www.qysea.com/products/q-dvl-sensor/)）；AI Vision Lock 則有 Focus Lock、One-touch Lock、Slide Lock 等以畫面目標為基準的鎖定〔廠商〕（[QYSEA AI Vision Lock](https://www.qysea.com/technology/underwater-ai-vision-lock/)）。所以沒有 DVL 的 FIFISH 鬆桿後會保持深度與姿態，但水平位置不保持、會滑行並隨流漂移〔推算〕，沒有任何來源給出滑行距離或時間。對 X1 而言，定點懸停是文件化的放手行為，但**鬆桿時是自動進入還是需要按鍵、定點精度數字、DVL 失去底鎖時的行為、A/S/C 模式名稱是否適用於 X1，全部查不到**。

### App 畫面：V6 世代有標註圖，X1 世代沒有

V6 世代 HUD 由手冊的標註圖確定：上排為狀態、燈光亮度、定深開關、遙控器設定、電池、一般設定；上方中間為控制模式與訊號強度；左緣由上而下為主選單、深度指示條、FPV 翻轉、姿態指示；右緣為 VR 開關、拍照／錄影切換、拍照、錄影、錄影模式、ROV 航向；下排為 ISO、白平衡、快門、EV、解析度與幀率、剩餘時間／張數、相機設定、羅盤（[FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)）。深度條會在 0–5 m、5–30 m、30–100 m 三段量程間自動切換；右下角羅盤指示的是操作員方向，ROV 航向以度數顯示；姿態以 3D 機體模型呈現；即時畫面設定有 480P/720P 與碼率選項（[FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)）。App 更新紀錄顯示 X1 世代新增了 Q-DVL 測距模式、AR 尺、自訂 ToolBox、馬達狀態紀錄、使用前自檢、濕度提醒與自訂浮水印（[App Store FIFISH](https://apps.apple.com/ly/app/fifish/id1364364991)），但**沒有任何 2025–2026 年帶標註的 Q-iRC + X1 畫面截圖**：聲納視窗外觀、DVL 速度與高度讀數位置、避障警告樣式、是否有溫度或放纜長度讀數，全部未知；現有證據顯示線盤是手動的，App 內沒有放纜計數器的跡象〔推算〕。

### 操作程序與廠商承認的怪癖

V6 家族的文件化流程是：長按電源至七聲上升音，三顆按鍵燈順時針輪轉表示待連線；纜線接遙控器、把纜線環綁在尾翼上、接上 ROV 後 ROV 自動上電並發出五聲提示音；燈號恆亮且 App 顯示「Connected」後，**只用纜線把 ROV 放入水中、不可拋擲、入水後才解鎖推進器**，深度超過 1 m 表現最佳；回收時先鎖定並停止錄影，只拉纜線收回；潛後清水浸泡至少 1 小時並執行約 10 分鐘的馬達清潔程式（[FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)）。新版 FAQ 把浸泡時間寫成至少 30 分鐘，兩份來源不一致（[QYSEA 商店 FAQ](https://store.qysea.com/pages/faq)）。禁止在空氣中解鎖，推進器空轉不得超過 30 秒（[FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)）。

廠商自己承認的行為是寶貴的「真實感細節」：即時影像延遲 **150–200 ms**，手機離遙控器超過 5 m、用 720P、舊手機或室內 Wi-Fi 干擾時更糟；在水面解鎖後不動或原地打轉是因為兩顆水平推進器露出水面；推進器纏異物或感測器未校正時會斜向爬升；下水前深度可能讀到 1 m 以上的零點偏移；3D 姿態模型在校正前與實際不符；中途拔纜後失去控制與影像，約 30 秒重連（[FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)）。「Disconnected」常見到廠商寫了專文，原因包括纜線接頭鬆脫或髒污，以及大型金屬結構附近的磁性或射頻干擾（[QYSEA 斷線排查指南](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)）。X1 的上電順序（多了岸上供電單元）、下水前檢查表、30 kg 載具的吊放方式與環境限值，沒有任何公開文件。

## 鏡頭裡的水比 HUD 更決定真實感

### 色彩沿整條光路流失，背向散射在濁水中 4–5 m 就吞掉場景

水依光譜順序吃掉顏色，長波長先消失；一份海洋學教材給的數字是紅光在上層 10 m 內被吸收、橙光約 40 m、黃光在 100 m 前消失（[Introduction to Oceanography 6.5](https://pressbooks.ccconline.org/introduction-to-oceanography/chapter/6-5-light/)），潛水參考資料則說紅色只到約 5 m（[Taucherpedia](https://en.taucherpedia.info/wiki/Light)）。來源之間的落差（紅 5 m 對 10 m、橙 8–10 m 對 40 m）對應的是不同水質假設與「明顯褪色」對「完全吸收」的差別，不是誰對誰錯。關鍵在於吸收取決於光在水中走過的**總距離**而不只是深度（[Divevolk](https://www.divevolkdiving.com/blogs/product-tips/why-colors-fade-underwater)，品質較低的來源）。對渲染器的含義〔推算〕：自然光的光路是「深度＋到鏡頭的水平距離」，載具燈光的光路是「燈到物體＋物體到鏡頭」；100 m 深處燈下 2 m 外的紅色物體仍偏紅，15 m 深處只靠日光的同一物體則是灰褐色。

Akkaynak 與 Treibitz 指出沿用大氣除霧的水下成像模型是錯的：水下衰減強烈依賴波長，而且支配背向散射的係數與支配直接訊號衰減的係數不同〔摘要，PDF 403〕（[CVPR 2018](https://openaccess.thecvf.com/content_cvpr_2018/html/Akkaynak_A_Revised_Underwater_CVPR_2018_paper.html)）；對非常混濁的 Jerlov 7C/9C 沿岸水型，背向散射飽和、場景被均勻水色取代的距離在 4–5 m 就到達〔摘要〕（[CVPR 2018 補充資料](https://openaccess.thecvf.com/content_cvpr_2018/Supplemental/0068-supp.pdf)）。混濁港區能見度可低於 1 m〔摘要〕（[TransNav](https://www.transnav.eu/files/Use_of_an_ROV_with_Modulated_Lighting_for_Diagnosing_the_Technical_Condition_of_Submerged_Port_Wharf_Structures,1527.pdf)）。也就是說，「霧」必須是每個 RGB 通道各自一組直接衰減係數與一組散射係數，而不是單一霧色〔推算；確切方程式未從論文讀到，寫程式前須對照 PDF〕。各水型各通道的係數數值、以及港口／沿岸／外海／湖泊的典型能見度表，本次都沒有取得可引用的來源。

背向散射是近場最主要的劣化：懸浮顆粒被自家燈光照亮後反射回鏡頭，燈越靠近光軸、越亮就越嚴重，所以使用者把燈移遠、裝在支臂上並向內夾角，代價是阻力與勾纏風險（[Blue Robotics 論壇：燈位](https://discuss.bluerobotics.com/t/rov-light-placement/761)）；Deep Trekker 手冊直接指示濁水中把主燈調暗或關掉以減少背向散射（[Deep Trekker 支援：Lights](https://support.deeptrekker.com/accessories/lights)）。這意味著濁水中燈光亮度的最佳值遠低於最大值〔推算〕。揚沙（silt-out）由朝向底部的推力或載具擾動造成，嚴重時攝影機完全失效而聲納照常運作（[Wikipedia: Silt out](https://en.wikipedia.org/wiki/Silt_out)）。顆粒在畫面上的大小、密度、漂移速度與沉降時間沒有任何量化來源。

### 鏡頭、燈光與延遲：可引用的硬數字

觀測級載具的燈是數千流明的冷白 LED 泛光：Blue Robotics Lumen 單顆超過 1500 lm、15 W、水中 135° 光束（[Blue Robotics Lumen](https://bluerobotics.com/?p=23076)），色溫在官方頁寫 5700 K、經銷商寫 6200 K；V6 Expert 為兩顆共 6000 lm、5500 K，光束角一說 160°、一說 120°（[Aonic V6 Expert](https://aonic.com/my/products/industrial/rov/qysea-fifish-v6-expert/)、[X-Ray Mag](https://xray-mag.com/content/qysea-fifish-v6-expert-m100a-underwater-ai-rov)）；X1 為 2 × 6,000 lm、120°，色溫未公布。120–160° 的光束沒有銳利光斑邊緣，熱點來自距離而非光束形狀〔推算〕。

BlueROV2 標準相機是 1/2.9" Sony IMX322/323、1080p、焦距 2.97 mm、水平 80° × 垂直 64°、畸變 1%、板載 H.264 壓縮（[Blue Robotics Low-Light HD USB Camera](https://bluerobotics.com/?p=17135)）。平面窗會把空氣中 90° 的視角縮到水中約 64°，並帶來枕形畸變與邊緣色散，球罩則保持空氣中視角但邊緣變軟（[Knight Optical](https://knightoptical.com/news/picture-perfect-underwater-photography-shots-dome-ports-vs-flat-ports)）；用司乃耳定律（n ≈ 1.33）可重現這個 90°→64° 並推得 80 × 64° 鏡頭在平面窗後約為 58 × 47°〔推算〕。V6 的 166° 鏡頭遠超平面窗極限，必然是球罩或濕式校正光學並帶明顯魚眼桶形畸變，所以**畸變是機型專屬而非通用**〔推算〕；V6 Expert 水中 FOV 96° 是唯一有來源的 FIFISH 水中視角，X1 的沒有。自動曝光與白平衡的收斂時間、低照度雜訊、鬼影等行為沒有任何量化來源。

影像延遲不是零：FIFISH 廠商自述 150–200 ms（見前節）；第三方文件引述 BlueROV2 為 200 ms（[OysterBot 圖 2](https://projects.sare.org/media/pdf/O/y/s/OysterBot-Figure-2.pdf)）；使用者回報設定不當時達 1–2 秒，並把 250 ms 以下當作舒適操控的目標（[Blue Robotics 論壇：camera latency](https://discuss.bluerobotics.com/t/bluerov2-camera-latency/2872)）；最佳化的自製系統可到 100–110 ms〔摘要〕（[Lanai Pro](https://discuss.bluerobotics.com/t/new-rov-lanai-pro-rev-3/20712)）。合理的模擬預設是 150–250 ms，1 秒為故障狀態；延遲在潛水中逐漸增長與偶發卡頓也是真實的故障行為〔推算〕。這些都不是受控量測，X1 經 Q-iRC 的實際延遲必須自己量。

### 疊字與螢幕配置：兩種真實風格，沒有強制標準

檢測影片例行疊上字元，使每一幀能對回時間與位置〔摘要〕（[Hydro International](https://www.hydro-international.com/content/article/send/digital-video-offshore)）。小型載具的代表是 VideoRay Pro 4：日期時間、最多 8 行操作員即時輸入的自訂文字、以「H」開頭的航向、以「D」開頭的深度、水溫；一鍵開關整個疊字，個別項目不能單獨切換；疊字只出現在數位影像而不在類比輸出，並錄進截圖與影片（[VideoRay Pro 4 手冊](https://download.videoray.com/documentation/pro_4/html/cockpit_overlay_text.html)）。測量級的代表是 NETmc VideoTXT：1U 機架式字元產生器，由導航電腦經 RS-232 驅動，一至四個獨立通道，「適合管線測量，各通道可分別標示 port、centre、starboard」，並可儲存客戶專屬的頁首範本（[NETmc VideoTXT](https://netmcmarine.co.uk/images/product-pdfs/VideoTXT_rev2.pdf)）；管線檢測的欄位還包括東距北距、KP、離底高度〔摘要〕。相反地，Blue Robotics Cockpit 不把遙測燒進畫面，而是錄原始串流並另存字幕檔（[Cockpit 文件](https://blueos.cloud/cockpit/docs/latest/usage/advanced/)）。因此「乾淨訊號」對「燒入疊字」的切換符合真實做法〔推算〕。**沒有找到任何公開文件強制規定疊字欄位**，內容由客戶與專案規格決定；CP 讀值、潛次編號、纜線圈數作為疊字欄位也沒有來源證實。

各級載具的螢幕配置模式一致〔推算，歸納自下列來源〕：攝影機畫面佔滿螢幕，航向、深度、姿態、模式／解鎖狀態、電力、連線、時間、錄影狀態常駐，其餘（設定、聲納、海圖、診斷）放在其他視圖或其他螢幕。Cockpit 是上方共用列、下方每視圖專屬列、中間自由擺放的小工具（姿態 HUD、羅盤帶、深度 HUD 都是可選線色的細線圖形），連線或斷線時畫面邊框閃綠或紅（[Cockpit 文件](https://blueos.cloud/cockpit/docs/latest/usage/advanced/)）；Falcon 的 iCON 水面單元配 22 吋可拆式日光可視觸控螢幕、可自訂的駕駛顯示、USB 手控器與螢幕虛擬控制器（[Falcon 型錄 rev 18](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)）；作業級則是含駕駛搖桿盤、圖形螢幕、影像螢幕、聲納處理與顯示、機械手控制的控制台，裝在 20 或 40 呎貨櫃裡（[ISE](https://ise.bc.ca/product/control-systems-consoles/)）。真實駕駛只有第一人稱鏡頭、沒有周邊視野也沒有追尾鏡頭〔摘要〕（[SAGE 2026](https://https-sage-cnpereading-com-443.webvpn1.xju.edu.cn/doi/10.1177/02783649261455065)）；外部視角在現實中只以合成輔助的形式存在。

## 推桿是推力不是速度：0.3 m 內停住，然後隨流漂

### 真實載具的預設語意是「開迴路水平、閉迴路航向與深度」

ArduSub 的 Manual 模式沒有任何回授；Stabilize 在駕駛不下轉向指令時保持航向並拉平橫滾，垂直完全手動；Depth Hold 再加上鬆開垂直桿即保持當前深度（[ArduSub 操作中功能](https://www.ardusub.com/reference/ardusub/features-while-in-operation.html)）。所有位置參考模式（POSHOLD、AUTO、GUIDED、CIRCLE）都需要位置來源（[ArduPilot Sub 模式表](https://ardupilot.org/sub/docs/modes.html)）。Pilot gain 線性縮放輸入、控制可用推力，按鍵功能包含逐級增減、50%/100% 切換，以及保持當前搖桿輸入的「input hold」（巡航的是推力而非速度）（[ArduPilot Sub 按鍵](https://ardupilot.org/sub/docs/buttons.html)）。Depth Hold 下垂直桿移動的是深度目標，受 PILOT_SPEED_UP/DN 與 PILOT_ACCEL_Z 限制，另有油門死區 THR_DZ（[ArduPilot Sub 駕駛控制](https://ardupilot.org/sub/docs/pilot-control.html)）。Falcon 同理：自動航向與自動深度（latch 與 track 模式）為標配，自動高度、DVL 定點、相對航點與自動速度都是選配，且沒有自動俯仰／橫滾（[Falcon 型錄 rev 18](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)）。

所以受訓者應該感受到、而且與空拍機式速度控制不同的東西是〔推算〕：鬆桿不會主動煞車；固定桿量給的是固定推力，對地速度隨洋流、纜線負載與航向而變；纜線拉力沒有自動補償；側移比前進慢；倒車推力較弱；只有垂直軸（定深時）與偏航像速率指令。對應到本專案的共用契約：`assist: 0` 對應 ArduSub Manual/Stabilize/Depth Hold 與無 DVL 的 Falcon；`assist: 1/2` 對應 DVL 輔助的速度與定點保持，並應繼承 DVL 的限制（高度窗、失鎖、強流下推力飽和）。X1 標配 Q-DVL，其「原廠預設手感」很可能更接近 `assist: 2`，但這一點正是查不到、必須實機確認的項目。

### BlueROV2 Heavy 是唯一有完整實測係數的參考載具

von Benzon 等人（Aalborg，JMSE 2022）以水池加 SBL 定位辨識出：質量 13.5 kg；實測極速前進 0.72 m/s（85 N）、側移 0.63 m/s（85 N）、垂直 0.71 m/s（120 N）；二次阻尼前進 141、側移 217、垂直 190 N·s²/m²，線性阻尼前進 13.7、垂直 33.0 N·s/m；附加質量 6.36 / 7.12 / 18.68 kg（經驗法估算而非量測，平移誤差 10–20%、轉動 30–100%）；模型穩態速度誤差約 10%（[von Benzon et al. 2022](https://doi.org/10.3390/jmse10121898)）。由這些係數可算出〔推算，非論文陳述〕：前進等效質量約 19.9 kg，滿推力起步加速度約 4.3 m/s²，零點幾秒即達九成極速；從 0.72 m/s 鬆桿後約 0.3 秒降到半速、約 1.4 秒降到 0.05 m/s、**總滑行約 0.30 m**；最大偏航率約 3.6–3.8 rad/s（約 206–220°/s）。它不像船那樣滑行。

這也暴露了廠商數字的樂觀：Blue Robotics 標稱標準版 1.5 m/s（[BlueROV2 頁面](https://bluerobotics.com/store/rov/bluerov2/)），舊版規格書寫 1 m/s〔摘要〕，員工在論壇重申 1.5 m/s 但提到內部有人認為約 1 m/s 較實際，而且 1.5 m/s 假設只下前進指令（[BR 論壇](https://discuss.bluerobotics.com/t/bluerov2-heavy-configuration-water-current-speed/17002)）；Heavy 實測只有約一半。**這是對 X1 的直接警訊：「4.5 節」同樣是廠商數字，實機很可能較低，必須自己量。** 推進器方面，T200 在 16 V 前推 5.25 kgf、倒推 4.1 kgf（倒推約為前推的 78%）（[Blue Robotics T200](https://bluerobotics.com/store/thrusters/t100-t200-thrusters/t200-thruster-r2-rp/)）；單一使用者量到指令到輸出變化約 110 ms（[BR 論壇：T200 響應](https://discuss.bluerobotics.com/t/response-time-and-minimum-rotation-speed-for-t200-with-basic-esc/11112)），論文辨識的轉移函數主導時間常數約 0.076 秒〔推算〕，以 0.08–0.11 秒的一階延遲建模兩者皆可重現。X1 的 Q-Motor Pro 與 Falcon 推進器都沒有公開的推力曲線或響應時間。

| 項目 | FIFISH X1 | FIFISH V6 Expert | BlueROV2（Heavy） | Saab Seaeye Falcon |
|---|---|---|---|---|
| 空氣中質量 | ≤30 kg | 4.6 kg | 11–12 kg（Heavy 實測 13.5 kg） | 60 kg（DR 100 kg） |
| 深度 | 350 m | 100 m | 100 / 300 m | 300 m（DR 1000 m） |
| 推進器 | 6，向量佈局（幾何未公布） | 6（V6：4 向量＋2 水平） | 4 向量＋2 垂直（Heavy 4＋4〔摘要〕） | 4 向量＋1 垂直 |
| 速度 | 官方 4.5 節；經銷商分軸 4.5/3.5/2.5/1.5 節 | 3 節 | 標稱 1.5 m/s；Heavy 實測 0.72/0.63/0.71 m/s | >3 節 |
| 推力 | 經銷商「前進最高 30 kg」 | 未公布 | 前 9／側 9／垂直 7 kgf（Heavy 垂直 14〔摘要〕） | 前 42–50／側 25–28／垂直 13 kgf（新舊文件不一致） |
| 供電 | 纜線直供 | 156 Wh 電池，1–4 h | 電池，約 2–4 h | 水面單相交流 |
| 纜線 | 350 m × 9.5 mm，300 kgf（經銷商） | 100/200 m × 4.6 mm，100 kgf | 7.6 mm 或 4.0 mm；斷裂 155 kgf／工作 35 kgf | 光纖選配可達 1100 m |
| 保持功能 | 前＋下 Q-DVL 定點（宣稱 4 節） | 定深 ±1 cm、姿態鎖定；定點需 Q-DVL 或視覺 | 航向、深度；定點需 DVL | 航向、深度標配；高度、DVL 定點選配 |

表中 Falcon 數字見 [Falcon 型錄 rev 18](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf) 與 [Saab Seaeye Falcon 頁面](https://www.saabseaeye.com/solutions/underwater-vehicles/falcon)（前者寫前推 50 kgf，後者寫 42 kgf）。以推力重量比看〔推算〕，BlueROV2（約 0.78）與 Falcon（0.70–0.83）水平能力相近，但 Falcon 垂直只有約 0.22，升沉應明顯遲鈍；X1 若採信經銷商數字則前進推重比約 1.0，垂直則因 1.5 節的垂直速度而顯得相對弱。Falcon 沒有任何公開的水動力係數。

### DVL 定點不是魔法：有高度窗、會漂、會失控

Water Linked DVL A50 的離底高度範圍是 5 cm 到 50 m，35 m 以上取決於底質與鹽度〔摘要〕（[Blueye DVL A50](https://www.blueyerobotics.com/products/dvl-a50)）。DVL 航位推算的位置誤差隨時間無上界累積，鬆軟或崎嶇的底質使底鎖更難（[BR 論壇：DVL A50 精度](https://discuss.bluerobotics.com/t/dvl-a50-accuracy/14873)）；Blueye 建議每 15–20 分鐘浮出水面用 GPS 重設起點（[Blueye 導航文章](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)）。現場回報包括定點模式啟動後載具跑走、解鎖後 5–10 秒 DVL 速度讀數發散導致推進器亂推〔摘要〕（[BR 論壇：DVL A50 問題](https://discuss.bluerobotics.com/t/ongoing-dvl-a50-issues/11419)）。沒有找到任何小型 ROV 定點精度的實測數字（公分 RMS）。模擬器的定點輔助應只在高度窗內可用、在中層水或鬆軟陡峭底質上劣化、失鎖時退回漂移〔推算〕；本專案 `state.assist.limited` 欄位正好對應推力飽和情境，但 X1 Q-DVL 失鎖時的實際表現仍是未知數。

## 纜線、聲納、流程與事故構成操作的另一半

### 臍帶纜是主動的力，不是長度上限

模型研究顯示，在 0.5 m/s 洋流下的模擬檢測中，BlueROV2 Heavy 平均約 **25%、峰值約 38%** 的水平推力只是用來抵消纜線力；被動測試中 15 m 纜線約 30 秒拉直，無動力載具約 100 秒後被拖到水面；即使在水池裡人工餵纜，纜線擾動也無法消除（[von Benzon et al. 2022](https://doi.org/10.3390/jmse10121898)，模型結果而非實測）。以該論文的纜線參數（7.5 mm、法向阻力係數 1.2）計算，橫向每公尺阻力約 4.5v² N，0.5 m/s 下約 75 m 橫擺的纜線就等於 Heavy 的全部水平推力〔推算〕。把同一公式套到 X1 的 9.5 mm 纜線則為每公尺約 5.7v² N，1 m/s 橫流下約 50 m 橫擺纜線即等於經銷商所稱的 30 kgf 前進推力〔推算；阻力係數為通用假設、推力為經銷商數字，僅供量級參考〕。X1 纜線的浮力、單位質量與實際阻力完全沒有公開數據。

操作準則高度一致。VideoRay：「使用到達目標區所需的最短纜線」，放太少影響操控、放太多則勾纏、打結或被螺槳割斷；下水點應在作業區上游並保持直視；收納用線盤或正反繞／八字繞，單向盤繞會留下難以消除的扭轉（[VideoRay Pro 4 纜線管理](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)）。多餘的纜線「像帆一樣」拉載具，橫跨洋流作業時阻力更大，要「把纜線當釣線」；強流中在 ROV 後方夾配重直到纜線垂直，配重與 ROV 間至少留 15 cm；從岸邊作業時寧可多次移動控制箱也不要多放纜（[VideoRay 強流技巧](https://videoray.com/?p=13174)）。纜線手（VideoRay 自己暱稱「tether monkey」）負責放出適量、避開水面危險、保持整齊並與駕駛溝通（[VideoRay 現場作業](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)），通常每放約 5 m 報一次〔摘要〕；每一圈扭轉都會對載具施加扭矩，駕駛要看圈數計〔摘要〕。勾纏時的緊急程序是：**不要慌、不要拉纜線**；先評估；能動就掉頭沿纜線飛回勾纏點；只有確信不會越拉越緊時才從水面拉（[VideoRay 勾纏應變](https://download.videoray.com/documentation/mss/html/emergency_snag.html)）。「保持定位」練習明確寫到纜線回彈會把 ROV 往出發方向拉並使其偏航，解法是先過頭再倒回或請纜線手多放纜（[VideoRay Hold Station](https://download.videoray.com/training/vtl_pro_5_exercises_manual_control/html/_hold_station_narration.html)）。

### 下水回收是一串可檢核的閘門

Blue Robotics 的 22 步潛前檢查本質上是「每樣東西都拉一拉、扭一扭」：配重、側板與框架、端蓋線束、纜線固定環、每個穿艙件、排氣塞、電池艙、推進器、燈、球罩螺絲、徑向密封；接著是功能測試（Manual 模式解鎖、前推確認水平推進器、垂直桿確認垂直推進器、空氣中不超過 30 秒、上鎖）。**載具入水且施放者離開後才解鎖，回收前先上鎖**；配平要求水平漂浮、壓到半臂深放開能保持深度、寧可略正浮力；潛後清水沖洗，離水超過 15 分鐘要遮陽；4S 鋰電池在 12.5 V 回收、低於 12.0 V 有永久損壞風險；失去電力或連線時以中等速度收纜（[Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)）。真空測試的通過標準（抽到 10 inHg、15 分鐘後仍高於 9 inHg）來自第三方手冊〔摘要〕。人員編制方面，VideoRay 列出駕駛、纜線手、附件操作員、督導（通常負責記錄日誌）、技師五種角色（[VideoRay 現場作業](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)）。這些與 FIFISH V6 的「入水後解鎖、空轉不超過 30 秒、鎖定後回收」邏輯一致，是可以跨機型採用的流程骨架；海況與風力限值、Falcon 級的吊放程序則沒有來源。

### 聲納與導航感測器各有特徵性的失效樣貌

小型 ROV 用兩類影像聲納：多波束（Oculus M750d：750 kHz / 1.2 MHz、量程 120 / 40 m、水平 130°、最高 40 Hz〔摘要〕（[Oculus M 系列](https://download.videoray.com/documentation/mss/pdf/blueprint_subsea/oculus/Oculus_M-Series_Datasheet_EN.pdf)）；Gemini 720ik：720 kHz、0.2–120 m、512 波束、120° × 20°〔摘要〕）與機械掃描式。Blue Robotics 的掃描聲納指南是最完整的一手教材：影像等同俯視圖，越亮回波越強，方位是相對艏向順時針；氣體、岩石、混凝土、金屬是強反射體，泥、沙、植物是弱反射體，只有朝向聲納的面才強回波；目標投下聲學陰影，高度高、俯角陡時陰影短而難判讀；同一斜距的目標無法分離；機械掃描未完成前移動會使影像拖影。駕駛的六步接近法是：坐底、360° 掃描、讀相對方位、轉到目標在 0°、把扇區縮到 60–90° 提高更新率、保持目標在畫面中前進；「10% 法則」是離底高度取量程的 10%（[Blue Robotics 掃描聲納指南](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)）。多路徑、增益設定、推進器噪聲等假影沒有來源描述；X1 三向避障聲納與其在 App 上的顯示樣式也沒有。

導航方面，磁羅盤在鋼構附近失準：一則現場回報是 BlueROV2 在鋼質沉船上打轉並出現偏航重對準警告，建議是後退且不要在附近用自動航向〔摘要〕（[BR 論壇](https://discuss.bluerobotics.com/t/rov-problem-spinning-around/10680)）；QYSEA 自己的斷線指南也把大型金屬結構旁的磁干擾列為原因。聲學定位（USBL/SBL）給的是絕對但帶跳動的位置，港牆與海床回波及他船噪聲會造成錯誤讀數；融合系統用 DVL 平滑聲學跳動、用聲學修正 DVL 漂移（[Blueye 導航文章](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)）。三層導航各有可模擬的失效特徵〔推算〕：僅羅盤加深度（近鋼構航向飄移）、DVL（平滑但會漂）、聲學定位（絕對但跳動）。

### 檢測怎麼飛、事故怎麼發生

唯一找到的量化航線規則來自 VideoRay 碼頭牆 SOP：**離牆距離約 0.7 × 能見度，航線間距約 1.3 × 能見度**（約 10% 重疊）（[VideoRay 碼頭牆 SOP](https://download.videoray.com/documentation/sop_pwi/html/_1_4_define_inspection_parameters.html)）。樁柱以面對樁的垂直航次檢查，下行時鏡頭略朝下、上行時略朝上，每趟結束後保持面對樁繞到下一起點（[VideoRay 樁柱 SOP](https://download.videoray.com/documentation/sop_ppi/html/vertical.html)）。環境規劃以洋流為主：VideoRay 把 1.5 節以上定義為強流，給出「可用推力約為載具質量兩倍」的經驗法則，並建議盡量在平潮作業且不要只信潮汐表，因為平潮在離參考港不遠處就可能偏移 30–60 分鐘；船殼、橋墩與沉船後方的渦流可作遮蔽（[VideoRay 強流技巧](https://videoray.com/?p=13174)）。小型抓手的夾持力約 100 N 等級〔摘要〕，用途是掛回收繩、解纜而不是起吊。陰極保護量測、管線與隧道檢測的飛行程序、航線上的檢測速度都沒有來源。

有兩起事故細節足以重建成情境。**IMCA 安全通報 02/23**：例行導管架檢測中，ROV 在強潮流下被推入結構內部受困，纜線受損後失去電力與遙測；小心拉扯未果，纜線被切斷繫在導管架上；隔日再試時受損纜線斷裂、ROV 漂走，信標數小時後失聯。檢討指出緊急程序未涵蓋此情況、該用三人卻只有兩人、信標詢問頻率設得太高耗盡電池；直接原因是纜線在導管架上磨斷，改正措施包括在程序中加入環境限值，以及**在駕駛介面加上洋流讀數**（[IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)）。**密西根湖案**：2014 年一台 SEAMOR ROV 在約 134 m 深的沉船上纏到測深銅線，團隊拉纜線反而把結拉緊（文章稱之為「經典錯誤」），三四小時後切纜棄置；2021 年第二台 ROV 用聲納 10 分鐘內找到它，2022 年由第二台 ROV 掛纜吊起、潛水員約一分鐘割斷纏線後回收，清潔後仍能上電（[Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)）。兩案共用同一條因果鏈〔推算〕：洋流或勾纏困住載具，人員拉扯或等待，纜線磨損或越拉越緊，追蹤失效。小型 ROV 纜線被母船螺槳割斷、進水、零能見度迷向等事故，雖是廠商文件點名的常態風險，卻沒有找到有細節的公開案例，也沒有按原因分類的事故統計。

## 訓練看的是日誌與誤差，遊戲的痛點是上手而不是寫實

### 業界考核以證據為本，模擬器時數正被納入制度

IMCA 是商業離岸 ROV 人員的實質框架。R 002（IMCA 認可 ROV 入門訓練課程要求）現行為 2025 年 8 月第 5 版，修訂史顯示模擬器的角色正被積極改寫：2024 年 9 月加入逐項列出的模擬器組成，2025 年版加入對新模擬器指引的引用（[IMCA R 002](https://www.imca-int.com/resources/technical-library/document/b0f5885b-c55b-ee11-8def-6045bdd0ecdb/)）。2025 年 6 月 IMCA 發布 R 028（Class-A ROV 模擬器認證要求，定義為「高擬真、完全沉浸式訓練系統」，訂有最低能力、性能基準與評估程序）與 G 014（模擬器系統核可臨時方案）（[IMCA 新聞 2025-06-10](https://www.imca-int.com/news-events/imca-news/news/imca-publishes-new-guidance-for-rov-simulator-approval/)）。晉級需在現職等被評為合格之外，再有 100 小時經記錄且受監督的飛行時數與 180 天離岸工作〔摘要，原頁 401，出自較舊文章，須對照現行 C 005〕（[IMCA 舊文](https://legacy.imca-int.com/?p=2490)）。**R 028 的具體技術準則、C 005 的各職等能力表、R 002 的課綱時數表都拿不到**（會員限定），而這些與本專案的訓練用途直接相關。合理的定位〔推算〕是：不宣稱 IMCA 等效，但讓練習項目命名與每場次可匯出的證據（飛行時數、完成任務、環境條件、對標準的通過與否）能對應到日誌本結構。

廠商課程提供了具體的能力清單：VideoRay 分成知識要求（載具組件、控制軟體、專案規劃、資料處理、診斷）與技能熟練度（電腦使用、作業戰術、維護），並附時數日誌，**駕駛、纜線手、附件操作、維護、督導各自一欄**；練習組為「手動控制」、「自動模式」與「DP 與 Jog 控制」（[VideoRay 能力項目](https://download.videoray.com/documentation/vtl/html/competencies.html)）。其 3–5 天的操作員課程涵蓋系統總覽、纜線施放系統、機械手、聲納、海圖與航點、定位導航、自主任務、診斷與維修（[VideoRay 2026 課程說明](https://videoray.com/wp-content/uploads/ROV_Operator_Course_Description-2026.pdf)）。商業學校的課程多為 3–7 週且以技師內容為主〔摘要〕，一位結業者的履歷只列出約 12 小時飛行時數〔摘要，單一個案〕，這正是模擬器要填補的缺口。沒有找到 QYSEA 的任何操作員訓練計畫。

### TRANSoM 提供了現成的評分矩陣與最重要的擬真度證據

TRANSoM（ONR 資助）的課程讓學員在電腦教練下練習下潛、轉場、懸停、繞行、對接五個階段，評分矩陣是五階段乘六項技能（保持航線、穩定前進、平順操控、面向目標、避免碰撞、拍照），每格以綠黃紅表示。底層指標每秒至少取樣一次，彙整為 RMS 誤差、最大最小誤差與超出門檻的時間百分比：路徑偏差、航向與目標方位夾角、深度、懸停距離、規定距離偏差、速度上下限、操控平順度（指令推力變異數、過零次數、每軸反桿次數）、朝目標的速度分量。門檻由專家與中階駕駛飛 12 項任務訂出 59 組，而且**有流與無流必須分開訂門檻**，因為洋流「大幅影響難度」（[Fletcher & Roberts, I/ITSEC 1998](https://xcdacademy.s3.amazonaws.com/iitsec/1998/72757R4N63405774.pdf)）。

同一研究是唯一找到的 ROV 對照實驗：32 名受試者分四組，操桿時間同為 4.5 小時，前後測都在真實 ROV 上進行。在未訓練過的檢測任務上，三個訓練組（模擬器加智慧教練、純模擬自由練習、純真機練習）都顯著優於無訓練組；純模擬與純真機的轉移效果相當。反常的是，初始能力低的學員在「完整訓練」組沒有進步，作者的解釋之一是通關式進度使 8 人中有 3 人到不了最難的關卡（強流、低能見度），而自主練習組「把大部分時間花在較難的情境」。擬真度驗證發現穩態響應與軸間耦合與真機相符；模擬的時間響應量起來比真機快，駕駛卻感覺較慢，歸因於較低的畫面更新率。外部「體育場」視角在訓練中提升表現，測驗時拿掉也沒有負面影響（[Fletcher & Roberts 1998](https://xcdacademy.s3.amazonaws.com/iitsec/1998/72757R4N63405774.pdf)）。這份證據老（1998）、樣本小（每組 8 人），2000 年後沒有找到任何 ROV 駕駛的對照轉移研究，但它給出的設計含義很清楚〔推算〕：擬真優先序是穩態動力學與軸間耦合、相同的實體控制介面、畫面更新率、洋流與能見度；難度不應以通關硬鎖；第三人稱視角是正當的訓練輔助，但考核時應可關閉並標示為輔助。這與本專案「遊戲化只加在控制輔助層與前端呈現層」的原則一致。

### 專業模擬器賣的是纜線、故障注入與回放；Steam 上幾乎沒有對手

商業作業級模擬器的賣點高度重疊〔以下多為 2008–2019 年行銷與業界媒體摘要，未見獨立驗證〕：Forum VMAX 標榜動態纜線系統、真實的物體水動力、即時任務錄製回放與情境編輯器，標準情境庫用於「纜線管理、進入評估與機械手控制」等技能的訓練與評估〔摘要〕（[Forum VMAX](https://f-e-t.com/?p=2974)）；Fugro DeepWorks 標榜全力模型物理、可在任務中改變並作用於纜線的三維洋流剖面、整個世界狀態可回捲到任一點〔摘要〕（[Hart Energy](https://hartenergy.com/exclusives/rov-simulation-training-tool-cuts-operational-costs-and-risks-18642)）；GRi VROV 的教官控制台可即時改變洋流、濁度、纜線效應並注入故障〔摘要〕（[GRi VROV](https://grisim.kayako.com/article/19-virtual-remotely-operated-vehicle-overview)）。沒有一家公開定價或驗證數據，也沒有找到使用者的公開批評。開源模擬器（Stonefish、DAVE、HoloOcean、MARUS、UNav-Sim）鎖定自主研究而非駕駛訓練，一篇 2025 年回顧沒有為其中任何一個報告纜線建模（[Aldhaheri et al., arXiv 2504.06245](https://arxiv.org/html/2504.06245v1)）。

消費端，Steam 上唯一找到的專門 ROV 駕駛作品是 subROV: Underwater Discoveries：售價 19.99 美元，2022 年 12 月進入搶先體驗至今，63 則評論 90% 好評（[Steam subROV](https://store.steampowered.com/app/1648760/subROV/)）。GameLuster 給 7/10，稱讚不計時、可任意順序的潛水與鼓勵徹底探索的圖鑑，「徹底具教育性」；批評是「到處都是按鈕」、教學得重玩、「前幾個任務感覺極慢且重複」、ROV 移動慢、早期潛水「有點空」（[GameLuster](https://gameluster.com/review-subrov-underwater-discoveries-roving-in-the-deep/)）。四年約 60 則評論顯示這個利基小而近乎空白〔推算〕；摩擦點是上手（一次給太多控制）、慢、早期內容稀薄，而不是寫實本身。subROV 似乎未把纜線當核心機制，物理建模的纜線會是差異化，但沒有證據顯示玩家是否想要它。個別 Steam 評論內文、Reddit r/rov 的駕駛討論、鄰近的潛艇與潛水遊戲都未能取得，工作中的駕駛對商業模擬器的第一手批評因此是空白。

## 對齊清單：通用骨架用公開數據，X1 專屬層只能自己量

把前述證據收斂成一張表。「公開數據可用」表示已有讀過原文的來源，可直接據以實作；「僅摘要或推算」表示方向可信但數字需再核對；「必須自有 X1 量測或截圖」表示公開管道查不到。

| 對齊項目 | 公開數據可用（已核實） | 僅摘要或推算，需再核對 | 必須自有 X1 量測或截圖 |
|---|---|---|---|
| 質量、尺寸、深度、極速 | X1 官方：≤30 kg、350 m、4.5 節、抗流 4.0 節 | 分軸速度 4.5/3.5/2.5/1.5 節、30 kgf、尺寸（僅經銷商）；型錄 PDF（403） | 各軸實測極速、繫纜拉力、水中重量與配平、重浮心距、推進器幾何 |
| 加減速與滑行 | BlueROV2 Heavy 完整係數與實測極速 | 0.3 m 滑行、4.3 m/s² 起步、206–220°/s 偏航率（由係數推算） | X1 各軸階躍響應、鬆桿滑行距離與時間、最大偏航率、推進器響應延遲 |
| 控制語意與模式 | ArduSub 各模式；V6 的 A/S/C、定深、姿態鎖定；Falcon 自動功能清單 | Falcon latch/track 的確切含義 | X1 是否沿用 A/S/C；鬆桿時定點是否自動進入；無 DVL 鎖時的行為；速度檔位與搖桿曲線預設值 |
| 定點與 DVL | Q-DVL 0.1–100 m 高度範圍（廠商）；DVL 漂移與重設建議 | A50 規格、失控案例（摘要）；公分級精度無數字 | X1 定點精度、4 節抗流是否屬實、失鎖與推力飽和時的表現與提示 |
| 遙控器 | Q-iRC 控制元件清單、螢幕、續航、埠；V6 遙控器佈局與 curvature／attenuation | Q-iRC 校正與模式選項（經銷商摘要） | Q-iRC 每個軸、旋鈕、開關、五向鍵與自訂鍵的預設功能；搖桿行程、死區與回中手感；完整 ROV/UAV × USA/JPN/CHN 對照表 |
| App 畫面與疊字 | V6 世代 HUD 標註配置、深度條三段量程；VideoRay 疊字欄位；Cockpit 小工具清單 | 測量級疊字欄位（東距北距、KP、高度）；FIFISH 自訂浮水印內容 | Q-iRC 上 X1 版 App 的逐畫面截圖：多視窗配置、聲納與地圖視窗、DVL 讀數、避障警告、警報文字、自檢流程 |
| 影像外觀 | BlueROV2 相機規格；平面窗與球罩的視角效應；色彩依光路流失的原則；燈光流明與色溫 | Jerlov 水型係數與 4–5 m 遮蔽距離；港區 <1 m 能見度；H.264 假影（推論） | X1 水中 FOV 與畸變、燈光色溫、自動曝光與白平衡收斂、低照度雜訊、實際水域的懸浮物與背向散射樣貌（需實拍影片） |
| 影像延遲 | FIFISH 廠商自述 150–200 ms（V6 世代）；BlueROV2 使用者回報範圍 | BlueROV2 200 ms（第三方）；100–110 ms 最佳化案例 | X1 經 Q-iRC 的玻璃到玻璃延遲、外接 HDMI 的延遲、長時間作業後是否累積 |
| 臍帶纜 | 操作準則、纜線手角色、勾纏程序、回彈現象；BlueROV2 纜線力占比（模型） | 每公尺阻力公式與 X1 量級估算；5 m 報數；扭轉扭矩；X1 纜線規格（經銷商） | X1 纜線水中浮力、單位質量、不同放纜長度與流速下的拉力與可維持航向、線盤操作手感 |
| 聲納與感測器 | 掃描聲納顯示原理、陰影、六步接近法、10% 法則；羅盤近鋼構失準；融合導航原理 | Oculus／Gemini 規格（摘要，且有互相矛盾處） | X1 三向避障聲納的顯示與告警、可選影像聲納在 App 的呈現、雷射尺與 AR 尺畫面 |
| 下水回收 | BlueROV2 22 步檢查與解鎖閘門；V6 上電、入水、回收、清洗流程與提示音描述 | 真空測試標準（第三方手冊） | X1 岸電單元開機順序、潛前檢查表、30 kg 吊放方式、提示音與燈號、環境限值 |
| 失誤與事故 | IMCA SF 02/23、密西根湖案；V6 廠商承認的怪癖 | 作業級 LARS 事故（摘要）；螺槳割纜、進水無公開個案 | X1 過流、過壓、過載警報的觸發條件與畫面；斷線重連時間 |
| 訓練與考核 | TRANSoM 評分矩陣與指標；VideoRay 能力清單與日誌欄位；IMCA 文件架構 | 100 小時／180 天；學校課綱時數 | 公司內部對 X1 操作員的合格標準（需由資深操作員飛基準航次來訂門檻）；IMCA R 028 準則需經會員管道取得 |

實務上，X1 專屬層可以用一次有計畫的實機作業補齊大半：在水池或靜水中錄下各軸滿桿階躍與鬆桿的螢幕錄影加外部攝影，用同一段畫面同時量延遲與滑行；逐一切換模式並記錄鬆桿行為；把 Q-iRC 每個控制元件動一遍並截下 App 每個視窗與設定頁；在已知流速處記錄不同放纜長度下的可控性。QYSEA 的 OpenSDK 文件本次沒有找到，若公司已有管道，應一併取得。

## Conclusion

這份研究改變的認知是：「與真實 ROV 一致」主要不是畫面像不像，而是資訊被限制的方式與力的來源對不對。真實駕駛的難處集中在四件事上，分別是纜線作為主動力（回彈、阻力、勾纏）、只靠一支受限鏡頭與聲納建立空間感、洋流讓固定桿量不等於固定速度、以及程序紀律（何時解鎖、放多少纜、何時中止）。這四件事恰好都有公開的一手資料可依，也恰好是唯一的消費級對手沒有做的部分；而遊戲端被批評的是上手負擔與早期內容空洞，不是寫實本身。所以訓練與 Steam 兩個目標在物理層並不衝突，分歧只出現在輔助層與呈現層，這與專案既有的分層原則相符。

真正的風險在於把廠商數字與類推當成 X1 的事實。BlueROV2 的教訓是標稱極速可以是實測的兩倍，而 X1 的分軸速度目前只有單一經銷商背書，鍵位、定點邏輯與 HUD 則完全沒有來源。建議把模擬器中所有 X1 專屬參數明確標記為「暫定值，待實測」，並在取得實機數據前，以有實測係數的 BlueROV2 Heavy 作為物理正確性的回歸基準：先證明引擎能重現一台已知載具的極速、滑行與纜線力占比，再把 X1 的量測值填進同一套模型。另外兩項值得主動取得的非公開資料是 IMCA R 028 的 Class-A 模擬器準則與 QYSEA 的 X1 手冊，它們分別決定訓練用途的對標方向與 X1 專屬層的正確性。
