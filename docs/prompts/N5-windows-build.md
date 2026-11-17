# N5：在你的 Windows 電腦上打包給同事（你本機的代理）

```
請在這台 Windows 電腦上幫我打包 ROV Solution 的可攜版給同事試玩。

1. 進到 rov 資料夾（沒有就 git clone https://github.com/jekaihsu/rov.git），git checkout main && git pull。
2. 完整讀 simulator/desktop/README.md 的「Rebuild」一節，照做：
   - 建一個乾淨的 Python 3.11 虛擬環境，只裝 numpy==1.24.4、numba==0.57.1、llvmlite==0.40.1、websockets==15.0.1、pyinstaller==6.22.3。
   - 需要 Node 22；沒有就幫我安裝。
   - cd simulator/desktop → npm ci → npm run vendor
   - 回到 rov 根目錄 → <虛擬環境的 python> simulator/desktop/build_backend.py → <虛擬環境的 python> simulator/desktop/smoke_backend.py
   - cd simulator/desktop → npm run make -- --platform=win32 --arch=x64
   - 至少要有 2 GB 可用空間。
3. 打包完成後：
   - 打開 simulator/desktop/out/ 裡的 ROV Simulator.exe，確認能進主選單、開始一次自由潛水、能操作。
   - 如果有 PS 手把，照 docs/reference/playstation-controller.md 的五分鐘清單測一遍。
4. 把 out/make 裡的 zip 檔路徑、大小告訴我；任何錯誤訊息完整貼給我。不要提交任何建置產物到 git。
```
