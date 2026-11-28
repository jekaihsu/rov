# 內部操作員訓練教材

適用：公司 X1 級 ROV 操作員的模擬器課堂訓練。版本：D3，待基準航次校準。
本課程不是實機操作授權，也不宣稱等同 IMCA 認證。

- [學員手冊](student-manual.md)：課前閱讀、流程與通訊演練。
- [課程表](curriculum.md)：初級 240 分鐘、中級 240 分鐘、進階 240 分鐘的個人操桿時間。
- [教官手冊](instructor-manual.md)：開課操作、故障注入、證據與門檻校準。
- [可列印考核表](assessment.html)：以瀏覽器開啟，A4 直向列印；每航次一份、每課彙總一份。

所有合格門檻：**暫定，待資深操作員基準航次校準**。課時是教學安排，不是已驗證的能力養成時間。
X1 專屬參數、模式名稱、按鍵、警報、岸電順序、吊放與環境限值均為暫定，須由原廠文件及公司實機資料確認。
目前倉庫未提供 `docs/reference/own/` 的實測資料，不填入推測的機型數字。

## 課堂入口與資料來源

內部版主選單的「訓練模式」開課程地圖（入門／操作員／進階／事故處置），預設真實擬真，
並在本機寫入學員紀錄（CSV／一頁成績單可匯出，不上傳）。Steam 版不顯示此入口。
工程面板的「章節 / 訓練課程」仍可選 B01–A04，勾選「公司課程（略過故事）」後開始。
每份 `course_*.json` 是一堂課的可重播航次；課時透過重複航次累積，不延長既有情境期限。
課程沒有故事、獎勵或通關鎖；由教官依課程表換課。JSON 的 `source_chapters` 是教材溯源，
不是引擎的跨章節呼叫；`training` 是課時與考核說明，不會自動計時或判定人工項目。
課程沿用 T12 的 objective/wait/branch/checkpoint 節點與原有情境。
劇情導演（R1 `beat_director.js`）尚未合併進 main 時，課程仍用既有 radio／節點執行。

教材依據：[研究報告](../reference/real-rov-research.md)的「臍帶纜」「下水回收」「事故」「訓練與考核」各節、
[實測清單](../reference/x1-measurement-checklist.md)、[T12](../tasks/T12-campaign-and-tutorial.md)、
[事故章節說明](../../simulator/campaign/INCIDENTS.md)、
[教官評分實作](../../simulator/qysim/instructor.py)與[場景評分實作](../../simulator/qysim/scenarios.py)。
研究中的其他機型程序僅用於通用原理比較，不作 X1 的操作規格。
