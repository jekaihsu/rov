# ROV 操作員訓練「講評／回放」研究筆記

閱讀標記：Fetched = 讀過原文；Snippet = 搜尋摘要，未全文核對；推算 = 依公開資料推論。日期基準：2026-11。

## 1. 講評要解決什麼

公司用途之一是操作員教育訓練。教官已能注入故障並看即時考核，但訓練後缺少「講評」：一起回看學員操作，在關鍵時刻停下來討論。商業模擬器把這段稱為 record / playback / post-simulation analysis；軍事與民航訓練則對應 after-action review（AAR）。

對本專案的含義〔推算〕：講評不是多一種遊戲視角，而是教官工具——要能停在關鍵事件、對照學員當下看到的受限畫面與真實世界，並留下可存檔的分數與註記。

## 2. 業界考核與講評內容

### IMCA 架構（能力證據，不是一次性考試）

- IMCA C 005（Remote Systems & ROV）把能力保證／考核定義為：對照職等能力表蒐集表現、知識與態度證據，並由具備資格的評估者判定。模擬器時數與離岸時數的換算需特別記錄；C 005 指出模擬器經驗與離岸經驗的價值關係複雜，應分開登錄（Fetched PDF 摘要）— [IMCA C 005 鏡像](https://www.lerus.com/_files/IMCAC005.pdf)、[IMCA C 005 頁](https://www.imca-int.com/resources/technical-library/document/3907f45c-c55b-ee11-8def-6045bdd2c7e3/)。
- IMCA C 014《Guidance on the use of simulators》為 ROV 模擬器訓練／定期演練提供評估範本，並補上副駕駛／觀察員準則（Snippet）— [Offshore Mag OTC 2015](https://www.offshore-mag.com/subsea/article/16767652/otc-2015-marine-contractors-issues-simulator-use-guide)、[IMCA C 014](https://www.imca-int.com/resources/technical-library/document/467e185d-c55b-ee11-8def-6045bdf1e8a2/)。
- 2025 年 IMCA 發布 R 028（Class-A ROV 模擬器認證）與 G 014（模擬器系統核可臨時方案）；入門課若以虛擬環境交付需 Class-A（Fetched）— [IMCA 新聞 2025-06-10](https://www.imca-int.com/news-events/imca-news/news/imca-publishes-new-guidance-for-rov-simulator-approval/)。R 028 技術細節仍會員限定。

講評／報告宜對齊的證據欄位〔推算〕：飛行時數、任務完成、環境條件、故障注入與反應、航線／深度／航向誤差、纜線張力與勾纏、碰撞、控制平順度、評估者文字註記。不宣稱 IMCA 等效。

### TRANSoM 評分與「示範 → 練習 → 回顧」

- 五階段（descent / transit / hover / orbit / dock）× 六技能（Stay On Course、Steady Progress、Drive Smoothly、Face the Target、Avoid Collisions、Snapshots）；綠／黃／紅。
- 指標：path、bearing、depth、hover、range、speed、control smoothness（推力變異、過零、反向），至少 1 Hz 取樣，RMS／min／max／超限時間比。
- 課程流程含 replay、與專家航跡比對、對出錯區段重飛（Fetched PDF）— [Fletcher & Roberts, I/ITSEC 1998](https://xcdacademy.s3.amazonaws.com/iitsec/1998/72757R4N63405774.pdf)。

### 廠商課程常見評分／練習項

- VideoRay：Hold Station、Follow Tether、Managing Tether；能力表分知識（組件、軟體、規劃、資料、診斷）與技能（電腦、戰術、維護）；日誌分欄 Pilot／Tether Handler／Accessory／Maintenance／Supervision（Fetched）— [VideoRay competencies](https://download.videoray.com/documentation/vtl/html/competencies.html)、[Hold Station](https://download.videoray.com/training/vtl_pro_5_exercises_manual_control/html/_hold_station_narration.html)。
- Fugro DeepWorks：任務時間、控制平順度、偏離規劃航線、纜線受力與放纜；教官可暫時「弄壞」電路／元件考故障反應（Fetched）— [Engineer Live / DeepWorks](https://engineerlive.com/24793/)。
- Forum VMAX 標準情境庫：纜線管理、進入評估、機械手控制（Snippet）— [Forum VMAX](https://f-e-t.com/?p=2974)。

## 3. 模擬器廠商的講評／回放功能

| 產品 | 講評相關能力（公開描述） | 來源 |
|---|---|---|
| Forum / VMAX | 完整 3D 場景錄製；VMAX Player 可回放；可切 ROV 攝影機與自由視角（含學員當下未用的視角）做事後分析 | Fetched — [World Oil 2019](https://www.worldoil.com/magazine/2019/december-2019/features/simulated-training-for-next-gen-electric-rovs-and-drivers)、[VMAX Player](https://www.vmaxsimulation.com/product-page/subsea-engineering-training) |
| Fugro DeepWorks | 訓練／任務預演的 3D 圖形錄製；客觀績效指標；故障注入後看學員判斷是否中止任務 | Fetched — [Engineer Live](https://engineerlive.com/24793/) |
| GRi VROV | 教官觸發故障、訓練目標疊圖；公開頁未明確寫「回放講評」，但定位為 stick-time 與程序驗證工具 | Fetched — [GRi VROV](https://grisim.com/products/vrov-virtual-remotely-operated-vehicle/)、[True North Map](https://truenorthmap.ca/capabilities/gri-vrov-training-and-mission-rehearsal) |

共同模式〔推算〕：

1. **時間軸回放**：整場可拖曳、可停。
2. **雙視角**：學員機載畫面 vs 自由／上帝視角（看出勾纜、碰撞前路徑、洋流）。
3. **事件錨點**：故障注入、碰撞、纜線異常、感測器失效、任務節點。
4. **客觀指標 + 教官註記**：分數矩陣與文字講評一併匯出。

## 4. 本專案講評應標出的事件

對照真實作業風險（IMCA SF 02/23 導管架受困、VideoRay 勾纏程序、揚沙／DVL／通訊研究筆記）與既有教官注入／考核欄位，講評時間軸至少標：

| 事件 | 訓練意義 | 資料來源（本模擬器） |
|---|---|---|
| 教官注入 | 考故障察覺與反應時間 | `instructor.events`／錄製 `debrief.events` |
| 碰撞 | Avoid Collisions；扣分 | `state.events`（ContactEvent） |
| 纜線警示／勾纏／斷纜 | 纜線管理核心技能 | `tether.warn`／`wraps`／`broken` |
| 揚沙全白 | 低能見度空間感 | `silt` 高值／`turbidity` |
| DVL 失鎖 | 定點／導航依賴 | `sensors.dvl.status == lost` |
| 通訊中斷 | 失聯保護與重連紀律 | `link.state == lost` |
| 任務目標完成 | 進度節點 | `score.objectives[].done` 上升沿 |
| 考核扣分點 | 講評討論焦點 | `score.penalties` |

點事件應跳到該時刻前約 5 秒，讓教官有時間講「發生前學員在做什麼」（與 TRANSoM「回顧出錯區段」一致）。

## 5. 講評視角（非擬真項目）

- **學員視角**：機載畫面 + 當時影像延遲與感測器讀值（不是真值）。對齊真實駕駛資訊受限。
- **上帝視角**：真實位置、真實纜線形狀、真實洋流、感測器誤差對照。對齊 VMAX「自由攝影機／事後分析視角」。
- 必須清楚標示「講評視角，非學員畫面」，且不計入擬真項目（見 AGENTS.md 擬真設定）。

## 6. 講評報告建議欄位

單頁 HTML／列印 PDF：

1. 學員／載具／情境／時長／暫定總評（綠黃紅矩陣摘要）
2. 事件清單（時間、種類、簡述）
3. 關鍵時刻截圖（時間軸錨點）
4. 教官文字註記
5. 聲明：門檻暫定、非 IMCA 認證

文字集中 STRINGS；匯出不得寫入教官碼。

## 7. 對實作的約束（摘自任務）

- 優先沿用 `qysim-replay-*` 錄製格式；不足處以選填欄位擴充，舊檔照常回放。
- `app.js` 只留最小 import／呼叫。
- 回放不得送出 RC；不得破壞輸入心跳在回放時停止重送的規定。

## 8. Gaps

- IMCA R 028 Class-A 技術準則、C 005 完整能力表數字門檻：會員限定，未取得。
- GRi 知識庫舊文（Kayako）404；其回放／講評細節未從一手文件確認。
- 未找到公開的「標準講評檢查表」PDF；上表為多家產品與 TRANSoM／IMCA 公開描述的綜合〔推算〕。
