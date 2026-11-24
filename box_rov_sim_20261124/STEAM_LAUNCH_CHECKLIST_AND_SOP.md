# ROV-01 Simulator — Steam (Steamworks / Steam Direct) 上架手續、稅務金流、審查時程與技術打包全指南

> **更新日期**：2026-10-24 (Asia/Taipei, UTC+8)  
> **官方依據**：Valve Steamworks Documentation (`partner.steamgames.com/doc/gettingstarted/onboarding`、`appfee`、`finance/taxfaq`、`contentsurvey`、`store/assets/standard`、`store/assets/libraryassets`、`store/review_process`、`sdk/uploading`)

---

## 一、行政、法務、稅務與外幣金流手續（5 大必備關卡）

### 1. Steamworks Partner 開發者／發行商帳號註冊與電子合約簽署
- **入口**：`https://partner.steamgames.com/`（建議使用專用的公司開發者主 Steam 帳號登入，且該帳號需綁定手機門號與 Steam Mobile Authenticator，否則後續無法將正式 Build 設為 Live）。
- **法定名稱一致鐵律（三合一完全一致）**：
  - 註冊填入的 **Company Legal Name（法定名稱）** 必須與 **① 台灣公司英文登記證明（經濟部國際貿易署出進口廠商英文名稱／公司變更登記表英文譯本）**、**② 台灣銀行外幣帳戶英文戶名**、**③ 美國 IRS 稅務表單（W-8BEN-E）** 字字完全一致（包含標點符號如 `Co., Ltd.`）。
  - **嚴禁填入簡稱、品牌名或 DBA（Doing Business As）**：顯示給玩家看的「開發者／發行商名稱」可在商店頁面單獨設定，但合約簽署主體必須為正式法人或自然人法定全名。
- **公司與個人（Sole Proprietorship）路徑比較**：

| 項目 | 方案 A：以台灣法人名義（永祥／新設主體） | 方案 B：以個人獨資名義（Sole Proprietorship） |
| :--- | :--- | :--- |
| **Company Form 填寫** | `A Taiwan limited company` 或 `A Taiwan corporation` | `A Sole Proprietorship`（法定名稱填護照英文全名） |
| **應備 KYC 文件** | 公司變更登記表、經濟部英文名稱證明、代表人護照／身分證 | 個人護照（Passport）＋英文戶籍謄本或英文銀行對帳單（地址證明） |
| **是否需要 D-U-N-S 鄧白氏環球編碼？** | **Steamworks 官方目前不強制要求 D-U-N-S**（與 Apple App Store 不同），但若銀行或第三方 KYC 抽查公司英文名稱，備有國貿署英文登記或 D-U-N-S 可加速人工覆核 | 不需要 |
| **簽署合約** | 線上電子簽署 **Steamworks NDA（保密協議）** 與 **Steam Distribution Agreement（Steam 發行協議）**（須由具備公司代表權 Actual Authority 之人簽署） | 本人線上電子簽署 NDA 與 Steam 發行協議 |

### 2. Steam Direct 產品申請費（App Credit Fee）
- **金額**：每申請一個新的 `AppID` 需支付 **$100 USD**（依台灣地區匯率折算新台幣，並可能依法加計跨境電子勞務營業稅 VAT/GST）。
- **付款方式**：支援台灣區 Steam 商店接受的信用卡（Visa / MasterCard / JCB），**不可使用 Steam 錢包餘額（Steam Wallet Funds）支付**。
- **退還機制（Recoupable）**：該筆 $100 USD 不可直接退費，但當 `ROV-01 Simulator` 在 Steam 商店累積滿 **$1,000.00 USD 調整後毛收入（Adjusted Gross Revenue）** 後，Valve 會在次月結算報表中以獨立項目將 **$100 USD 全額退還**。
- **發票注意**：Valve 的 $100 USD 收據會開給「刷卡當下登入的個人 Steam 帳號」，無法重開雙重公司抬頭發票；公司入帳通常以員工代墊報支處理。

### 3. 美國 IRS 稅務問卷（Tax Interview by Lilaham / TaxIdentity）
- **表單類型**：
  - **台灣公司法人**：系統引導填寫 **Form W-8BEN-E**（Part I 填入台灣公司英文名稱、註冊地址，Foreign TIN 填入 **台灣公司統一編號 8 碼**，實體分類選Active NFFE）。
  - **台灣個人開發者**：系統引導填寫 **Form W-8BEN**（Foreign TIN 填入 **台灣身分證字號**）。
- **美國來源所得預扣稅率（US Withholding Tax Rate）實況核實**：
  - **台灣與美國目前尚未生效正式的全面所得稅租稅協定（No U.S. Income Tax Treaty in force）**（美台快速雙重稅收減免法案雖經推動，但在 IRS W-8 協定稅率表上台灣仍無 0% 權利金減免條款）。
  - 因此：
    - **美國境內玩家購買（U.S.-Sourced Royalty Income）**：依法由 Valve 代扣 **30% 美國來源預扣稅（Statutory Withholding）**。可憑 Valve 年度發放的 **Form 1042-S** 洽台灣會計師評估境外所得稅額扣抵。
    - **美國以外全球玩家購買（台灣、日本、歐洲、東南亞等 Non-U.S. Sales）**：**0% 美國預扣稅**（不扣 30%）。
  - **Steam 平台分成**：基礎分成 Valve 抽 **30%**、開發者實拿 **70%**（扣除退款、各國 VAT 與美國玩家部分的預扣稅後按月電匯）。
- **審核時間**：第三方稅務驗證通常需 **2～7 個工作天**（官方上限最長可達 30 天，若 TIN 驗證卡住會收到補件信）。注意：稅務問卷必須一次填完，不可中途存檔。

### 4. 台灣銀行美元外幣帳戶設定（Bank Account Setup）
- **帳戶要求**：必須為台灣本地銀行的 **外幣（美元 USD）活期存款帳戶**。
- **必填欄位**：
  - **Account Holder Name（受款人英文戶名）**：必須與 Steamworks 的 `Company Legal Name` **100% 相同**。
  - **SWIFT / BIC Code**（8 或 11 碼國際銀行代碼）與銀行英文名稱、分行英文地址。
  - **Bank Account Number**（外幣帳號，勿含破折號 `-`）。
- **結算門檻**：每月月底結算，次月 **30 日前** 以美元國際電匯（SWIFT Wire Transfer）撥款（預設最低匯款門檻可設定為 $100 USD 以上，以避免中轉行手續費吃掉小額營收）。

### 5. 兩大強制冷卻期與雙軌審核時程（決定最快上市日的硬限制！）
這是排定上市日時最關鍵的 **4 個時間閘門**：
1. **新帳號首款產品 21 天等待期（App Fee Waiting Period）**：自刷卡付完 $100 USD Steam Direct 費用起算，必須滿 **21 天**（舊制為 30 天，現行官方 Onboarding 文件明訂為 21 天；但若加計稅務／銀行驗證最長可達 30 天）才可點擊正式發行。
2. **商店頁面「即將推出（Coming Soon）」強制公開滿 14 天**：商店頁面通過審核並公開掛出「Coming Soon（可加入願望清單 Wishlist）」後，必須在公開狀態維持 **至少 14 天（2 週）**，系統才會解鎖最終「Release（正式發售）」按鈕。
3. **商店頁面審核（Store Presence Review）**：提交後約 **3～5 個工作天**（官方建議預留 **7 個工作天**）。
4. **遊戲主程式審核（Product Build Review）**：上傳完整可執行版本後提交，約 **3～5 個工作天**（官方建議預留 **7 個工作天**）。一旦首次審核通過（Review once; Update any time），後續透過 SteamPipe 推送更新（Patch）即可秒級上線，無須再次排隊人工審核！

> **最快上市時程公式（Critical Path）**：
> - **Day 1**：完成 Steamworks 註冊、刷卡付 $100 USD、完成 W-8BEN-E 與外幣帳戶設定（啟動 21 天倒數）。
> - **Day 2–3**：上傳所有商店膠囊圖、5+ 張純實機截圖、填妥內容與 AI 問卷，提交 **Store Page Review**。
> - **Day 7–8**：商店頁面審核通過，立即發布為 **「Coming Soon（即將推出）」**（啟動 14 天公開倒數，與 21 天等待期重疊計算！）。
> - **Day 10–12**：用 `steamcmd` 上傳 Win64 正式打包至 `default` 分支，提交 **Product Build Review**。
> - **Day 17–19**：Build Review 通過，取得 `Ready for release` 綠燈。
> - **Day 22**：21 天等待期與 14 天 Coming Soon 期雙雙屆滿，隨時可按下 **Release App** 正式開賣！

---

## 二、2026 Valve AI 內容揭露政策與 IP／商標合規（Content Survey & Brand Gate）

### 1. 2026 年 1 月更新版 Valve 生成式 AI 揭露規則（Generative AI Content Survey）
Valve 在 `partner.steamgames.com/doc/gettingstarted/contentsurvey` 第 3 節將 AI 使用明確區分為三類：
- **開發效率與輔助工具（AI-Powered Developer Tools — 免揭露）**：開發過程中使用 AI 輔助撰寫程式碼（如 Cursor / Copilot）、重構或測試，**不屬於玩家消費的生成內容，官方明訂無須在商店頁面揭露**。
- **預先生成內容（Pre-Generated AI Content — 須填寫說明）**：若出貨給玩家的美術圖、音效、語音或在地化文本含有 AI 預生成素材，須在問卷勾選 `Pre-Generated` 並簡述用途（例如：「部分商店宣傳背景或環境音效輔助生成」），Valve 會比照一般內容審查是否侵害第三方版權。
- **即時生成內容（Live-Generated AI Content — 我們不使用）**：遊戲執行期間即時呼叫外部生成式 AI API 產出內容，須額外審核防違法 Guardrails。**`ROV-01 Simulator` 採用 100% 離線確定性 6DoF 物理引擎與程序化 3D 網格，無任何執行期外部 AI 呼叫，因此 `Live-Generated` 勾選 `No`。**

### 2. 為何我們的 `CORR-ROV-01`（`brand_gate.py` 0 處原廠殘留）是過審關鍵？
Valve 在 Build Review 與《Steam 發行協議》第 5 條嚴格審查 **「是否包含未獲授權的第三方商標、機型名稱或真實硬體廠牌 Logo」**：
- 若遊戲內、HUD、3D 機殼貼圖或程式碼字串殘留任何真實水下無人機大廠名稱或機型代號，極易在人工審核時被要求出具品牌授權書，甚至遭同業發動 DMCA / 商標申訴下架。
- 我們在 Wave 2 完成的 **`CORR-ROV-01` 去品牌化工程**（全自研雙浮筒橘黑防撞籠 `ROV-01` 程序化模型、`ROV01_SIM_SDK_V1.2.1`、正式打包自動剝離相容層，並由 `brand_gate.py` 靜態＋動態雙重掃描 **0 違規**），可直接以 **100% 原創工業模擬器 IP** 安全通過 Valve 審核。

---

## 三、Steam 商店與收藏庫美術素材尺寸規格表（對齊 Valve 最新放大版規格）

> **Valve 美術鐵律**：所有 Capsule 膠囊圖**只能包含遊戲主視覺與清晰可讀的遊戲 Logo（`ROV-01 Simulator`）**，**嚴禁**在膠囊圖上印製「獲獎標章、促銷折數、媒體評語、搶先體驗字樣或大段宣傳標語」。

### A. 商店頁面必備素材（Store Graphical Assets）
| 素材名稱 | 必填 | 像素尺寸 (寬 × 高) | 格式與設計規範重點 |
| :--- | :---: | :--- | :--- |
| **Main Capsule（主膠囊圖）** | 是 | **`1232 × 706 px`** | 首頁大型輪播用；主視覺＋清晰 `ROV-01 Simulator` Logo（Valve 已由舊版 616×353 倍增為 1232×706） |
| **Header Capsule（頂部膠囊圖）** | 是 | **`920 × 430 px`** | 商店頁右上角與推薦區主圖（已由舊版 460×215 倍增為 920×430）；禁止放 Logo 以外的推銷文字 |
| **Small Capsule（小型膠囊圖）** | 是 | **`462 × 174 px`** | 搜尋結果與排行榜清單（系統自動縮出 184×69 與 120×45）；**Logo 必須幾乎填滿畫面以確保縮圖可讀** |
| **Vertical Capsule（直式膠囊圖）** | 是 | **`748 × 896 px`** | 季節特賣與主題頁直立海報 |
| **Screenshots（實機截圖）** | 是 | 至少 **5 張**，**`1920 × 1080 px`** (16:9) | **必須 100% 為實機遊戲畫面（含 HUD）**，不可放概念圖或文字字卡；**至少勾選 4 張為「適合所有年齡（Suitable for all ages）」**，否則首頁滑鼠懸停預覽不會顯示！（我們現有的 `01_mission1`～`05_p260` 實機截圖即可直接升頻／輸出使用） |
| **Trailer（實機預告片）** | 強烈建議 | **`1920 × 1080 px`** (MP4 / H.264, 30/60fps) | 至少 1 支 30～60 秒實機操作短片（展示 6DoF 推進、P260 聲納掃描、船體 UT `<3°` 綠環耦合、T3 斷槳迫降） |
| **Page Background（商店背景）** | 選填 | **`1438 × 810 px`** | 低對比深海環境氛圍圖（不填則系統自動取最後一張截圖模糊處理） |

### B. Steam 收藏庫必備素材（Library Assets）
| 素材名稱 | 必填 | 像素尺寸 (寬 × 高) | 格式與設計規範重點 |
| :--- | :---: | :--- | :--- |
| **Library Capsule（收藏庫直式封套）** | 是 | **`600 × 900 px`** | 玩家收藏庫網格封面（自動生成 300×450 縮圖），須含主視覺與 Logo |
| **Library Header（收藏庫橫幅）** | 是 | **`920 × 430 px`** | 最近遊玩與收藏庫橫幅，可直接沿用 Store Header Capsule (`920×430`) |
| **Library Hero（收藏庫頂部巨幅背景）** | 是 | **`3840 × 1240 px`** | **嚴禁包含任何文字或 Logo！** 中央 `860 × 380 px` 為安全不裁切區（適合放 ROV-01 機體主體） |
| **Library Logo（收藏庫透明 Logo）** | 是 | 寬 **`1280 px`** 及/或 高 **`720 px`** | **透明背景 PNG**，僅含 `ROV-01 Simulator` 標準字與標誌，系統會疊加在 Library Hero 上產生視差滾動 |
| **App Icon（桌面與清單小圖示）** | 是 | **`184 × 184 px`** JPG + Windows `.ico` | 顯示於工作列與 Steam 左側列表 |

---

## 四、技術與 SteamPipe 打包準備現況（已於 Box 建置完成並通過測試）

我們已在 `/workspace/rov_sim/desktop/` 與 `/workspace/rov_sim/box_run/desktop/` 完成 Steamworks SDK 與 SteamPipe 自動化打包骨架，並全數通過單元測試與 `brand_gate.py`：

1. **`desktop/steam_app_id.txt` & `desktop/steam_appid.txt`**：
   - 預設填入 `480`（Valve 官方 `Spacewar` 本地開發測試 AppID），取得正式 AppID 後直接替換該數字即可。
2. **`desktop/steamworks_config/app_build_template.vdf` & `depot_build_win64.vdf`**：
   - 標準 SteamPipe ContentBuilder 腳本，自動映射 `desktop/dist/steam_depot_win64/` 並排除 `.pdb`、`.log`、`steam_appid.txt` 與 `__pycache__`。
   - 一鍵上傳指令：
     ```bash
     steamcmd +login <steam_build_account> +run_app_build /workspace/rov_sim/desktop/steamworks_config/app_build_template.vdf +quit
     ```
3. **`desktop/steamworks_config/steam_input_manifest.vdf`**：
   - 完整定義 Steam Input 原生控制器動作集 `ROVFlightControls`（支援 Steam Deck / Xbox / DualSense 原生按鍵圖示與「完整控制器支援 Full Controller Support」認證標章）：
     - 雙搖桿類比軸：`LeftStick_SurgeSway`（前後推進／左右橫移）、`RightStick_HeaveYaw`（垂直升降／偏航旋轉）
     - 任務與飛控動作：`Surge`、`Sway`、`Heave`、`Yaw`、`Depth_Hold`、`Heading_Hold`、`Emergency_Surface`、`UT_Sample`、`Motor_Arm_Toggle`、`Gain_Cycle`
     - 內建英文（`english`）與繁體中文（`tchinese`）雙語控制器映射名稱。
4. **`desktop/steam_bridge.js`（Steamworks 成就＋Rich Presence＋B2B 雙模無縫降級橋接層）**：
   - 內建 4 項核心訓練考評 Steam 成就：
     - `M1_POOL_CLEAR`（泳池 6DoF 檢定通關）
     - `M2_UT_CERTIFIED`（船體 UT 測厚 `<3°` 3 秒穩定採樣認證）
     - `M3_T3_FAULT_SURVIVOR`（T3 推進器失效 5 槳降級返航成功）
     - `M4_PIPE_GOLD`（海底管線巡檢 85+ 分金牌且零纏繞）
   - 支援 Steam Rich Presence（動態顯示當前任務與水深 `depth_m`），且在無 Steam 環境（B2B 企業單機交付版）自動平滑降級為本地記憶體狀態，絕不崩潰。
5. **一鍵打包腳本 `npm run build:win64-steam`（`desktop/package_steam_depot.js`）**：
   - 自動彙整 `viewer/`、`rov01sim/`、`desktop/` 與 `steamworks_config/` 至 `desktop/dist/steam_depot_win64/`，並**自動剔除 `sdk_vendor_adapter.py`**，確保上架 Steam 的正式二進位包 100% 零第三方廠商字串。
