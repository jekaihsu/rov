# 礁區生命模型（N3）

來源為 Sketchfab／Smithsonian 的 **CC0** 實物掃描；以 `cad/build_reef_life.py` 減面、烘焙法線與顏色後輸出
`simulator/viewer/models/reef/<id>.glb` 與 `<id>_lo.glb`。

珊瑚捨棄乾燥標本白骨色，改以程序色（參考公開水下珊瑚描述的褐黃／粉紅／黃綠調）上成活珊瑚色，
**未使用任何照片當貼圖**。貼圖 ≤ 512 px WebP；每個 GLB ≤ 400 KB。

| 檔名 | 物種 | 三角形（近／遠） | 大小（近／遠） | 授權 |
|---|---|---:|---:|---|
| `acropora_palmata.glb` | 鹿角珊瑚 *Acropora palmata* | 4000 / 800 | 105 / 73 KB | CC0 |
| `acropora_hyacinthus.glb` | 桌形珊瑚 *Acropora hyacinthus* | 4000 / 799 | 174 / 129 KB | CC0 |
| `brain_coral.glb` | 腦珊瑚 *Diploria labyrinthiformis* | 4000 / 800 | 156 / 118 KB | CC0 |
| `pocillopora.glb` | *Pocillopora damicornis* | 4000 / 800 | 163 / 123 KB | CC0 |
| `porites.glb` | *Porites monticulosa* | 4000 / 800 | 128 / 95 KB | CC0 |

棚拍：同目錄 `<id>.jpg`（1600×900 JPEG，各 ≤ 300 KB）。

## 尚未產出（缺 Sketchfab 下載權杖）

下列 ffishAsia-and-floraZia 模型已在 Sketchfab API 確認授權欄為 **cc0**，但下載需登入帳號
（現僅能透過 Epic Games 註冊；本環境無法自建帳號）。請設定環境變數 `SKETCHFAB_API_TOKEN` 後執行：

```bash
python cad/download_reef_sources.py --out /tmp/reef_sources
blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources --render
```

待下載：海膽、海星、蟹、海參、貽貝、藤壺、蝴蝶魚、神仙魚、條紋魚（stripey）、隆頭魚。

## 重建

```bash
# 珊瑚可在無 Sketchfab token 時自 CC0 HF 鏡像取得（與 Smithsonian／Sketchfab 同一批 NMNH 包）
python cad/download_reef_sources.py --out /tmp/reef_sources --corals-from hf --only \
  acropora_palmata acropora_hyacinthus brain_coral pocillopora porites
blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources --render
```
