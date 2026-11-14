"""Save sonar polar returns as a PGM image. 模拟器扩展，非原厂 SDK 接口。"""
from pathlib import Path
import numpy as np
from qysea.sonar import get_latest_sonar

frame = get_latest_sonar()
if frame is None:
    raise SystemExit('Subscribe and pin sonar in the viewer first.')
image = np.zeros((256, 256), dtype=np.uint8)
for beam, (distance, intensity) in enumerate(zip(frame['distance_m'], frame['intensity'])):
    if distance < frame['range_m']:
        image[min(255, int(distance / frame['range_m'] * 256)), beam] = intensity
Path('sonar.pgm').write_bytes(b'P5\n256 256\n255\n' + image.tobytes())
print('sonar.pgm')
