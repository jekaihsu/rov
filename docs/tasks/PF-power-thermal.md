# PF 供電與熱保護

供電在推進器分配後、馬達動力學積分前生效。優先供應附件，依總電流、單路電流及負載端電壓
等比例縮小帶正負號的推力指令。熱限制採用前一步的馬達、驅動器與艙溫。降載或保護停機後，
實際推力仍按既有馬達時間常數衰減。

- [模型參數與待量測項目](../reference/x1-measurement-checklist.md#pf-供電附件與熱保護量測)
- [狀態欄位與單位](../../simulator/PROTOCOL.md#optional-power-tether-power-budget--battery)
- 系統面板 1600 × 900 截圖：[修改前](evidence/PF/before.jpg)、[修改後](evidence/PF/after.jpg)
