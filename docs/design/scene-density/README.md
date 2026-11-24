# T1 場景密度（審查退回後重做）

範圍只含 T1 負責的戶外情境（開放水域、風場／導管架、沉船、礁與海草、聲納、事故演練等）。
港灣歸 R5；船殼與箱網歸 R6，本分支不改其碰撞與任務幾何。

## 做法

- 地標仍以 `qysim/scene_landmarks.py` 加在既有障礙物上；`add_landmarks` 只對 `OWNED` 場景生效。
- 可拍攝細節改走 R6 已定義的 `inspection_finds`（habitat 實體），刪除自建的 `site_discoveries`／`discovery_details`。
- 每場約 8 個近距看得清楚的主體（材質、頂點色、受燈光與陰影），不堆灰方塊。
- `observation_photo` 維持只在遠征模式可用（撤回對 SDK 行為的放寬）。
- 開放水域測站浮具改以與碰撞一致的 tube 繪製，並把回收浮標完全沒入水面下。
- 近水面（深度 < 0.4 m）關閉水下 optics 雙面海面與背景對水面的硬裁切
  （`fx/surface.js`、`fx/daylight.js`、`fx/water_optics.js`），避免機載畫面出現深藍三角板。
  證明圖：`spawns/open_water_depth01.jpg`。

## 驗收畫面

每個負責場景留一張出生姿態（中畫質、燈關）與一張前後對照聯絡表（≤ 300 KB），放在 `contacts/`。
大量逐秒原圖改放到本機 `output/scene-density-archive/`，不提交。

| 場景 | 聯絡表 |
|---|---|
| 開放水域 | [contacts/open_water.jpg](contacts/open_water.jpg) |
| 導管架／風場 | [contacts/jacket_inspection.jpg](contacts/jacket_inspection.jpg)、[contacts/cold_open_jacket.jpg](contacts/cold_open_jacket.jpg)、[contacts/monopile_current.jpg](contacts/monopile_current.jpg)、[contacts/tether_untangle.jpg](contacts/tether_untangle.jpg) |
| 沉船 | [contacts/wreck_survey.jpg](contacts/wreck_survey.jpg)、[contacts/korean_castle.jpg](contacts/korean_castle.jpg)、[contacts/incident_wreck.jpg](contacts/incident_wreck.jpg) |
| 礁／草 | [contacts/coral_reef.jpg](contacts/coral_reef.jpg)、[contacts/seagrass_meadow.jpg](contacts/seagrass_meadow.jpg) |
| 其他 | [contacts/sonar_search.jpg](contacts/sonar_search.jpg)、事故四場、[contacts/random.jpg](contacts/random.jpg) |

## 開場標準對照

| 項目 | 本次 |
|---|---|
| 30 秒內有事可做 | 出生朝向可見地標或生物；可飛近拍照（遠征模式）或沿原任務前進 |
| 一次一個提示 | 未新增並列提示 |
| 角色無線電 | 沿用既有風場／任務對講 |
| 真實危機 | 既有勾纏、洋流、揚沙、能見度不變 |
| 不卡關 | 新物件不擋任務點；R5／R6 場景幾何未動 |
| 演出交還操控 | 未改過場 |
| 乾淨 HUD | 未新增常駐 HUD |
| 有收尾 | 遠征拍照仍進收藏；原任務結算照常 |
