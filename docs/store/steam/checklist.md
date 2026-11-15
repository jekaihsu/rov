# ROV Solution｜Steam 上架前檢查清單

2026-11-15；文件準備不代表完成後台設定或發行驗收。每個空框由負責人補上 build／日期／證據連結後才能勾；本任務不操作 Steamworks 發布、不改遊戲程式。基底：`138c242effe2867e49f77cc083aade6d0d2ff9e4`。

## 文件、內容與發行門檻

- [ ] 補讀目前 main 缺少的 `docs/design/key-art/README.md`、`docs/design/palette-631/README.md`，核對 [assets.md](assets.md) 所有暫行構圖、YX／機型符號與配色；不得以本稿當原規格。
- [ ] [game-plan](../../design/game-plan.md) 全文為範圍依據；首版為序章＋第一章港口與船舶＋第二章養殖場、約 10 關。逐關記錄開始、目標、交付、評分、重試、解鎖、存檔讀回與四語字幕；不得用後續章節代替首版完成數。
- [ ] [page.md](page.md) 四語逐段人工校對，短說明 <300 字元，名稱統一 ROV Solution、公司與虛構發照機構 YX。機型僅使用核准對外名稱，非內部 key；不宣稱職業認證或完整真機校準。
- [ ] 開賣前把 Coming Soon／規劃語氣與 EA「目前狀態」更新為實際版本；沒有驗收的賣點四語同步刪除。QA、截圖、影片與可下載 build 一致。
- [ ] [RELEASE](../../../simulator/desktop/steam/RELEASE.md) 仍記載 Steam edition 阻擋：內訓品牌模型與文字、USB 匯入依賴邊界、Steam 包白名單待核；必須由發行工程另行解除。存在 Windows 內訓產物不等於可上架。
- [ ] 最低／建議系統需求以最終包實測，保留 CPU／GPU／驅動、記憶體、實際渲染比例、FPS、安裝大小與物理計時；[舊推估](../positioning-and-requirements.md) 不能直接發布成保證。
- [ ] 全部圖片與影片來自實際遊戲，無現場照片、插畫或合成玩法。至少 8 張正式截圖（本包規劃 10 張），其中至少 4 張核對為適合所有年齡；Steam 最低需求 5 張不替代本任務交付數。

## Steamworks 設定

官方：[Release Process](https://partner.steamgames.com/doc/store/releasing)、[Review Process](https://partner.steamgames.com/doc/store/review_process)、[Coming Soon](https://partner.steamgames.com/doc/store/coming_soon)、[Early Access](https://partner.steamgames.com/doc/store/earlyaccess)、[Localization](https://partner.steamgames.com/doc/store/localization)。

- [ ] 確認合作夥伴法律實體、稅務、銀行、Steam Direct 費用、權限與真實 AppID／DepotID；名稱、開發商、發行商、客服連結由擁有者核定。
- [ ] 建立 Windows package／depot、執行檔與 launch option；其他平台不勾，直到有實際對應包與驗收。年齡、語言、EA、類型、功能及商店四語欄位逐一完成。
- [ ] 優先標籤建議：Simulation、Realistic、Physics、Underwater、First-Person、Singleplayer；以後台現有標籤與實際內容確認。不要先勾多人、VR、Workshop 或專業認證類宣稱。
- [ ] 四語介面、字幕、完整音訊分欄驗證；AI 無線電部分配音不等於 Full Audio。確認日文／繁簡中文字型、換行、數值單位和控制器提示。
- [ ] 開啟 EA 設定、填六問、校對期間與價格答覆；不承諾固定完成日或未交付功能。[page.md](page.md) 已提供無可靠工期時的透明答覆。
- [ ] 使用 `simulator/desktop/steam/app_build.vdf.example`、`depot_build.vdf.example` 與 `generate_vdf.cjs` 規劃上傳。現有 `Preview=1` 只是預覽；核對 ContentRoot、實際 exe、depot 範圍與測試分支後才由擁有者上傳，不對 default 分支盲目設 live。
- [ ] 真實 ID 由外部環境注入；不提交憑證或 `steam_appid.txt` 到發行包。Steam 啟動／無 Steam 回退／離線／Overlay 返回／後端崩潰重試均實測。
- [ ] 商店與 build 分別送審、確認兩邊完成；預留退件修正時間。核對 Steam Direct 支付後等待期及 Coming Soon 最低公開期（官方一般為 30 天與至少兩週；以帳戶當前解鎖條件為準），不把審查時間當發售日期保證。
- [ ] 預覽四語、圖片裁切、影片、購買 package 與區域價格；保存、發布商店變更後再外部檢查。公開 Coming Soon 與正式 Release 為兩次不同動作。

## 年齡分級、成人內容及 AI 問卷

官方：[Content Survey](https://partner.steamgames.com/doc/gettingstarted/contentsurvey)、[德國分級](https://partner.steamgames.com/doc/gettingstarted/contentsurvey/germany)。

- [ ] 完成 General Content、Mature Content、Generative AI 三部分；需盤點整個上傳 build，含玩家尚不能進入的內容，不只看商店展示。
- [ ] 逐項檢查設備事故、作業壓力、死魚回收、動物屍體細節、粗口、暴力、恐懼、酒精／藥物、性與裸露、賭博、購買功能；沒有證據不推定全為「無」。設計中的搜救改為證物／假人，不等於最終所有資產已符合。
- [ ] 使用 page.md 四語成人揭露候選文字，刪除編輯指示並按最終內容修正。各區域問卷結果／已有官方證書分開處理，不自行宣稱特定級別；確認目標銷售區包括德國的分級可見性要求。
- [ ] AI 無線電必揭露。核定供應商、聲音權利、是否離線預先合成；預先產生隨包發行填 Pre-Generated。若任何執行時生成，填 Live-Generated，說明輸入範圍、違法內容防護、費用／連線需求與實測，不直接填無。
- [ ] 逐檔盤點遊戲內文本、翻譯、貼圖、模型、圖像、音樂、聲音的 AI 來源。另記本包商店文字及翻譯為 AI 輔助草稿；未盤點不寫「只有語音使用 AI」。辨識式 AI／程序物理不是自動等於生成式 AI。
- [ ] 保存授權、合成紀錄與人工審稿；本包沒有生成圖片。截圖內若有生成式素材，仍計入來源清冊。最終提交文字必須具體，不能保留待查證欄位。

## 輔助功能問卷

依 [Accessibility Features](https://partner.steamgames.com/doc/accessibility_features)（本次讀取官方正文），在 Basic Info 的 Accessibility Feature Wizard 填寫。下表全為待測，不是已勾選承諾。

| 官方功能 | 驗收方法／標示限制 |
|---|---|
| Adjustable Difficulty | 確認可選輔助對一般任務有效且可理解；考照強制 real 的例外要清楚，不為勾選而改物理 |
| Save Anytime | 手動與自動存檔、任務中斷後還原實測；只保存偏好／照片或結算不算隨時存檔 |
| Custom Volume Controls | 分別靜音語音、音樂、音效、環境並重啟確認；單一主音量不足 |
| Narrated Game Menus | 盲操作完成全部選單；無線電配音不算選單朗讀 |
| Stereo Sound／Surround Sound | 分別驗證聲源定位與聲道；不能因有音訊就勾環繞 |
| Adjustable Text Size | HUD、選單、字幕均可讀且無裁切；Electron zoom 不自動等於完整文字大小支援 |
| Subtitle Options | 所有口語與必要聲音資訊具字幕及可用顯示選項；測 AI 無線電說話者與換行 |
| Color Alternatives | 告警除顏色外還有形狀／文字，或可調區別色；不只全畫面濾鏡 |
| Contrast Controls | 真正可調文字／背景對比並涵蓋操作資訊 |
| Camera Comfort | 關閉或調整晃動、模糊等不適效果；檢查所有視角 |
| Playable without Vision | 整個遊戲可不看螢幕才勾；目前無此完成證據，不宣稱 |
| Keyboard Only／Mouse Only／Touch Only | 各自單獨從首次啟動到退出與完整任務可玩；鍵鼠合用不能同時勾三項 |
| Playable without Quick Time Events | 確認全部任務不存在精準限時按鍵，或可關／跳過 |
| Playable at Your Own Pace | 即時洋流、考核與事故處理可能仍要求反應；有暫停不自動合格，逐情境驗證 |
| Chat Text-to-speech／Chat Speech-to-text | 若沒有交付聊天功能或轉換能力，不勾；NPC 無線電字幕不等於語音聊天轉錄 |

- [ ] 填寫人逐項附 build 與操作證據；四語功能覆蓋不一致先修正或降低宣稱，不用設計目標代替可用功能。

## 手把支援標示

依 [Steam Input](https://partner.steamgames.com/doc/features/steam_controller)、[Getting Started](https://partner.steamgames.com/doc/features/steam_controller/getting_started_for_devs) 及 [專案 Steam Input](../../steam/steam-input.md)。

- [ ] 現有 `game_actions_TEMPLATE.vdf` 有 Flight／Menu 與英繁文字；補驗簡中／日文、每裝置實際映射，不把模板等同已發布推薦設定。
- [ ] 實體 Xbox、PlayStation、Switch Pro、Steam Deck 各測：首次啟動、選單、對話、檢查清單、航行、工具、拍照、講評、存讀檔、設定、退出。記錄有無鍵鼠需求。
- [ ] 檢查 `navigator.getGamepads()` standard mapping、軸 0–3、按鍵 0–16、死區／反轉、重新連接、正確 glyph；Steam Input 推薦設定需實機匯出與發布。
- [ ] Overlay／失焦期間不殘留輸入，返回可恢復；RELEASE 的 `overlayActive=null` 是偵測未支援，不是已證明關閉。其他快捷鍵開 Overlay 的缺口要實測。
- [ ] 完整支援只能在不需鍵鼠即可使用全功能、文字輸入與裝置提示符合要求後標示；若只部分功能需鍵鼠，按實測填部分支援及限制。**未測不標完整，也不自行把部分當保證。**

## Steam Deck 相容性自評

依 [Compatibility Review](https://partner.steamgames.com/doc/steamdeck/compat)；自評不是 Valve 的 Verified／Playable 標章。現況 **未驗證**；偵測 Deck 後設 1280×800 不代表可玩。

- [ ] 測 Windows 完整包在 Proton 冷啟動、Steamworks native binding、WebGL／字型、後端埠、離線；沒有 Linux 原生包不勾 Linux。
- [ ] 預設設定 1280×800／720、可玩幀率：官方 Deck 目標 800p 30 fps；記錄實測平均、低幀、長纜／粒子壓力、JIT 載入及長時穩定，不能以輸出解析度掩蓋內部縮放。
- [ ] 全流程手把可達、正確 glyph、必要輸入自動叫出螢幕鍵盤、無不相容硬體警告／需滑鼠啟動器。
- [ ] 800p 四語字幕、HUD 與數字可辨；查閱當期官方字級／解析度標準，全部畫面核對而非只主選單。
- [ ] 休眠／喚醒、掉線、離線存檔、Cloud 衝突、Overlay 及反覆退出重啟；核對進度不丟失、輸入不殘留。
- [ ] 保存結果：硬體、SteamOS、Proton、build、設定、失敗步驟。由擁有者申請 Valve 審查；商店不自行畫 Deck Verified 徽章。

## 成就

依 [Stats and Achievements](https://partner.steamgames.com/doc/features/achievements)、[achievements.json](../../../simulator/desktop/steam/achievements.json)、[既有本地化](../achievements.md)。

- [ ] 15 個 event／API 名逐一對照，不改唯一目錄。現有 RELEASE 記載未接線／未驗證真 Steam 解鎖；送審前追蹤最新實作證據。
- [ ] 後台 stat 依 RELEASE 使用 `STAT_`＋大寫 event、INT、default 0、client-set、increment-only；門檻與完成語意由工程核定，不把任意上報值當成功。
- [ ] 補齊四語名稱、描述（舊表缺日文）；逐項觸發與反例驗證，取消／失敗不解鎖、重啟不重複、離線再同步、不同帳號不串檔。
- [ ] `three_pilots` 等首版不保證可達項目由產品決定延後／隱藏或調整發布成就集合，不能發布玩家永久無法完成的清單；本文件不改 API。
- [ ] 每項提供解鎖／未解鎖圖示，按後台要求與官方文件確認尺寸（常用 256×256，當期後台要求未查證）；仍從遊戲內實際圖示擷取，不用現場照片。通過後才勾 Steam Achievements。

## 雲端存檔

依 [Steam Cloud](https://partner.steamgames.com/doc/features/cloud) 與 RELEASE；現有 Auto-Cloud 規格只是候選配置。

- [ ] 以 `steamStatus().cloudPath` 驗證真實 Electron userData；候選 WinAppData／`ROV Simulator`，不能只因遊戲改名就改雲端路徑。新舊名稱遷移另驗證。
- [ ] 原候選包含 `preferences.json`、`window.json`、`collection/**`，排除 logs、numba-cache、`local-backups/**`；**另查職涯／執照／經濟／章節進度真正存放位置**，不把照片同步當完整進度同步。
- [ ] 設定各 Steam 帳號根目錄隔離／override，雙帳號、雙機、不同解析度往返測試；決定 window.json 是否應跨機同步，防止視窗位置失效。
- [ ] 1 GiB／10,000 檔案是 RELEASE 的初始預算，不是已保證容量；以實際照片大小、長期存檔與後台 quota 驗證，超限處理尚待完成。
- [ ] 測離線分歧、衝突選擇、覆寫、刪除、配額滿、重裝與舊檔升級；本機 snapshot 只能保存啟動時仍在的資料，不能保證追回已被雲端覆蓋的檔案。
- [ ] 手動匯出／匯入與本機備份恢復實測，回報限制；通過真 Steam 雙機同步後才勾 Steam Cloud。

## 定價與區域定價建議

查價：2026-11-15 UTC，Steam 公開 appdetails，`cc=us&l=english`，USD；下列皆本體，未折扣價／當日價分列。API 是讀取當下的商店資料，不是銷量或付費意願證明。

| 參照作品 | USD 原價／當日價 | 定位與來源 |
|---|---|---|
| [subROV: Underwater Discoveries](https://store.steampowered.com/app/1648760/) | 19.99／19.99，折扣 0% | 直接 ROV 模擬參照；[本次價格 API](https://store.steampowered.com/api/appdetails?appids=1648760&cc=us&l=english) |
| [vROVpilot: TITANIC](https://store.steampowered.com/app/3397800/) | 24.99／24.99，折扣 0% | 直接 ROV／沉船觀測參照；[價格 API](https://store.steampowered.com/api/appdetails?appids=3397800&cc=us&l=english) |
| [Deep Diving Simulator](https://store.steampowered.com/app/990030/) | 19.99／19.99，折扣 0% | 鄰近潛水題材，非同等擬真對標；[價格 API](https://store.steampowered.com/api/appdetails?appids=990030&cc=us&l=english) |
| [Beyond Blue](https://store.steampowered.com/app/883360/) | 19.99／19.99，折扣 0% | 海洋探索題材，非 ROV 操控競品；[價格 API](https://store.steampowered.com/api/appdetails?appids=883360&cc=us&l=english) |

建議 EA 基價 **US$17.99**，評估區間 **US$14.99–19.99**（提案，非既定價格）。約 10 關的量不能直接換成遊玩時數；以教學完成率、重玩價值、手把／儲存穩定性與試玩願付價決定。若首版內容與品質驗收不足，延後售賣，不用高擬真口號補足價值。正式版是否漲價留待新增內容與擁有者決策；page.md 不承諾價差。

區域定價依 [Steam Pricing](https://partner.steamgames.com/doc/store/pricing) 當期工具。官方現列匯率、購買力、多變量三種轉換方法；建議用多變量結果當起點，再人工檢查當地同類本體價格。這不是所有市場固定匯率換算。

| 市場 | 建議處理 | 本次可用數字 |
|---|---|---|
| 美國 USD | 用 17.99 作草案基準，與直接競品比 | 上表已查價；本作價格未設定 |
| 台灣 TWD | 比較本地 ROV／模擬作品、購買力與可接受尾數；繁中完整度列入考量 | 區域競品價格與 Steam 轉換值：未查證；不捏造 NT$ 建議值 |
| 日本 JPY | 比較同類價位、日文介面／字幕品質與整數尾數 | 區域競品價格與轉換值：未查證 |
| 中國大陸 CNY | 檢查簡中覆蓋、當地購買力與可用販售區域；全球 Steam 不等於 Steam China 發行 | 區域競品價格與轉換值：未查證 |
| 其他貨幣與 USD 區域群組 | 匯出後台價格表，查遺漏／異常低價、最低售價與稅務後收益 | 當期後台值：未查證，由有權限者確認 |

- [ ] 擁有者確認基價、每區價格與首發折扣；可評估 10% 首發折扣但非必要。送審前重查競品，記錄日期／幣別／本體或 bundle／原價與特價。
- [ ] 查 [Discounting](https://partner.steamgames.com/doc/marketing/discounts) 與 [EA 價格限制](https://partner.steamgames.com/doc/store/earlyaccess)：漲價後 30 天內不能折扣，包含轉正式版首發折扣；不要排互相衝突的漲價與促銷。最終以當期後台規則檢查。

### 研究如何影響本包

[sim_game_patterns](../../../research_notes/遊戲設計/sim_game_patterns.md) 的競品評價多為摘要與二手整理，不能當最新評論全體結論。本包不搬用其好評率、評論數或遊玩時數作行銷數字；這些目前數字 **未查證**。

- [subROV 的 GameLuster 評測](https://gameluster.com/review-subrov-underwater-discoveries-roving-in-the-deep/) 提及控制／節奏問題（依倉庫研究轉述）：本包第一鏡直接做事，第一張圖呈現目標，並要求預潛與教學實測，而非降低物理難度。
- [vROVpilot 商店](https://store.steampowered.com/app/3397800/) 為直接題材參照；研究提到內容量與更新間隔，但本次未重查其評論／公告，不沿用數字或聲稱對方停更。本包清楚列約 10 關與不含後續章節。
- [Deep Diving Simulator 商店評論](https://store.steampowered.com/app/990030/) 與 [GOG 評論](https://www.gog.com/en/game/deep_diving_simulator) 是研究「模擬期待落差」的來源；此為研究摘要，不作本次獨立評論統計。本包具體描述推力、纜線、誤差與程序，避免「百分之百真實」的宣稱。

## 需要擁有者決定或親自操作（集中清單）

以下是具體待辦，不是要求對本文件 PR 再授權；本任務不替擁有者發布 Steam 商店。

1. 提供缺失主視覺與配色文件位置；確認最終 YX／Model R 等符號已在遊戲出現，滿足全實機素材限制。
2. 決定 EA 工期表達、正式版方向、社群管理窗口／實際公告頻率、約 10 關最終名單及首版成就可達範圍。
3. 決定美元基價、所有區域價格、首發折扣及正式版調價政策；有定價權限帳號提交後台價格審核。
4. 核定公司法律名稱、開發商／發行商、客服、商標權利、AI 聲音供應商及生成方式；簽核全部素材授權、成人與 AI 問卷。
5. 親自完成銀行、稅務、協議、AppID／DepotID、付款與帳戶權限；憑證不寫入本倉庫。
6. 指派 Windows、四種實體控制器、Deck／Proton、Steam 雙機 Cloud 與成就測試人員；依結果勾支援，不能由文件作者推定通過。
7. 核定四語人工校稿與實際音訊覆蓋；不因本包有四語文字就勾 Full Audio。
8. 通過驗收後上傳素材與 build、送審、設定 Coming Soon／Release 日期、公開商店與開賣；申請 Valve Deck 相容性審查，確認回傳結果再使用標示。

## 本包的完成界線

四份文件完成不解除 RELEASE 阻擋、不完成後台問卷、不代表正式素材已拍攝。缺失文件、實機證據、素材授權與擁有者決策集中保留在本清單；其餘工作可先進行。程式與既有資產不在本 PR 修改範圍。
