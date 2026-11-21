# 預告片分鏡審核畫面

每張 `*.jpg` 是對應鏡頭的代表畫面（≤ 300 KB），由 `simulator/tools/trailer/run.py` 產出。  
分鏡定義在 `simulator/tools/trailer/storyboards/`；商店 80 秒說明見 `docs/store/steam/trailer.md`。

重新產生審核靜幀：

```bash
python3 simulator/tools/trailer/run.py \
  --storyboard simulator/tools/trailer/storyboards/store_80s.json --hero-only
python3 simulator/tools/trailer/run.py \
  --storyboard simulator/tools/trailer/storyboards/demo.json --hero-only
```

## 商店 80 秒（`store_80s.json`）

| 檔名 | 對應 trailer.md |
|---|---|
| `01-harbor-fpv-drift.jpg` | 01 港灣 FPV 漂移 |
| `02-harbor-fpv-current.jpg` | 02 讀水流 |
| `03a-harbor-tether-follow.jpg` | 03 第三人稱纜線 |
| `03b-harbor-fpv-return.jpg` | 03 切回 FPV |
| `04-pool-sensors.jpg` | 04 感測限制 |
| `05a-pool-descent.jpg` | 05 水池下潛 |
| `05b-cold-open-establish.jpg` | 重用倒敘開場 |
| `06-hull-document.jpg` | 06 船殼記錄 |
| `07-pen-inspect.jpg` | 07 網衣巡檢 |
| `08-pen-approach.jpg` | 08 精準接近 |
| `09-harbor-next-job.jpg` | 09 下一次作業 |
| `10a`–`10c-*.jpg` | 10 蒙太奇 |
| `11-harbor-cta.jpg` | 11 CTA 背景 |

Demo 剪輯靜幀為 `demo-*.jpg`；`test-5s-harbor.jpg` 為管線證明鏡。
