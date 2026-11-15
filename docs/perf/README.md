# 實機 GPU 效能量測報告

每台機器一份 `gpu-<機器代號>.md`，由 `simulator/tools/browser_gpu_bench.py` 產生。

```bash
cd simulator
# 可選 smoke（無 GPU 也可；不在 run_browser_checks 預設清單）
python tools/run_browser_checks.py browser_gpu_bench

# 實體 GPU 完整矩陣（Steam 決策用）
export ROV_CHROMIUM=/usr/bin/google-chrome   # 本機 Chrome
export ROV_BROWSER_GL=gpu
python tools/browser_gpu_bench.py --full --machine my-pc --duration 30 --desktop
```

軟體算圖（SwiftShader）報告僅供工具驗證，見各檔開頭警告。
