"""Build the U3 Ogg Opus loops with ffmpeg/libopus and NumPy, using verified inputs in an external cache."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

TOOLS = Path(__file__).resolve().parent
AUDIO = TOOLS.parent / 'viewer/audio'
RATE = 48000
# Source, start, seconds (including the two-second seam), filter, mix gain.
CUTS = {
    'music/title_drone': [('menu', 36, 50, 'anull', 1)],
    'music/title_goldberg_aria': [('title_goldberg_aria', 0, 147, 'anull', 1)],
    'music/briefing_wtc_prelude1': [('briefing_wtc_prelude1', 0, 161, 'anull', 1)],
    'ambience/deck': [('deck', 4, 34, 'anull', 0.8), ('idle', 8, 34, 'lowpass=f=600', 0.45)],
    'ambience/harbor': [('harbor', 7, 34, 'lowpass=f=350', 1)],
    'ambience/farm': [('farm', 0.15, 8, 'lowpass=f=1800', 1)],
    'ambience/wind': [('wind', 1, 14, 'anull', 1)],
    'ambience/wreck': [('wreck', 1, 32, 'lowpass=f=1500', 1)],
}


def source_file(cache, key, source):
    path = cache / (key + Path(source['url']).suffix)
    if not path.exists():
        with TemporaryDirectory(dir=cache) as temp:
            download = Path(temp) / path.name
            subprocess.run(['curl', '-fLsS', '--retry', '3', source['url'], '-o', download], check=True)
            data = download.read_bytes()
            if hashlib.sha256(data).hexdigest() != source['sha256']:
                raise ValueError(f'Input checksum mismatch: {key}')
            download.replace(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError(f'Input checksum mismatch: {path}')
    return path


def build(name, cuts, sources, cache):
    mix = None
    for key, start, seconds, filters, gain in cuts:
        path = source_file(cache, key, sources[key])
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(start), '-i', path, '-t', str(seconds),
                                       '-af', filters, '-ac', '2', '-ar', str(RATE), '-f', 'f32le', '-'])
        cut = np.frombuffer(raw, dtype='<f4').reshape(-1, 2) * gain
        mix = cut if mix is None else mix + cut
    # Rotate the splice inside the loop. At wrap, adjacent samples come from the same continuous take.
    seam = RATE * 2
    ramp = np.linspace(0, 1, seam, dtype=np.float32)[:, None]
    loop = np.concatenate((mix[seam:-seam], mix[-seam:] * (1 - ramp) + mix[:seam] * ramp))
    pcm = loop.astype('<f4').tobytes()
    cmd = ['ffmpeg', '-hide_banner', '-f', 'f32le', '-ar', str(RATE), '-ac', '2', '-i', '-']
    measured = subprocess.run(cmd + ['-af', 'loudnorm=I=-23:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'],
                              input=pcm, stderr=subprocess.PIPE, check=True).stderr.decode()
    stats = json.loads(measured[measured.rindex('{'):measured.rindex('}') + 1])
    level = -23 - float(stats['input_i'])
    if float(stats['input_tp']) + level > -2:
        raise ValueError(f'Peak headroom insufficient for linear R128 normalization: {name}')
    output = AUDIO / (name + '.opus')
    output.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temp:
        encoded = Path(temp) / output.name
        subprocess.run(cmd + ['-v', 'error', '-af', f'volume={level}dB', '-c:a', 'libopus', '-b:a', '64k',
                              '-vbr', 'constrained', '-fflags', '+bitexact', encoded], input=pcm, check=True)
        if encoded.stat().st_size > 1_500_000:
            raise ValueError(f'{name} exceeds 1.5 MB')
        encoded.replace(output)
    print(name, output.stat().st_size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache', type=Path)
    cache = parser.parse_args().cache
    cache.mkdir(parents=True, exist_ok=True)
    sources = json.loads((TOOLS / 'audio_u3_sources.json').read_text(encoding='utf8'))
    for name, cuts in CUTS.items():
        build(name, cuts, sources, cache)
    sizes = [p.stat().st_size for group in ('ambience', 'music') for p in (AUDIO / group).glob('*.opus')]
    if max(sizes) > 1_500_000 or sum(sizes) > 15_000_000:
        raise ValueError('Audio exceeds the shipping budget')
