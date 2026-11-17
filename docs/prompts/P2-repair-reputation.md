# P2：失敗代價：維修費與聲譽（Codex／Cursor）

```
你在 jekaihsu/rov（遊戲 ROV Solution）工作。依 game-plan §11「失敗代價：要賠錢修設備、聲譽下降；不會破產卡死（公司墊付）」實作：
- 碰撞、纏纜、缺陷漏檢造成的推進器損傷、進水、纜線受損、遺失配件，在結算時列出維修項目與費用（價格表放資料檔，註明為遊戲設定值）；費用從報酬扣，不夠扣時公司墊付並記為欠款，之後的報酬優先償還；永遠不會無法接案。
- 聲譽：依委託方分別記錄；中止但安全撤離扣少量，損壞客戶設施或交付不實扣較多，金牌與準時加分；聲譽影響可接的委託（career/rules.js 已有門檻）。
- 結算畫面（大片感版）在「明細」裡列出維修單；主數字仍是實領。
- 存檔 rov.career.v1 要相容舊存檔（新欄位有預設值，附遷移測試）。
- 損傷判定只讀伺服器既有狀態（推進器健康、事件、纜線事件），不新增物理。
瀏覽器檢查：browser_career_smoke browser_results_smoke browser_menu_smoke。

共同規則（每份都適用）：
- 先完整讀 AGENTS.md（有約束力）、docs/design/game-plan.md §9–§11、docs/prompts/README.md 最後的「所有場景的共同規則」。
- 物理、SDK 語意、協定既有欄位不得為遊戲性而改；新增協定欄位一律選填並更新 simulator/PROTOCOL.md。
- 超出真機的輔助一律註冊擬真項目，real 預設關（simulator/viewer/menu/fidelity_items.js）。
- app.js 只加最小的 import 與呼叫；新程式一行一敘述、≤120 字元、具名函式、檔頭註解；玩家看得到的字串放 STRINGS 並用 i18n 的 localize 包裝，附英文、簡中、日文。
- 新後端邏輯要有單元測試；不得刪除或放寬既有測試。
- 本機測試必跑並把指令與結果貼進 PR：cd simulator && python -m unittest discover -s tests；node --test simulator/tests/*.mjs；python ../tools/test_check_matrix.py（在 simulator 外為 python tools/test_check_matrix.py）；以及任務列出的瀏覽器檢查（python tools/run_browser_checks.py ...）。
- 前端變更附前後截圖（1600×900），放 docs/design/<任務名>/。
- 從最新 main 開分支 task/<編號>-<短名>，開 draft PR，完成後轉 ready for review。PR 標題以編號開頭。
```
