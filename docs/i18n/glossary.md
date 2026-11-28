# ROV Solution 四語術語表

專有名稱 `ROV Solution`、`YX`、`YX Model R／O／V／S`、`Block` 不翻譯。
縮寫 DVL、SDK、HUD、OSD 與單位保持原樣。機載 OSD 的英文儀表縮寫沿用真機風格。

第一個譯法供介面使用。「／」後列無線電簡稱、詞形或依情境可用的說法。作業人員的職稱與通話呼號分列。纜線手說「我放一點」時，台詞可以省略上下文已明確的名詞。

下表的「研究」指[真實 ROV 研究報告](../reference/real-rov-research.md)，「設定集」指[故事設定集](../story/bible.md)。依據欄指出作業概念或作品內的定名；未取得當地專業來源的候選詞註記「待確認」。

## 作業用語

| 繁中 | English | 简中 | 日本語 | 依據 |
|---|---|---|---|---|
| 遙控無人潛水載具／遙控潛水器 | remotely operated vehicle／ROV | 遥控无人潜水器／遥控潜水器／ROV | 遠隔操作型無人潜水機／ROV | 研究報告首節；字幕與 HUD 可保留 ROV |
| 臍帶纜 | umbilical | 脐带缆 | アンビリカルケーブル | 研究「臍帶纜是主動的力」；主纜，與輕型 ROV 的 tether 依系統區分。[JAMSTEC KM-ROV 運用資料](https://www.jamstec.go.jp/mare3/e/boarding/guide_ship/doc/km-rov.pdf) |
| 纜線 | tether／line | 缆线／缆 | テザー／ライン | 研究引 VideoRay Pro 4 纜線管理；口語可簡稱 line |
| 纜線手 | tether tender／tender | 缆手 | テザー担当 | 設定集 §3.2；英文可見[華盛頓大學 ROV 團隊技術文件](https://20693798.fs1.hubspotusercontent-na1.net/hubfs/20693798/EX12%20UniversityofWashington_UnderwaterRemotelyOperatedVehiclesTeam_TECHNICAL%20DOCUMENTATION_2023.pdf)。日文為本作職稱，業界統一稱謂待確認 |
| 張力 | tension | 张力 | 張力 | 研究「纜線、聲納、流程與事故」；HUD 讀數用 N |
| 定深 | depth hold／hold depth | 定深 | 深度保持 | 研究「閉迴路航向與深度」；深度控制模式 |
| 定向 | heading hold | 定向 | 方位保持 | 同上；羅盤航向 |
| 定點 | position hold／station keeping／hold position／holding position | 定点保持／定点 | 定点保持 | 研究「DVL 定點」；對地位置 |
| 勾纏 | snag／entanglement／foul | 钩挂／缠绕／挂住 | 引っかかり／絡まり | 研究引 VideoRay 纜線管理；卡在邊緣與繞住物件須按情境選詞 |
| 犧牲陽極 | sacrificial anode | 牺牲阳极 | 犠牲陽極 | AMPP 陰極保護資料，見下方來源 |
| 陰極保護 | cathodic protection／CP | 阴极保护 | 電気防食／陰極防食 | AMPP 陰極保護資料；日文技術標籤可用陰極防食 |
| 機械臂 | manipulator／robotic arm | 机械臂 | マニピュレーター／マニピュレータ | 研究「檢測怎麼飛」及 JAMSTEC 作業資料 |
| DVL 失鎖／DVL 失去底鎖 | DVL bottom lock lost／loss of bottom lock | DVL 失去底锁 | DVL ボトムロック喪失 | Water Linked DVL 文件；指失去對底速度參考 |
| 陽極 | anode | 阳极 | 陽極 | 設定集末段 C 腿陽極座；防蝕用途 |
| 導管架 | jacket | 导管架 | ジャケット | 研究「檢測怎麼飛、事故怎麼發生」引 IMCA 02/23 |
| 船殼 | hull | 船壳／船体 | 船体／外板 | 第一章船體檢查；外板專指拍攝或接觸的板材 |
| 海底門 | sea chest | 海底门 | シーチェスト | [船底場景規格](../prompts/R6-hull-pen-scenes.md)；拍攝目標是入口格柵。[日本運輸安全委員會事故報告註 1](https://jtsb.mlit.go.jp/ship/rep-acci/2025/keibi2025-4-4_2023yh0153.pdf) |
| 網衣 | netting／net | 网衣／网 | 網地／網 | 第二章箱網巡檢；網布與整座網箱分開。[深水网箱通用技术要求 第2部分：网衣](https://std.samr.gov.cn/hb/search/stdHBDetailed?id=BFEAD835AAAC4233E05397BE0A0AB035) |
| 上鎖掛牌／LOTO | lockout/tagout／LOTO／lockout and tagout | 上锁挂牌／LOTO | ロックアウト・タグアウト／LOTO／ロックアウトとタグアウト | C12-001 船方確認隔離；[GB/T 33579-2017](https://std.samr.gov.cn/gb/search/gbDetailed?id=71F772D81D67D3A7E05397BE0A0AB82A)、[OSHA 1910.147](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.147) |
| 聲納 | sonar | 声呐 | ソナー | 研究「聲納與導航感測器」 |
| 離底高度／離底 | altitude above bottom／altitude／height above bottom／above bottom | 离底高度／离底 | 対底高度 | 研究「DVL 定點」；從機體量到海床 |
| 推進器 | thruster | 推进器 | スラスター／推進器 | 研究「真實載具的預設語意」；與可夾取物件的機械臂區分 |

## 呼號與姓名

| 繁中 | English | 简中 | 日本語 | 依據 |
|---|---|---|---|---|
| 向潮 | Facing Tide | 向潮 | コウチョウ | 設定集 §2、§5.1 船名 |
| 向潮－指揮 | Tide Control | 向潮－指挥／向潮指挥 | コウチョウ指揮 | 設定集 §5.1、開場語音 |
| 向潮－纜手 | Tide Cable | 向潮－缆手／向潮缆手 | コウチョウ・テザー | 設定集 §5.1；日文依船名與職務定名 |
| 向潮－甲板 | Tide Deck | 向潮－甲板／向潮甲板 | コウチョウ甲板 | 設定集 §5.1；日文依船名與職務定名 |
| R-1 | R-One／R-1 | R-1 | R-1 | 設定集 §5.1；英文通話讀 R-One，儀表用 R-1 |
| R-2 | R-Two／R-2 | R-2 | R-2 | 設定集 §5.1；備機 |
| 岸台－葉 | Shore Yeh | 岸台－叶 | 陸上局のイェ | 設定集 §3、§5.1，C11-001 |
| 網台－翁 | Pen Weng | 网台－翁 | いけす局のオン | 設定集 §3、§5.1，C21-001 |
| 林岑 | Lin Cen | 林岑 | リン・ツェン | 設定集 §3.1 |
| 周楷 | Zhou Kai | 周楷 | シュウ・カイ | 設定集 §3.2 |
| 方晴 | Fang Qing | 方晴 | ファン・チン | 設定集 §3.3 |
| 馬力 | Ma Li | 马力 | マー・リー | 設定集 §3.4 |
| 葉理 | Yeh Li | 叶理 | イェ・リー | 設定集 §3 |
| 翁慈 | Weng Ci | 翁慈 | オン・ツー | 設定集 §3 |

## 固定介面標籤

| 繁中 | English | 简中 | 日本語 | 依據 |
|---|---|---|---|---|
| 二級駕駛員 | Class II pilot | 二级驾驶员 | 二級操縦士 | 本作執照卡 brand.licence_card，與生涯工單一致 |
| 開始 | Start | 开始 | 開始 | menu.main 按鍵提示 |
| 確認 | Confirm | 确认 | 決定／確認 | 選定選項用「決定」，檢查表覆核用「確認」。menu.main、procedure.index |
| 返回 | Back | 返回 | 戻る | menu.main 按鍵提示 |
| 關閉 | Close／Off | 关闭 | 閉じる／オフ | menu.main 關窗按鍵；顯示設定的停用狀態用 Off、オフ |
| 下水 | Deploy | 下水 | 着水 | menu.screens 簡報主按鈕 |
| 設定 | Settings | 设置 | 設定 | menu.screens 主選單 |
| 解鎖 | Arm／Arm thrusters／Unlock | 解锁 | アーム／ロック解除 | 研究「下水回收」；推進器啟用用 arm |
| 上鎖 | Disarm／Lock | 上锁 | ディスアーム／ロック | 研究「下水回收」；回收前停用推進器 |
| 手把 | controller／gamepad | 手柄 | コントローラー | input.settings 裝置名稱 |
| 解析度 | resolution | 分辨率 | 解像度 | menu.display_settings 顯示設定 |
| 螢幕 | screen／display | 屏幕 | 画面 | menu.display_settings 顯示設定 |
| 訊號 | signal | 信号 | 信号 | 研究「聲納與導航感測器」 |

## 校對時執行

在儲存庫根目錄執行 `python simulator/tools/i18n_glossary_check.py`。每筆提示附上語言、namespace 與 key 或台詞 ID、建議用語和實際譯文。作業用語會比對句中用詞；固定按鍵按完整標籤比對，例如顏色設定的 Off 與關窗按鈕的 Close。通話中的簡稱、省略與語序仍需讀完整句判斷。完整檢查層將報告寫入 `simulator/output/checks/full/i18n_glossary_check.log`。

## 用語依據

以下為術語與操作語意依據，四語欄為本專案編譯，不宣稱來源提供官方四語對照。

- [NOAA：ROV](https://oceanexplorer.noaa.gov/ocean-fact/rov/)：ROV 的定義與繫纜操作。
- [ArduSub flight modes](https://ardupilot.org/sub/docs/modes.html)：深度保持、方位保持與定位控制的區分。
- [Water Linked DVL 文件](https://docs.waterlinked.com/dvl/overview/)：bottom lock、altitude 與對底速度；失鎖不可翻成斷線。
- [JAMSTEC「かいこう」](https://www.jamstec.go.jp/j/about/equipment/ships/kaiko.html)：日文無人探查機與纜線系統語境。
- [AMPP：Cathodic protection](https://www.ampp.org/resources/what-is-corrosion/cathodic-protection)：犧牲陽極與陰極保護的關係。
- [GB/T 國家標準查詢](https://openstd.samr.gov.cn/bzgk/gb/)：以「阴极保护」「牺牲阳极」查詢中國大陸標準用語。
- 專案 [真實 ROV 研究](../reference/real-rov-research.md) 的控制模式、導航感測器與臍帶纜章節。
