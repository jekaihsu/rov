# 礁區生物與珊瑚模型（N3）

由 CC0 真實標本掃描減面、烘焙後輸出。重建：

```bash
python cad/download_reef_sources.py --out /tmp/reef_sources
blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources
```

下載腳本寫入 `ffish/<id>/src/scene.gltf` 與 `smithsonian/<id>_raw.glb`（與建置腳本一致）。
來源與授權見 `simulator/viewer/models/CREDITS.md`。珊瑚為史密森尼乾燥標本，
已用程序色改成活珊瑚色調（未使用任何照片貼圖）。

棚拍 JPEG（1600×900）與本 README 同目錄。

| 模型 | 近景三角形 | 近景大小 | 遠景三角形 | 遠景大小 | 授權 |
|---|---:|---:|---:|---:|---|
| `urchin` | 1481 | 172.0 KB | 281 | 147.6 KB | CC0 |
| `starfish` | 1498 | 131.6 KB | 298 | 101.2 KB | CC0 |
| `crab` | 1487 | 151.0 KB | 258 | 108.4 KB | CC0 |
| `cucumber` | 1500 | 106.6 KB | 300 | 72.9 KB | CC0 |
| `mussel` | 1381 | 126.5 KB | 300 | 75.7 KB | CC0 |
| `barnacle` | 1500 | 137.0 KB | 300 | 122.4 KB | CC0 |
| `butterflyfish` | 2247 | 105.5 KB | 463 | 80.5 KB | CC0 |
| `angelfish` | 2285 | 110.8 KB | 499 | 106.9 KB | CC0 |
| `stripey` | 2289 | 136.2 KB | 492 | 115.7 KB | CC0 |
| `wrasse` | 1796 | 101.7 KB | 689 | 105.1 KB | CC0 |
| `acropora_palmata` | 3998 | 100.8 KB | 800 | 65.2 KB | CC0 |
| `acropora_hyacinthus` | 3998 | 141.1 KB | 798 | 89.3 KB | CC0 |
| `diploria` | 3964 | 133.8 KB | 764 | 82.0 KB | CC0 |
| `pocillopora` | 3997 | 137.5 KB | 797 | 88.5 KB | CC0 |
| `porites` | 4000 | 113.8 KB | 800 | 77.2 KB | CC0 |

三角形上限：小型生物 1500／300，魚 2500／700，珊瑚 4000／800。
每個 GLB ≤ 400 KB；貼圖 512 px WebP。魚：鼻尖 +Z、背朝上、公尺單位。
