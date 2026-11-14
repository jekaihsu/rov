# 成就本地化草案（15 項）

唯一事件／API 來源為 [achievements.json](../../simulator/desktop/steam/achievements.json)。本文件不改原檔 `event`、`api` 或 `name`；以下為顯示名稱與描述提案，供產品審核後填入 Steam 後台。RELEASE 明確說明事件尚未接入遊玩，不能將本表當作已實作觸發規格。

## 本地化文字

| event | api（必須原樣保留） | 繁中名稱 | 繁中描述 | 简中名称 | 简中描述 | English name | English description |
|---|---|---|---|---|---|---|---|
| first_dive | ACH_FIRST_DIVE | 第一次下潛 | 完成第一次下潛。 | 第一次下潜 | 完成第一次下潜。 | First Dive | Complete your first dive. |
| inspection | ACH_INSPECTION | 目標已確認 | 首次完成巡檢任務。 | 目标已确认 | 首次完成巡检任务。 | Inspection Complete | Complete your first inspection mission. |
| recovery | ACH_RECOVERY | 帶回成果 | 首次完成回收作業。 | 带回成果 | 首次完成回收作业。 | Brought Back | Complete your first recovery operation. |
| deployment | ACH_DEPLOYMENT | 安放到位 | 首次完成部署作業。 | 安放到位 | 首次完成部署作业。 | Set in Place | Complete your first deployment operation. |
| scenario | ACH_SCENARIO | 初次結訓 | 首次完成場景訓練。 | 初次结训 | 首次完成场景训练。 | First Exercise | Complete your first training scenario. |
| zero_collision | ACH_ZERO_COLLISION | 完好航跡 | 在零碰撞的情況下完成一次任務。 | 完好航迹 | 在零碰撞的情况下完成一次任务。 | A Clean Run | Complete a mission without a collision. |
| guide_fish | ACH_GUIDE_FISH | 魚群留影 | 在圖鑑中記錄第一筆魚類觀察。 | 鱼群留影 | 在图鉴中记录第一条鱼类观察。 | Fish in Focus | Record your first fish observation in the field guide. |
| guide_coral | ACH_GUIDE_CORAL | 礁間色彩 | 在圖鑑中記錄第一筆珊瑚觀察。 | 礁间色彩 | 在图鉴中记录第一条珊瑚观察。 | Reef Colors | Record your first coral observation in the field guide. |
| guide_seagrass | ACH_GUIDE_SEAGRASS | 水下草原 | 在圖鑑中記錄第一筆海草觀察。 | 水下草原 | 在图鉴中记录第一条海草观察。 | Underwater Meadows | Record your first seagrass observation in the field guide. |
| guide_structure | ACH_GUIDE_STRUCTURE | 水下結構 | 在圖鑑中記錄第一筆結構觀察。 | 水下结构 | 在图鉴中记录第一条结构观察。 | Beneath the Structure | Record your first structure observation in the field guide. |
| guide_other | ACH_GUIDE_OTHER | 另一種發現 | 在圖鑑中記錄第一筆「其他」類觀察。 | 另一种发现 | 在图鉴中记录第一条“其他”类观察。 | Another Discovery | Record your first observation in the field guide's Other category. |
| guide_complete | ACH_GUIDE_COMPLETE | 五類見聞 | 在圖鑑的五個類別中各記錄至少一筆觀察。 | 五类见闻 | 在图鉴的五个类别中各记录至少一条观察。 | Five Ways to Discover | Record at least one observation in each of the five field-guide categories. |
| three_pilots | ACH_THREE_PILOTS | 三人同潛 | 與另外兩位駕駛一同參與協作任務。 | 三人同潜 | 与另外两位驾驶员一同参与协作任务。 | Three Pilots, One Dive | Take part in a cooperative mission with two other pilots. |
| untangled | ACH_UNTANGLED | 重獲通路 | 成功解除一次纜線纏繞。 | 重获通路 | 成功解除一次缆线缠绕。 | Clear of the Snag | Successfully free a tangled tether. |
| first_photo | ACH_FIRST_PHOTO | 第一張水下照 | 拍攝並保存第一張水下照片。 | 第一张水下照 | 拍摄并保存第一张水下照片。 | First Underwater Photo | Take and save your first underwater photo. |

## 事件契約待確認事項

上表不增加深度、時限、碰撞距離或物種數等未定門檻。工程接線前由產品與程式共同確認以下語意，再回頭修訂三語描述：

- `first_dive`：以遊戲正式認定的下潛完成為準；是否入水即成立需決定，不自行加入某個深度或強制回航。
- `inspection`、`recovery`、`deployment`、`scenario`：使用對應任務／作業成功事件；開始、取消與失敗均不可當完成。
- `zero_collision`：定義哪些任務可計入、起訖區間，以及碰撞計數是否只含載具或含纜線；不能把自由探索離開當零碰撞完成。
- `guide_*` 五類：以成功寫入圖鑑的類別為準，僅按快門不等於記錄；`guide_complete` 是五類各一筆，不是收齊所有物種。最終分類若變動先審查，API 不改名。
- `three_pilots`：建議以同一協作任務有三位實際玩家參與為準，不以三台本機模擬載具、三個旁觀者或歷史累計三人替代；「參與」的有效條件待接線確認。
- `untangled`：須先有有效纏繞，再以操作解除；重置房間、斷纜或重新載入不算。
- `first_photo`：確認「保存」指遊戲成功寫入本地收藏；取消或保存失敗不算。

RELEASE 指定每個事件的 stat 名為 `STAT_` 加大寫 event，INT、default 0、client-set、increment-only。`steamEvent(event, integerValue)` 的值與各解鎖門檻仍需實作方確認，本文件不另發明累計演算法。

完成後用測試帳號逐項驗證觸發／不觸發、重啟不重複解鎖、離線後重連、三語後台顯示與五類集齊；多人事件需真實跨機測試。解鎖圖示採原創海事符號（燈、鏡頭、無品牌纜線、魚／珊瑚／海草等），不要用現實載具輪廓。隱藏狀態暫建議全部公開，以幫助玩家理解目標；後台設定另審核。
