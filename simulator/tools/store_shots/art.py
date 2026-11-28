"""Typeset store plates, render the maritime symbols and assemble the proof sheet."""
import csv
import io
import json
import os
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STORE = ROOT / 'docs/store/steam'
ASSETS = STORE / 'assets'
ART = ASSETS / 'capsules'
ICONS = ASSETS / 'achievements'
CLIENT = ASSETS / 'client'
FONT = os.environ.get('ROV_STORE_FONT', '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf')
INK = '#06121c'
WHITE = '#eef3f0'
ORANGE = '#ff7a2f'
NS = '{http://www.w3.org/2000/svg}'


def font(size):
    return ImageFont.truetype(FONT, size)


def title(width):
    """Ink-tight transparent title. Scale letterforms and rule as one unit."""
    face = font(240)
    box = face.getbbox('ROV Solution')
    height = box[3] - box[1]
    word = Image.new('RGBA', (box[2] - box[0] + 62, height + 4))
    pen = ImageDraw.Draw(word)
    pen.rectangle((0, 4, 18, height), fill=ORANGE)
    pen.text((62-box[0], -box[1]), 'ROV Solution', fill=WHITE, font=face)
    return word.resize((width, round(word.height * width / word.width)), Image.Resampling.LANCZOS)


def plate(name, spec, scale=1):
    w, h, source, center_x, center_y = spec
    w *= scale
    h *= scale
    img = Image.open(ASSETS / 'shots' / f'{source}.jpg')
    label = title(round(w * (0.9 if name.startswith('small') else 0.81)))
    margin = round(w * 0.05)
    band = 0 if name == 'page-background' else label.height + 2 * min(margin, round(h * 0.068))
    crop = ImageOps.fit(img, (w, h-band), Image.Resampling.LANCZOS, centering=(center_x, center_y))
    canvas = Image.new('RGB', (w, h), INK)
    canvas.paste(crop)
    if band:
        canvas.paste(label, (margin, h-band+(band-label.height)//2), label)
    canvas.save(ART / f'{name}.jpg', quality=94, optimize=True)


def rasterize(svg):
    render = subprocess.run(['inkscape', '--pipe', '--export-type=png', '--export-filename=-'],
                            input=svg, stdout=subprocess.PIPE, check=True)
    return Image.open(io.BytesIO(render.stdout))


def client_icons():
    """Rasterize the same Model R silhouette shown by the in-game hangar."""
    source = """import {fleetSymbol} from './simulator/viewer/brand/marks.js';
      process.stdout.write(fleetSymbol('x1', {size:512, sized:true, ink:'#eef3f0', accent:'#ff7a2f'}));"""
    svg = subprocess.run(['node', '--input-type=module', '-e', source], cwd=ROOT,
                         capture_output=True, check=True).stdout
    symbol = rasterize(svg).convert('RGBA')
    background = Image.new('RGB', symbol.size, INK)
    background.paste(symbol, mask=symbol.getchannel('A'))
    background.save(CLIENT / 'shortcut.png', optimize=True)
    background.resize((184, 184), Image.Resampling.LANCZOS).save(CLIENT / 'app.jpg', quality=95)


def badges():
    atlas = ET.parse(HERE / 'symbols.svg').getroot()
    events = json.loads((ROOT / 'simulator/desktop/steam/achievements.json').read_text(encoding='utf-8'))
    symbols = {symbol.attrib['id']: symbol for symbol in atlas}
    assert set(symbols) == {event['event'] for event in events}
    for event in events:
        svg = ET.fromstring(f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 64 64">
          <rect width="64" height="64" fill="{INK}"/>
          <rect x="4" y="4" width="56" height="56" rx="8" fill="#102836" stroke="#456272"/>
          <g fill="none" stroke="{WHITE}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>''')
        svg.find(NS + 'g').append(symbols[event['event']])
        color = rasterize(ET.tostring(svg)).convert('RGB')
        color.save(ICONS / f"{event['api']}.png", optimize=True)
        ImageOps.grayscale(color).save(ICONS / f"{event['api']}-locked.png", optimize=True)


def sheet():
    shots = sorted((ASSETS / 'shots').glob('*.jpg'))
    with (STORE / 'listing/captions.tsv').open(encoding='utf-8', newline='') as file:
        captions = list(csv.DictReader(file, delimiter='\t'))
    assert [shot.stem for shot in shots] == [row['shot'] for row in captions]
    groups = [
        ('In-game screenshots', shots),
        ('Store and library artwork', sorted(ART.iterdir())),
        ('Steam client icons', sorted(CLIENT.iterdir())),
        ('Achievement icons', sorted(ICONS.iterdir())),
    ]
    width, height, columns = 264, 163, 4
    sections = sum(52 + height * ((len(paths)+columns-1)//columns) for _, paths in groups)
    proof = Image.new('RGB', (width*columns, sections+90), INK)
    pen = ImageDraw.Draw(proof)
    face = font(13)
    top = 0
    for label, paths in groups:
        pen.rectangle((8, top+11, 11, top+37), fill=ORANGE)
        pen.text((21, top+8), f'{label}  /  {len(paths)}', fill=WHITE, font=font(22))
        top += 52
        for i, path in enumerate(paths):
            img = Image.open(path).convert('RGBA')
            if path in shots:
                assert img.size == (1920, 1080), path
            x, y = width*(i % columns), top+height*(i // columns)
            img.thumbnail((width-14, height-30), Image.Resampling.LANCZOS)
            proof.paste(img, (x+(width-img.width)//2, y+(height-30-img.height)//2), img)
            pen.text((x+8, y+height-25), path.stem, fill=WHITE, font=face)
        top += height*((len(paths)+columns-1)//columns)
    pen.text((12, top+10), 'Listing and screenshot captions', fill=WHITE, font=font(20))
    pen.text((12, top+50), 'listing/   zh-Hant.md   /   en.md   /   zh-Hans.md   /   ja.md   /   captions.tsv',
             fill=WHITE, font=face)
    proof.save(ASSETS / 'contact-sheet.jpg', quality=88, optimize=True)
    for path in [ASSETS / 'contact-sheet.jpg', *(p for _, paths in groups for p in paths)]:
        if path.stat().st_size > 2_000_000:
            raise ValueError(f'Image exceeds 2 MB: {path}')


def main():
    ART.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)
    CLIENT.mkdir(parents=True, exist_ok=True)
    client_icons()
    badges()
    for name, spec in json.loads((HERE / 'art.json').read_text(encoding='utf-8')).items():
        plate(name, spec)
        if name in ('header', 'small', 'main', 'vertical'):
            plate(name+'-2x', spec, 2)
    (ART / 'library-header.jpg').write_bytes((ART / 'header-2x.jpg').read_bytes())
    hero = Image.open(ROOT / 'output/store/library-hero/hero.png')
    assert hero.size == (3840, 1240)
    hero.convert('RGB').save(ART / 'library-hero.jpg', quality=92, optimize=True)
    title(1280).save(ART / 'library-logo.png')
    sheet()
    print(f'{len(list(ART.iterdir()))} store/library images, {len(list(ICONS.iterdir()))} achievement icons, '
          '2 client icons, contact sheet')


if __name__ == '__main__':
    main()
