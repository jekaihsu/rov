# Steam 成就規格（S4）

唯一事件／API 來源：[`simulator/desktop/steam/achievements.json`](../../../simulator/desktop/steam/achievements.json)。
觸發邏輯為純函式：`simulator/viewer/play/achievements.js`（`node --test simulator/tests/test_achievements.mjs`）。
內部訓練版（`window.rovDesktop.edition !== 'steam'`）不回報、不顯示成就。

沒有 App ID 時，桌面殼把解鎖寫入 `userData/steam-mock/state.json`，可在工程抽屜的 Steam 開發者頁查看。

## 設計原則

- 對應真實作業能力（零接觸、原路解纜、低能見度量測、考照、放纜紀律）。
- 不做刷次數／累計量型成就。
- 不出現廠商或機型名稱；圖示用原創海事符號。

## 圖示規格（美術後續）

| 項目 | 規格 |
|---|---|
| 解鎖／未解鎖 | 各一張，Steamworks 後台常用 **256×256** PNG（送審前再核對當期後台） |
| 風格 | 扁平海事符號（燈、纜線、量尺、聲納扇、獎章輪廓）；深色底、高對比 |
| 禁止 | 真實載具輪廓、廠商標誌、現場照片、可辨識商標 |

## 清單與觸發

| event | api | 繁中名稱 | 觸發條件（純函式） | 隱藏 |
|---|---|---|---|---|
| first_dive | ACH_FIRST_DIVE | 第一次下潛 | 解鎖後深度 ≥ 1 m | 否 |
| harbor_clean | ACH_HARBOR_CLEAN | 零接觸港巡 | 工單 `c1_pier_level1` 完成且 contacts = 0 | 否 |
| murk_measure | ACH_MURK_MEASURE | 濁水量測 | 職涯結算：完成量測交付，且當下能見度 ≤ 1.5 m | 否 |
| tether_retrace | ACH_TETHER_RETRACE | 原路解纜 | `tether_ops.result.correct === true`（先回到卡點再脫開） | 否 |
| chapter1_gold | ACH_CHAPTER1_GOLD | 第一章金牌 | 第一章七張工單皆為金牌 | 否 |
| pool_gold | ACH_POOL_GOLD | 水池金牌 | `p1_pool_checkout` 金牌完成 | 否 |
| open_water_clean | ACH_OPEN_WATER_CLEAN | 開放水域完好 | `p2_open_water` 完成且 contacts = 0 | 否 |
| hull_loto | ACH_HULL_LOTO | 軸系上鎖 | `c1_hull_fouling` 完成（工單本身要求 LOTO） | 否 |
| sonar_find | ACH_SONAR_FIND | 聲納尋物 | `c1_dropped_object` 完成 | 否 |
| cp_survey | ACH_CP_SURVEY | 陰極巡測 | `c1_quay_cp` 完成 | 否 |
| ut_survey | ACH_UT_SURVEY | 測厚到位 | `c1_hull_ut` 完成 | 否 |
| grade2_exam | ACH_GRADE2_EXAM | 二級考照 | `c1_signoff_exam` 考核通過 | 否 |
| real_exam | ACH_REAL_EXAM | 真實模式過關 | 任一考核在真實擬真下通過 | 否 |
| cable_discipline | ACH_CABLE_DISCIPLINE | 放纜紀律 | 結算時 `discipline_score ≥ 90` 且纜線未斷 | 否 |
| zero_collision | ACH_ZERO_COLLISION | 零碰撞完成 | 任一成功結算且 contacts = 0 | 否 |
| prologue_done | ACH_PROLOGUE_DONE | 序章結訓 | `p2_open_water` 完成（見習執照路徑） | 否 |
| untangled | ACH_UNTANGLED | 解開纏繞 | 目標 `untangle` 完成，或 `tether_ops` 脫困結果出現 | 否 |
| inspection_coop | ACH_INSPECTION_COOP | 協作巡檢 | 三人協作巡檢任務成功 | 否 |
| recovery_work | ACH_RECOVERY_WORK | 回收到位 | 探索委託 `recover` 完成 | 否 |
| deployment_work | ACH_DEPLOYMENT_WORK | 部署到位 | 探索委託 `deploy` 完成 | 否 |
| evidence_photo | ACH_EVIDENCE_PHOTO | 現場證據 | 首次成功寫入圖鑑／工程觀察的本機照片 | 否 |
| pier_measure | ACH_PIER_MEASURE | 碼頭量測 | `c1_pier_level2` 完成 | 否 |

## 四語顯示名稱（商店／後台）

| event | zh-Hant | zh-Hans | en | ja |
|---|---|---|---|---|
| first_dive | 第一次下潛 | 第一次下潜 | First Dive | 初めての潜水 |
| harbor_clean | 零接觸港巡 | 零接触港巡 | Clean Harbor Run | 無接触の港湾点検 |
| murk_measure | 濁水量測 | 浊水量测 | Measure in the Murk | 低視程の計測 |
| tether_retrace | 原路解纜 | 原路解缆 | Retrace the Tether | 来た道で解纜 |
| chapter1_gold | 第一章金牌 | 第一章金牌 | Chapter One Gold | 第一章すべて金 |
| pool_gold | 水池金牌 | 水池金牌 | Pool Gold | プールで金 |
| open_water_clean | 開放水域完好 | 开放水域完好 | Clean Open Water | 外洋で無傷 |
| hull_loto | 軸系上鎖 | 轴系上锁 | Locked Out | ロックアウト確認 |
| sonar_find | 聲納尋物 | 声呐寻物 | Sonar Find | ソナーで発見 |
| cp_survey | 陰極巡測 | 阴极巡测 | CP Survey | 陰極防食の計測 |
| ut_survey | 測厚到位 | 测厚到位 | Thickness Done | 板厚計測完了 |
| grade2_exam | 二級考照 | 二级考照 | Grade II Pass | 二級資格 |
| real_exam | 真實模式過關 | 真实模式过关 | Exam in Real Mode | リアル設定で合格 |
| cable_discipline | 放纜紀律 | 放缆纪律 | Cable Discipline | ケーブル規律 |
| zero_collision | 零碰撞完成 | 零碰撞完成 | No Contact Finish | 無衝突で完了 |
| prologue_done | 序章結訓 | 序章结训 | Prologue Complete | 序章修了 |
| untangled | 解開纏繞 | 解开缠绕 | Clear of the Snag | 絡まり解除 |
| inspection_coop | 協作巡檢 | 协作巡检 | Crew Inspection | 協働点検 |
| recovery_work | 回收到位 | 回收到位 | Recovery Complete | 回収完了 |
| deployment_work | 部署到位 | 部署到位 | Set in Place | 設置完了 |
| evidence_photo | 現場證據 | 现场证据 | Field Evidence | 現場の証拠 |
| pier_measure | 碼頭量測 | 码头量测 | Pier Measurements | 桟橋の計測 |

後台 stat 名：`STAT_` + 大寫 event，INT、default 0、client-set、increment-only。

## 驗收

- 假後端：解鎖後 `steam-mock/state.json` 有對應 event；工程抽屜可見。
- 真 Steam：測試 App 上逐項解鎖／重啟不重複／離線再同步。
- 內部訓練包：成就 UI 與回報皆關閉。
