# 礁區生物與珊瑚模型（N3）

由 CC0 真實標本掃描減面、烘焙後輸出。重建：

```bash
# optional: python cad/download_reef_sources.py --out /tmp/reef_sources
blender -b -P cad/build_reef_life.py -- --source /path/to/reef_sources
```

來源與授權見 `simulator/viewer/models/CREDITS.md`。珊瑚為史密森尼乾燥標本，
已用程序色改成活珊瑚色調（未使用任何照片貼圖）。

棚拍 JPEG（1600×900）與本 README 同目錄。

| 模型 | 近景三角形 | 近景大小 | 遠景三角形 | 遠景大小 | 授權 |
|---|---:|---:|---:|---:|---|
| `urchin` | 1482 | 178.5 KB | 281 | 154.6 KB | CC0 |
| `starfish` | 1499 | 133.6 KB | 299 | 104.1 KB | CC0 |
| `crab` | 1487 | 155.9 KB | 258 | 112.3 KB | CC0 |
| `cucumber` | 1500 | 110.6 KB | 300 | 76.0 KB | CC0 |
| `mussel` | 1388 | 130.7 KB | 300 | 78.0 KB | CC0 |
| `barnacle` | 1500 | 140.7 KB | 300 | 126.2 KB | CC0 |
| `butterflyfish` | 2268 | 109.1 KB | 480 | 83.6 KB | CC0 |
| `angelfish` | 2299 | 113.6 KB | 506 | 111.1 KB | CC0 |
| `stripey` | 2290 | 139.6 KB | 494 | 119.9 KB | CC0 |
| `wrasse` | 1916 | 108.5 KB | 690 | 111.4 KB | CC0 |
| `acropora_palmata` | 3998 | 103.2 KB | 800 | 68.6 KB | CC0 |
| `acropora_hyacinthus` | 3998 | 144.8 KB | 798 | 94.4 KB | CC0 |
| `diploria` | 3967 | 137.7 KB | 765 | 86.5 KB | CC0 |
| `pocillopora` | 3997 | 141.4 KB | 797 | 93.8 KB | CC0 |
| `porites` | 4000 | 116.7 KB | 800 | 81.0 KB | CC0 |

三角形上限：小型生物 1500／300，魚 2500／700，珊瑚 4000／800。
每個 GLB ≤ 400 KB；貼圖 512 px WebP。魚：鼻尖 +Z、背朝上、公尺單位。
