# T12 驗證證據

基底：origin/main `132b86e`（含 T02、T05、T08）。
截圖均為 1600×900；錄影為 800×450，保留完整介面並降低儲存量。
這些 PNG／WebM 是任務書要求的審查證據，刻意提交；沒有修改 docs/showcase。

- [變更前](before.png)：主線介面，同一測試水池。
- [序章對話](prologue.png)、[序章完成](prologue-completed.png)。
- [第一章簡報](chapter-one.png)、[第一章操控](chapter-one-flight.png)。
- [完整序章錄影](prologue.webm)：從主選單開始，實際按鍵操控。
- [第一章遊玩片段](chapter-one.webm)：港灣簡報、纜線對話、解鎖與前進；不是全章通關證明。
- [序章完成狀態](results.json)：status=completed、completed 包含 prologue，逐步 visited 與 errors=[]。

本機執行：

```text
cd simulator
python -m unittest discover -s tests
Ran 131 tests in 173.858s
OK (skipped=1)
```

唯一跳過是既有 test_ecology 對可選 Numba 的檢查，沒有新增 skip 或變更既有測試。
序章整合測試透過 RC 通道驅動物理更新，未直接改寫位置、速度或任務完成旗標。
新增測試另涵蓋條件、分支、腳本驗證、房主權限、席位重連、解鎖／存讀檔、存檔點重啟與腳本效果。

```text
node --test simulator/tests/*.mjs             # 15 passed
node simulator/desktop/test_collection_store.cjs  # passed
python simulator/tools/vendor_manifest.py --check  # Three.js manifest: 10 files
python simulator/tools/sync_version.py --check     # passed
python simulator/tools/check_changed_js.py origin/main  # passed
python tools/browser_campaign_smoke.py        # passed, full main-menu-to-completion input run
python tools/browser_menu_smoke.py            # passed
```

瀏覽器伺服器使用 `--http-port 8092 --ws-port 8792 --rpc-port 9792`。
需安裝 Playwright 與 FFmpeg；新教學測試明確指定 ANGLE／SwiftShader。
既有 smoke 測試未修改；本機以啟動器加同樣渲染旗標。

`browser_smoke.py` 三視窗測試在 `.pilot-pip-canvas` 出現前逾時。
對最初主線 `4065ba5` 的原始工作樹重跑同一測試，也遇到軟體渲染的 screenshot 逾時。
這兩個結果都不是通過；PiP／多視窗渲染列為後續，未在 T12 改動或放寬測試。
目前主線自己的 Browser workflow 已將這組測試列為 advisory；T12 沒有變更 workflow。
