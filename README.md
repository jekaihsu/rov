# ROV 水下機器人模擬器

目前版本：0.3.0（單一來源：`VERSION`）。

共用同一套物理與協定，支援兩個目標：公司內部操作員訓練與 SDK／AI 整合沙盒，以及 Steam 發行的協作潛航遊戲。

## 啟動

```sh
cd simulator
pip install -r requirements.txt
python -m qysim.server
```

開啟 http://127.0.0.1:8080/；回放使用 `http://127.0.0.1:8080/?replay=demo_recording.json`；模型预览为 `/model-preview.html`。

## 測試與建置

```sh
cd simulator
python -m unittest discover -s tests
node --test tests/*.mjs
python tools/vendor_manifest.py --check
python tools/sync_version.py --check
python tools/build_showcase.py
```

瀏覽器測試需安裝 `playwright` 與 Chromium／Chrome。`python tools/run_browser_checks.py` 會自行在空閒埠啟動伺服器、
依序執行 smoke 腳本並列出通過／失敗表（可指定腳本名稱，例如 `python tools/run_browser_checks.py browser_smoke browser_menu_smoke`；
`--list` 列出全部）。也可手動啟動 `python -m qysim.server --http-port 8092 --ws-port 8792` 後單獨執行 `python tools/browser_smoke.py`。
環境變數：`ROV_CHROMIUM`（瀏覽器執行檔絕對路徑）、`ROV_HTTP_PORT`／`ROV_WS_PORT`（伺服器埠）、
`ROV_BROWSER_TIMEOUT_SCALE`（慢機器放大逾時倍數），詳見 `tools/_browser.py`。
桌面版：`cd simulator/desktop && npm ci && npm run vendor`。

## 目錄

- `simulator/qysim/`：權威物理後端。
- `simulator/viewer/`：原生 ES modules 前端與精簡 three.js。
- `simulator/sdk_mock/`：SDK 整合沙盒。
- `simulator/desktop/`：Electron 桌面版。
- `simulator/tests/`、`simulator/tools/`：測試與建置工具。
- `docs/tasks/`：任務書；[代理工作規範](AGENTS.md)。
- [舊硬體設計文件](docs/hardware/README.md)。

`docs/showcase/` 為忽略的產生物；main 更新時由 Actions 建置並部署 Pages。
新增 three.js addon 的步骤（从仓库根目录执行）：

```sh
(cd simulator/desktop && npm ci)
# 在 viewer 新增 import 后，自动从固定版本 three@0.160.0 恢复缺失的 addon 与递归依赖。
python simulator/tools/vendor_manifest.py --prune
python simulator/tools/vendor_manifest.py --check
```

提交更新后的 `vendor-manifest.json` 与 vendor 文件。`--check` 只检查，不恢复或改写文件；失败会给出修复命令。
Basis / Draco 解码器、WASM、worker 等通过 URL 路径载入的资产不在 import 图中：
请手动将其相对 `vendor/three/` 的文件路径加入清单的 `runtime` 数组（目前为空）。
生成器会从同版本 npm 套件恢复这些文件，`--prune` 保留它们，桌面版与展示页也会复制它们。
更新版本時修改 `VERSION`，執行 `python simulator/tools/sync_version.py` 並提交產生的版本資訊。
授權狀態見 [LICENSING.md](LICENSING.md)。
