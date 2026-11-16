# L1 四語術語表

專有名稱 `ROV Solution`、`YX`、`YX Model R／O／V／S`、`Block` 不翻譯。
縮寫 DVL、SDK、HUD、OSD 與單位保持原樣。機載 OSD 的英文儀表縮寫沿用真機風格。

| 繁體中文 | English | 简体中文 | 日本語 |
|---|---|---|---|
| 遙控無人潛水載具（ROV） | remotely operated vehicle (ROV) | 遥控无人潜水器（ROV） | 遠隔操作型無人潜水機（ROV） |
| 臍帶纜 | umbilical | 脐带缆 | アンビリカルケーブル |
| 纜線（觀測級連接纜） | tether | 缆线 | テザー |
| 定深 | depth hold | 定深 | 深度保持 |
| 定向 | heading hold | 定向 | 方位保持 |
| 定點 | station keeping / position hold | 定点保持 | 定点保持 |
| DVL 失鎖 | DVL bottom lock lost | DVL 失去底锁 | DVL ボトムロック喪失 |
| 離底高度 | altitude above bottom | 离底高度 | 対底高度 |
| 犧牲陽極 | sacrificial anode | 牺牲阳极 | 犠牲陽極 |
| 陰極保護 | cathodic protection | 阴极保护 | 電気防食（陰極防食） |
| 機械臂 | manipulator | 机械臂 | マニピュレーター |
| 聲納 | sonar | 声呐 | ソナー |
| 推進器 | thruster | 推进器 | 推進器 |
| 解鎖／上鎖 | arm / disarm | 解锁／上锁 | アーム／ディスアーム |
| 手把 | controller | 手柄 | コントローラー |
| 解析度 | resolution | 分辨率 | 解像度 |

## 用語依據

以下為術語與操作語意依據，四語欄為本專案編譯，不宣稱來源提供官方四語對照。

- [NOAA：ROV](https://oceanexplorer.noaa.gov/ocean-fact/rov/)：ROV 的定義與繫纜操作。
- [ArduSub flight modes](https://ardupilot.org/sub/docs/modes.html)：深度保持、方位保持與定位控制的區分。
- [Water Linked DVL 文件](https://docs.waterlinked.com/dvl/overview/)：bottom lock、altitude 與對底速度；失鎖不可翻成斷線。
- [JAMSTEC「かいこう」](https://www.jamstec.go.jp/j/about/equipment/ships/kaiko.html)：日文無人探查機與纜線系統語境。
- [AMPP：Cathodic protection](https://www.ampp.org/resources/what-is-corrosion/cathodic-protection)：犧牲陽極與陰極保護的關係。
- [GB/T 國家標準查詢](https://openstd.samr.gov.cn/bzgk/gb/)：以「阴极保护」「牺牲阳极」查詢中國大陸標準用語。
- 專案 [真實 ROV 研究](../reference/real-rov-research.md) 的控制模式、導航感測器與臍帶纜章節。

「臍帶纜」與「tether」依實際系統區分；短 HUD 標籤既有「纜線」用 tether，
不得把所有纜線都解釋成供電臍帶纜。此任務不改動真機參數或控制行為。
