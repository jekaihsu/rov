"""Regenerate the evidence inventory from canonical vehicle definitions."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'simulator'))
from qysim.vehicles import HYDRO_FITS, X1_HYDRO_SOURCES, X1_PARAMETERS, X1_TETHER_PARAMETERS


def main():
    lines = ['# X1 暫定參數', '', '參數及來源集中於 `simulator/qysim/vehicles.py`。',
             '實測後只改該表，再執行 `python docs/reference/export_x1_parameters.py`。',
             '目前沒有 measured。official 是廠商宣稱，reseller 是單一經銷商，'
             'published 是公開文獻採為模型預設（不是 X1 實測），estimated 是假設。', '',
             '| 參數 | 值（SI） | 等級 | 依據 |', '|---|---|---|---|']
    for key, item in {**X1_PARAMETERS, **{f"tether.{key}": item
                                        for key, item in X1_TETHER_PARAMETERS.items()}}.items():
        lines.append(f'| {key} | `{item["value"]}` | {item["level"]} | {item["source"]} |')
    for key, source in X1_HYDRO_SOURCES.items():
        value = getattr(HYDRO_FITS['x1'], key)
        lines.append(f'| hydro.{key} | `{value}` | estimated | {source} |')
    Path(__file__).with_name('x1-parameters.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
