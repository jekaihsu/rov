"""Build simulator/desktop/THIRD_PARTY_NOTICES.txt from npm, Python and viewer assets.

Lists name, version, licence and source URL for packaged desktop dependencies and
third-party media. Licences outside the project allow-list are reported, not removed.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'simulator'
DESKTOP = SIM / 'desktop'
VIEWER = SIM / 'viewer'
OUTPUT = DESKTOP / 'THIRD_PARTY_NOTICES.txt'
VIEWER_COPY = VIEWER / 'legal' / 'THIRD_PARTY_NOTICES.txt'
CREDITS = VIEWER / 'models' / 'CREDITS.md'
SCAN_SOURCES = SIM / 'tools' / 'scan_materials_sources.json'
PACKAGE_JSON = DESKTOP / 'package.json'
LOCK_JSON = DESKTOP / 'package-lock.json'

# Backend packages copied into the frozen desktop build (build_backend.py).
PYTHON_LICENSES = {
    'numpy': 'BSD-3-Clause',
    'numba': 'BSD-2-Clause',
    'llvmlite': 'BSD-2-Clause AND Apache-2.0 WITH LLVM-exception',
    'websockets': 'BSD-3-Clause',
    'pyinstaller': 'GPL-2.0-or-later with Bootloader exception',
    'jsonschema': 'MIT',
    'jsonschema-specifications': 'MIT',
    'referencing': 'MIT',
    'rpds-py': 'MIT',
    'attrs': 'MIT',
}

# Project allow-list: MIT / BSD / Apache / zlib / CC0 / public domain (AGENTS.md).
STRICT_ALLOWED_PATTERNS = (
    r'\bmit\b',
    r'\bbsd\b',
    r'\bapache\b',
    r'\bzlib\b',
    r'\bcc0\b',
    r'public\s*domain',
    r'creative\s*commons\s*zero',
)


@dataclass
class Notice:
    name: str
    version: str
    license: str
    source: str
    kind: str
    notes: str = ''
    allowed: bool = True


@dataclass
class Report:
    notices: list[Notice] = field(default_factory=list)
    disallowed: list[Notice] = field(default_factory=list)


def _norm_license(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip())


def license_allowed(text: str) -> bool:
    lowered = _norm_license(text).lower()
    if not lowered or lowered in ('?', 'unknown', 'unlicensed'):
        return False
    if 'gpl' in lowered and 'exception' not in lowered and 'with llvm' not in lowered:
        # Plain GPL (without a documented redistributable exception we recognise) is out.
        if re.search(r'\bgpl\b', lowered) and 'mit' not in lowered and 'bsd' not in lowered:
            return False
    for pattern in STRICT_ALLOWED_PATTERNS:
        if re.search(pattern, lowered):
            return True
    # Full BSD text pasted into the License metadata field.
    if 'redistribution and use in source and binary forms' in lowered:
        return True
    return False


def collect_npm(report: Report) -> None:
    package = json.loads(PACKAGE_JSON.read_text(encoding='utf8'))
    packages = json.loads(LOCK_JSON.read_text(encoding='utf8'))['packages']
    declared = {}
    declared.update(package.get('dependencies') or {})
    declared.update(package.get('devDependencies') or {})
    for name in sorted(declared):
        entry = packages[f'node_modules/{name}']
        version = entry['version']
        license_text = entry.get('license', 'unknown')
        source = entry.get('resolved') or f'https://www.npmjs.com/package/{name}'
        notice = Notice(name, version, _norm_license(str(license_text)), source, 'npm')
        notice.allowed = license_allowed(notice.license)
        report.notices.append(notice)
        if not notice.allowed:
            report.disallowed.append(notice)
    # Electron ships Chromium/Node; the npm field is MIT but the runtime bundle is mixed.
    electron = next((n for n in report.notices if n.name == 'electron'), None)
    if electron:
        electron.notes = (
            'npm package field is MIT; the packaged runtime includes Chromium and Node '
            'with additional third-party notices (some LGPL components). Review before Steam ship.'
        )
        # Flag for legal review even though the npm licence string is MIT.
        if electron not in report.disallowed:
            flagged = Notice(
                electron.name + ' (runtime bundle)',
                electron.version,
                'mixed (Chromium/Node; includes non-MIT components)',
                electron.source or 'https://www.electronjs.org/',
                'npm',
                notes=electron.notes,
                allowed=False,
            )
            report.disallowed.append(flagged)


def collect_python(report: Report) -> None:
    versions = {}
    for filename in ('requirements-server.txt', 'requirements-desktop.txt'):
        for line in (SIM / filename).read_text(encoding='utf8').splitlines():
            match = re.fullmatch(r'([\w-]+)([<>=!~].*)', line.strip())
            if match:
                versions[match[1]] = match[2].removeprefix('==')
    for name, license_text in PYTHON_LICENSES.items():
        version = versions.get(name, '(transitive, unpinned)')
        notice = Notice(name, version, license_text, f'https://pypi.org/project/{name}/', 'python')
        if name == 'pyinstaller':
            notice.notes = 'Used to freeze the backend under the bootloader exception.'
        notice.allowed = license_allowed(notice.license)
        # Python interpreter itself is PSF; call it out when we record the runtime.
        report.notices.append(notice)
        if not notice.allowed:
            report.disallowed.append(notice)
    py = Notice(
        'Python',
        '3.11 (desktop build)',
        'PSF License (Python Software Foundation)',
        'https://www.python.org/',
        'python',
        notes='Frozen backend embeds the CPython runtime.',
        allowed=False,
    )
    report.notices.append(py)
    report.disallowed.append(py)


def collect_three(report: Report) -> None:
    three = next(entry for entry in report.notices if entry.kind == 'npm' and entry.name == 'three')
    notice = Notice(
        'three.js',
        three.version,
        three.license,
        'https://github.com/mrdoob/three.js',
        'three.js',
        notes='Vendored under simulator/viewer/vendor/three (Water.js, Sky.js and core).',
        allowed=True,
    )
    report.notices.append(notice)


def collect_fonts(report: Report) -> None:
    report.notices.append(Notice(
        'System UI fonts (Inter / Noto Sans / Barlow Condensed fallbacks)',
        'n/a',
        'system fonts (not redistributed)',
        'OS font stack',
        'fonts',
        notes='Referenced by CSS font-family only; no font files are shipped in the game package.',
        allowed=True,
    ))
    report.notices.append(Notice(
        'DejaVu Sans (build-time rasterisation only)',
        'n/a',
        'Bitstream Vera License',
        'https://dejavu-fonts.github.io/',
        'fonts',
        notes='Used when baking deck monitor glyphs into workboat textures; the font file is not distributed.',
        allowed=False,
    ))
    # Bitstream Vera is not on the allow-list even though glyphs-only is common practice.
    report.disallowed.append(report.notices[-1])


def collect_audio(report: Report) -> None:
    music = [
        ('title_goldberg_aria.opus', 'CC0 1.0',
         'https://archive.org/details/OpenGoldbergVariations'),
        ('briefing_wtc_prelude1.opus', 'CC0 1.0 / Public Domain Mark 1.0',
         'https://archive.org/details/bach-well-tempered-clavier-book-1'),
        ('dive_underwater_theme_ii.opus', 'CC0 1.0',
         'https://opengameart.org/content/underwater-theme-ii'),
        ('dive_underwater_theme.opus', 'CC0 1.0',
         'https://opengameart.org/content/underwater-theme-1'),
        ('results_peer_gynt_morning.opus', 'Public Domain Mark 1.0',
         'https://archive.org/details/musopen-dvd-in-lossless-flac-format'),
        ('tension_peer_gynt_aase.opus', 'Public Domain Mark 1.0',
         'https://archive.org/details/musopen-dvd-in-lossless-flac-format'),
    ]
    sources = json.loads((SIM / 'tools/audio_u3_sources.json').read_text(encoding='utf8'))
    for source in sources.values():
        if source['page'].startswith('https://freesound.org/'):
            music.append((source['title'] + ' — ' + source['author'], source['license'], source['page']))
    for name, license_text, source in music:
        notice = Notice(name, 'asset', license_text, source, 'audio', allowed=license_allowed(license_text))
        report.notices.append(notice)
        if not notice.allowed:
            report.disallowed.append(notice)
    report.notices.append(Notice(
        'Radio voice lines (AI text-to-speech)',
        'asset',
        'original (synthesised; see CREDITS.md)',
        'simulator/viewer/audio/voice/',
        'audio',
        notes='Generated with a hosted TTS API at build time; runtime does not call the network for voice.',
        allowed=True,
    ))
    report.notices.append(Notice(
        'SDL_GameControllerDB (controller-db.json)',
        'retrieved 2026-11-14',
        'zlib',
        'https://github.com/mdqinc/SDL_GameControllerDB',
        'input',
        notes='Compact Linux records; full notice in viewer/input/SDL-LICENSE.txt.',
        allowed=True,
    ))


def collect_models(report: Report) -> None:
    assets = [
        ('worker.glb', 'CC0 1.0', 'https://quaternius.com/packs/animatedmen.html'),
        ('waternormals.jpg', 'MIT',
         'https://github.com/mrdoob/three.js/tree/r160/examples/textures'),
        ('Fish Kit models (models/fish/)', 'CC0 1.0',
         'https://cda-social.github.io/fish/terms.html'),
        ('Poly Haven / ambientCG scan materials (models/scan/)', 'CC0 1.0',
         'https://polyhaven.com/license ; https://docs.ambientcg.com/license/'),
    ]
    for name, license_text, source in assets:
        notice = Notice(name, 'asset', license_text, source, 'models',
                        notes='Provenance in simulator/viewer/models/CREDITS.md',
                        allowed=license_allowed(license_text))
        report.notices.append(notice)
        if not notice.allowed:
            report.disallowed.append(notice)
    if SCAN_SOURCES.is_file():
        report.notices.append(Notice(
            'scan_materials_sources.json',
            '1K downloads',
            'CC0 1.0',
            str(SCAN_SOURCES.relative_to(ROOT)),
            'models',
            notes=f'{len(json.loads(SCAN_SOURCES.read_text(encoding="utf8")))} source files hashed',
            allowed=True,
        ))
    if CREDITS.is_file():
        report.notices.append(Notice(
            'CREDITS.md',
            'document',
            'project documentation',
            str(CREDITS.relative_to(ROOT)),
            'models',
            notes='Authoritative asset provenance; not a software licence grant for vehicle designs.',
            allowed=True,
        ))


def collect_all() -> Report:
    report = Report()
    collect_npm(report)
    steam = Notice(
        'steam_api64.dll', 'bundled with steamworks.js', 'Valve Steamworks SDK licence',
        'https://partner.steamgames.com/doc/sdk/api', 'native runtime', allowed=False,
    )
    report.notices.append(steam)
    report.disallowed.append(steam)
    collect_python(report)
    collect_three(report)
    collect_fonts(report)
    collect_audio(report)
    collect_models(report)
    return report


def render(report: Report) -> str:
    lines = [
        'ROV Solution — Third-Party Notices',
        '',
        'This file is generated by simulator/tools/third_party_notices.py.',
        'It lists third-party software and media included with, or used to build, the desktop package.',
        'Project allow-list: MIT / BSD / Apache / zlib / CC0 / public domain.',
        'Items outside the allow-list are retained here for legal review; the generator does not remove them.',
        '',
    ]
    current = None
    for notice in report.notices:
        if notice.kind != current:
            current = notice.kind
            lines.append(f'=== {current} ===')
            lines.append('')
        flag = '' if notice.allowed else '  [OUTSIDE ALLOW-LIST]'
        lines.append(f'- {notice.name} {notice.version}{flag}')
        lines.append(f'  License: {notice.license}')
        if notice.source:
            lines.append(f'  Source: {notice.source}')
        if notice.notes:
            lines.append(f'  Notes: {notice.notes}')
        lines.append('')
    if report.disallowed:
        lines.append('=== outside allow-list (do not auto-remove) ===')
        lines.append('')
        for notice in report.disallowed:
            lines.append(f'- {notice.name} {notice.version}: {notice.license}')
            if notice.notes:
                lines.append(f'  Notes: {notice.notes}')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def write_notices(path: Path | None = None) -> Report:
    report = collect_all()
    text = render(report)
    target = path or OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf8')
    VIEWER_COPY.parent.mkdir(parents=True, exist_ok=True)
    VIEWER_COPY.write_text(text, encoding='utf8')
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='Fail if the committed notices file is stale')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    report = collect_all()
    text = render(report)
    if args.check:
        existing = args.output.read_text(encoding='utf8') if args.output.is_file() else ''
        viewer = VIEWER_COPY.read_text(encoding='utf8') if VIEWER_COPY.is_file() else ''
        if existing != text or viewer != text:
            print('THIRD_PARTY_NOTICES.txt is stale; run: python simulator/tools/third_party_notices.py')
            return 1
        print(f'OK: {len(report.notices)} notices; {len(report.disallowed)} outside allow-list')
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding='utf8')
    VIEWER_COPY.parent.mkdir(parents=True, exist_ok=True)
    VIEWER_COPY.write_text(text, encoding='utf8')
    print(f'Wrote {args.output} and {VIEWER_COPY} ({len(report.notices)} entries)')
    if report.disallowed:
        print('Outside allow-list:')
        for notice in report.disallowed:
            print(f'  - {notice.name}: {notice.license}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
