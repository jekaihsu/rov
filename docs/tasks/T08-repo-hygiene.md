# T08 儲存庫整理：產生物與重複的第三方程式

**目標**：讓 PR 乾淨、clone 變小、之後多個代理並行不互相干擾。

**範圍**：`docs/showcase/`、`simulator/viewer/vendor/`、`simulator/tools/build_showcase.py`、`simulator/desktop/vendor.cjs`、`.github/workflows/`、`.gitignore`、README。不改功能程式。

**要做**

1. `docs/showcase/` 是 `simulator/viewer/` 的複製品（含完整 three.js）。改為由 GitHub Actions 在 `main` 更新時執行 `build_showcase.py` 並部署到 GitHub Pages（`actions/deploy-pages`）。從版本庫移除 `docs/showcase/`，加入 `.gitignore`。`docs/index.html` 的連結照常可用。在 PR 描述寫清楚：合併後使用者需把 Pages 來源改為「GitHub Actions」。
2. `simulator/viewer/vendor/three/` 提交了整包 three.js（上千個檔案，含未使用的 rhino3dm、ammo、draco、basis 等 wasm）。改為只保留實際 import 到的檔案：寫一支腳本從 `simulator/viewer/**/*.js` 的 import 圖算出需要的檔案清單，產生精簡的 vendor 目錄並保留 LICENSE。桌面版的 `vendor.cjs` 與展示頁建置使用同一份清單。
3. 根目錄 README 重寫：專案是什麼、兩個目標、如何啟動、如何測試、目錄導覽、連到 `AGENTS.md`。舊的 ROV-01 硬體設計內容移到 `docs/hardware/README.md`。
4. `simulator/desktop/package.json` 版本與 README 寫的 0.3 對齊；建立單一版本來源（例如根目錄 `VERSION`，前端與桌面版讀取）。
5. 加入 `LICENSE` 佔位說明檔 `LICENSING.md`：列出第三方授權彙整位置；專案本身的授權待擁有者決定，不要自行選擇授權條款。
6. 加入 `.editorconfig`，以及 CI 步驟：新增或修改的 `simulator/viewer/**/*.js`（不含 vendor）行寬超過 160 字元時失敗。只檢查 PR 變更的行，不要求清理既有檔案。
7. CI 加入一個 Playwright job，跑 `simulator/tools/browser_smoke.py` 與 `browser_menu_smoke.py`（軟體繪圖，headless）。若在 CI 不穩定，標記為非必要檢查並在 PR 說明原因，不可靜默忽略失敗。

**驗證**：本機啟動模擬器、回放模式、`model-preview.html`、桌面版 `npm run vendor` 都正常。PR 描述列出移除的檔案數與 clone 大小變化。

**注意**：這個 PR 會刪除大量檔案。請在其他前端 PR 合併的空檔處理，並在開始前先 rebase 到最新 `main`。不要重寫 git 歷史。
