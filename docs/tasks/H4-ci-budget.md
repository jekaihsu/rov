# H4：CI 額度準備

基底 main，開發期間維持 draft，12/1 額度恢復前以本機驗證。

- 記錄各單元模組與瀏覽器腳本時間於 `docs/ci/timings.md`。
- `tools/check_matrix.py` 共用 quick/full 與路徑選測規則。
- 非 draft PR 執行 quick；ready_for_review 或 workflow_dispatch 執行 full。
- Playwright PR 工作僅限 viewer 路徑；Windows 僅手動。
- pip、numba 快取；所有 workflow 有取消舊工作及 timeout。
- 審查者與代理使用 `python tools/run_checks.py --changed`，完整驗證仍需 full。

驗收紀錄及限制見 timings 與 PR 描述。
