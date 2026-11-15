"""Cut the site plates of the chapter title card (viewer/brand/chapter_card.js) from the reviewed scene captures.

Usage (from the simulator directory):
  python tools/build_chapter_plates.py              # every scenario a campaign chapter uses
  python tools/build_chapter_plates.py coral_reef   # only the named scenarios

Sources are the in-game overview captures in docs/design/scenes/ (written by tools/browser_scene_review.py) and
docs/design/silt/. Each plate is a portrait 800x900 crop for the card's left half, toned slightly darker so the
paper half stays the brightest area. Writes viewer/brand/plates/<scenario>.jpg (about 30-80 KB each).
The card falls back to the small menu preview and then to a drawing of the chapter symbol, so a missing plate is
never an error. Re-run after the scene captures are retaken.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent / 'docs' / 'design'
OUT = ROOT / 'viewer' / 'brand' / 'plates'
SIZE = (800, 900)
# scenario → (capture under docs/design/, horizontal centre of the crop as a fraction of the capture's width).
PLATES = {
    'tutorial_pool': ('scenes/tutorial_pool-third-after.jpg', 0.46),
    'harbor_inspection': ('scenes/harbor_inspection-third-after.jpg', 0.64),
    'hull_inspection': ('scenes/hull_inspection-third-after.jpg', 0.58),
    'jacket_inspection': ('scenes/jacket_inspection-third-after.jpg', 0.5),
    'coral_reef': ('scenes/coral_reef-third-after.jpg', 0.5),
    'wreck_survey': ('scenes/wreck_survey-third-after.jpg', 0.6),
    'open_water': ('scenes/open_water-third-after.jpg', 0.5),
    'monopile_current': ('scenes/monopile_current-third-after.jpg', 0.5),
    'incident_silt': ('silt/after_third_person.jpg', 0.5),
}


def chapter_scenarios():
    """Scenario keys used by the campaign scripts, in file order without repeats."""
    keys = []
    for path in sorted((ROOT / 'campaign').glob('*.json')):
        if path.name == 'schema.json':
            continue
        key = json.loads(path.read_text(encoding='utf8')).get('scenario')
        if key and key not in keys:
            keys.append(key)
    return keys


def plate(source, centre):
    """Crop a portrait plate around `centre` and tone it."""
    image = Image.open(source).convert('RGB')
    width, height = image.size
    crop_width = round(height * SIZE[0] / SIZE[1])
    left = round(min(max(centre * width - crop_width / 2, 0), width - crop_width))
    image = image.crop((left, 0, left + crop_width, height)).resize(SIZE, Image.LANCZOS)
    image = ImageEnhance.Color(image).enhance(0.9)
    return ImageEnhance.Brightness(image).enhance(0.94)


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    for key in chapter_scenarios():
        if names and key not in names:
            continue
        if key not in PLATES:
            # Drill scenarios reuse another site's plate (PLATE_ALIASES in viewer/brand/chapters.js).
            continue
        source, centre = PLATES[key]
        target = OUT / f'{key}.jpg'
        plate(DOCS / source, centre).save(target, quality=74, optimize=True, progressive=True)
        print('wrote', key, target.stat().st_size)


if __name__ == '__main__':
    main(sys.argv[1:])
