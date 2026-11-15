# 真實小型觀測級 ROV：操作員實際聽到的聲音

整理公開文件與影片可核實的「水面端聽覺」與「超出真機」的水下層。未標來源或查不到的項目標為**假設**。

## 結論（對訓練真實感）

小型觀測級 ROV 多半**沒有水聽器**。操作員在控制盒／筆電旁，聽到的是：

1. **甲板與岸上設備**：控制盒或筆電風扇、絞車／線盤馬達與剎車、纜線經過導纜器的摩擦、船與甲板環境聲。
2. **App／地面站提示音**：連線狀態、低電量、錄影等 UI 回饋。
3. **聽不到**：水下推進器聲、碰撞聲、生物聲、水下底噪（除非外接水聽器，非消費級標配）。

因此模擬器應分兩層：**水面端（real 預設開）**與**水下（exceedsReal，assisted 開）**。

## 已核實：機體／遙控器本體提示音

| 聲音 | 說明 | 來源 |
|---|---|---|
| 遙控器開機七聲上升音 | 長按電源至七聲（Do–Ti） | [FIFISH V6 Quick Start](https://www.fifish.co.uk/wp-content/uploads/2021/05/FFIFISH_V6_Quick_Start_V1.3_EN.pdf) |
| ROV 上電五聲 | 接上纜線後 ROV 自動上電，五聲（Do Re Mi Do Mi）；FAQ 亦寫 LED 閃爍伴隨此旋律 | [同上](https://www.fifish.co.uk/wp-content/uploads/2021/05/FFIFISH_V6_Quick_Start_V1.3_EN.pdf)；[V6 APP FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf) |
| 靜置省電蜂鳴 | 開機後持續 beep；開啟 Depth Holding 可停 | [V6 APP FAQ V1.4 §After Dive #3](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)；W6／V-EVO 手冊亦寫「10 分鐘靜置後 beep，開 Depth Holding 可避免」 |

這些是**載具／遙控器硬體蜂鳴**，不是 App 內建音效庫的完整清單。X1 岸電與提示音無公開規格（見 `docs/reference/real-rov-research.md` 缺口表）。

## App／地面站提示音

### FIFISH App（消費級）

| 項目 | 狀態 | 依據 |
|---|---|---|
| 連線／Disconnected | 文件與排查文強調**畫面狀態與燈號**，未寫專用失聯音效 | [QYSEA 斷線排查](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)；FAQ 寫拔纜後約 30 s 重連 |
| 低電量 | RC 電源鍵燈色分級（白／黃／紅）；App 顯示電量百分比；**未找到「低電量提示音」條目** | 同上排查文 |
| 錄影開始／停止、拍照 | 手冊有 Record／Stop／Snap 按鈕與流程；**未找到快門或錄影提示音規格** | [E-GO Manual V1.5](https://www.fifish.co.uk/wp-content/uploads/2025/07/FIFISH_E-GO_User-Manual_V1.5_EN-2024-10-16-172mm232mm.pdf) 等 |
| 深度警示 | 深度尺有分段顯示；**未找到超深／深度警示音** | FAQ 深度尺說明 |
| DVL 失鎖 | 公開 App 文件**未描述**失鎖音效（X1 Q-DVL 行為亦缺實測） | `real-rov-research.md` 定點與 DVL 缺口 |

### 開源地面站（對照，非 X1）

| 項目 | 狀態 | 依據 |
|---|---|---|
| 載具連線／斷線 | Cockpit 可語音／警示（Vehicle connected／disconnected） | [Cockpit alerts](https://deepwiki.com/bluerobotics/cockpit/8.1-data-logging-and-alerts) |
| 低電量 | QGroundControl「Announce battery lower than」；ArduSub 低壓仍可有視覺＋語音警告 | [QGC General settings](https://docs.qgroundcontrol.com/Stable_V5.1/en/qgc-user-guide/settings_view/general.html)；[BR 論壇低壓警示](https://discuss.bluerobotics.com/t/creating-a-low-voltage-alert/14436) |
| DVL 失鎖專用音 | **未找到**獨立「DVL lost lock」音效條目；多為模式／定位狀態文字 | 論壇與 Cockpit 文件抽樣 |

## 水面機械聲（非 App）

| 聲音 | 狀態 | 依據 |
|---|---|---|
| 電動／手搖線盤 | 小型系統常見手搖或慢速電動線盤；QYSEA 電動盤標示 300 m 快／慢檔時間（可推算線速） | `docs/reference/tether-research.md`；[Scuba.com 電動盤摘要](https://www.scuba.com/p-qyelecspool/qysea-electric-powered-spool-for-fifish-w6-version-drone) |
| 剎車／離合 | Deep Trekker API：放纜時線盤脫離、單向離合器、失速旗標 | [PoweredReel](https://docs.api.deeptrekker.com/types/PoweredReel.html) |
| 導纜器摩擦 | 纜線手作業常識；**無公開頻譜量測** → 模擬器以程序合成摩擦噪聲，標**假設** | VideoRay 纜線管理手冊（作業規範，非聲學） |
| 控制盒／筆電風扇 | 操作席常見；**無廠商頻譜** → **假設**低增益粉紅／布朗噪聲 | 領域推論 |

## 水下層（超出真機）

推進器負載、碰撞分級、水下底噪、生物點綴：消費級觀測 ROV 操作員在水面**聽不到**。僅作輔助擬真／遊戲回饋，必須 `registerFidelityItem({id:'underwaterAudio', exceedsReal:true, defaults:{real:false, assisted:true}})`。

## 本專案實作對應（假設一覽）

下列在公開文件查不到音色規格，以短促、不刺耳的 WebAudio 合成代替，並在 PR 標「假設」：

1. App 失聯／重連提示音（對照 Cockpit／斷線文的狀態事件）。
2. 低電量／電源跳脫／功率受限、漏水、熱警告的 App 警告音。
3. DVL 失鎖／重新鎖定的短提示音。
4. 錄影開始／停止與拍照快門音。
5. 絞車馬達音高隨 `tether.reel.speed`、`hold`／失速時剎車摩擦；導纜器摩擦隨放收速度。
6. 水面風扇與甲板底噪的電平。

授權：全部程序合成，無版權取樣檔。
