# D5｜Steam 商店素材與文案規劃

本目錄為編輯／製作草案，不是已發布的商店頁。核對日期：2026-11-14；基準：`origin/main` 的 `afc33198adfec6b34114db0416bf810be98157ff`。只新增文件，不修改遊戲或成就 API。

## X1 商店素材

[全素材聯絡表](steam/assets/contact-sheet.jpg) · [四語商店文案與截圖說明](steam/listing/) · [擷取分鏡與重製指令](../../simulator/tools/store_shots/README.md) · [素材授權](steam/assets/CREDITS.md)

## 交付索引

- [三語商店文案](copy.md)：五個名稱候選、商標檢索建議、賣點、短／完整描述、功能條列。
- [定位、定價與系統需求](positioning-and-requirements.md)：競品、標籤、效能推估與實測門檻。
- [截圖與預告片](capture-plan.md)：八張截圖、80 秒分鏡、拍攝依賴。
- [成就本地化（舊草案）](achievements.md)：早期 15 組文案；**現行規格以 [steam/achievements.md](steam/achievements.md) 為準**（S4，22 項技能成就）。
- [Steam Auto-Cloud](steam/cloud.md)：同步路徑、檔名樣式、配額與 S3 TODO。
- [美術外包需求](art-brief.md)：當前 Steam 尺寸、構圖、交付檔與禁止元素。
- [EULA／隱私權草稿](legal/)：繁中與英文；標明需法務審閱。
- [Steam AI 揭露問卷草稿](steam/ai-disclosure.md)：依 `CREDITS.md` 填寫。

## 編輯與發布條件

文案以「完成驗收後可發布」為用途；不能因為文件列了功能就勾選商店支援項目。`copy.md` 的三語段落語意一致，名稱未定所以不嵌入候選名。其餘文件是內部規劃，不整頁貼到商店。

| 項目 | 依據與現況 | 上線前處理 |
|---|---|---|
| 操控與纜線 | `AGENTS.md`、研究報告：推力控制、纜線施力、有限視野；第三人稱為可關閉輔助 | Steam 包內驗收；不宣稱認證訓練、完全複製某款真機或精確實測數字 |
| HUD／教學 | T04、T16、T12 是製作／驗收依據，不代表全部交付 | 確認全幅視野、一行當前目標、速覽卡與逐步提示；失敗則延後拍攝並刪去相關賣點 |
| 水下畫質／模型 | T07、T11 的效果與原創資產仍須逐項確認 | 發行包通過品牌審查後才拍；不能直接使用內訓版既有載具或已命名沉船作主視覺 |
| 任務／攝影／圖鑑 | `qysim/mission_modes.py`、`scenarios.py`、`expedition.py` 有實作線索 | 實玩確認巡檢、回收、部署、拍照入冊；未通過的功能整段移除，三語同步 |
| 三人協作 | 房間／協作程式存在，非已驗證的 Steam 連線產品 | 跨機連線、加入退出、任務同步與效能通過後，才加入多人賣點和標籤 |
| 成就 | RELEASE 明載事件尚未接線，未驗證 Steam 解鎖 | 本地化僅供審稿；完成事件契約與實機解鎖後才標示 Steam Achievements |
| 平台／手把／雲端 | RELEASE 列出 Windows 發行、實體控制器、離線與雲端衝突等缺口；其他桌面平台未完成 | 不標示全面手把支援、掌機認證或其他作業系統支援；依實測結果更新 |
| 發行阻擋 | RELEASE：品牌資產、文字與依賴邊界仍阻擋 Steam edition | 完成發行內容清單與包內稽核；本 PR 不解除阻擋 |

## 研究轉成素材的決策

研究中對同類遊戲的「到處都是按鈕、前期慢、內容空」批評，轉成三個可檢查的製作要求：第一張圖就看得懂目標；預告片頭 5 秒已有實際觀測行為；前三張圖展示不同活動。新手試玩另記錄首次移動、首次拍照、首次完成目標的時間與卡住原因，不憑剪輯宣稱「三分鐘學會」。靠目標密度與呈現改善節奏，不加速物理、不承諾高速航行。

目前沒有 `docs/reference/own/`，不能補造自有實測。鏡頭距離、剪輯時間、硬體門檻、售價與成就事件的精確判定均為本次製作建議，須以候選發行版驗收；不宣稱已完成商標檢索。

## 來源

- [倉庫規範](../../AGENTS.md)、[ROV 研究（Steam 段落）](../reference/real-rov-research.md#專業模擬器賣的是纜線故障注入與回放steam-上幾乎沒有對手)
- [發布限制](../../simulator/desktop/steam/RELEASE.md)、[成就唯一對照來源](../../simulator/desktop/steam/achievements.json)
- [物理效能](../physics-performance.md)、[目前渲染分級](../../simulator/viewer/render_quality.js)、[介面方向](../design/ui-direction.md)
- [T07 畫質](../tasks/T07-underwater-visuals.md)、[T11 資產](../tasks/T11-realistic-assets.md)、[T12 教學與戰役](../tasks/T12-campaign-and-tutorial.md)

本輪不承諾完整戰役、章節數、遊玩時數、配音、開放世界或所有任務不計時；任務書中的未完章節不當作現有內容。
