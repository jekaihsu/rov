#!/usr/bin/env python3
"""Extract radio dialogue lines from campaign scripts into voice_manifest.json.

Ids are a stable content hash of language + speaker + text so unchanged lines are
skipped on the next synthesize run. Tether-hand radio copy is listed in
tether_lines.json beside this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / 'campaign'
DEFAULT_MANIFEST = ROOT / 'viewer' / 'audio' / 'voice' / 'voice_manifest.json'
TETHER_LINES = Path(__file__).resolve().parent / 'tether_lines.json'
CHARACTERS = Path(__file__).resolve().parent / 'characters.json'


def line_id(language: str, speaker: str, text: str) -> str:
    material = f'{language}\0{speaker}\0{text}'.encode('utf-8')
    return hashlib.sha256(material).hexdigest()[:20]


def load_characters():
    data = json.loads(CHARACTERS.read_text(encoding='utf-8'))
    names = {}
    for key, entry in data.get('characters', {}).items():
        for name in entry.get('names', []):
            names[name] = key
    return names, data.get('fallback', {})


def character_for(speaker: str, name_map: dict) -> str:
    if speaker in name_map:
        return name_map[speaker]
    for name, key in name_map.items():
        if name and name in speaker:
            return key
    return 'unknown'


def resolve_string(strings: dict, key: str | None) -> str | None:
    if not key:
        return None
    value = strings.get(key)
    return value if isinstance(value, str) and value.strip() else None


def extract_campaign(name_map: dict) -> list[dict]:
    lines = []
    for path in sorted(CAMPAIGN.glob('*.json')):
        if path.name == 'schema.json':
            continue
        script = json.loads(path.read_text(encoding='utf-8'))
        chapter = script.get('id') or path.stem
        locales = script.get('strings') or {}
        for language, strings in locales.items():
            if not isinstance(strings, dict):
                continue
            for node in script.get('nodes') or []:
                if node.get('type') != 'dialogue':
                    continue
                text = resolve_string(strings, node.get('text_key'))
                speaker = resolve_string(strings, node.get('speaker_key'))
                if not text or not speaker:
                    continue
                entry = {
                    'id': line_id(language, speaker, text),
                    'chapter': chapter,
                    'node': node.get('id'),
                    'source': f'campaign/{path.name}',
                    'character': character_for(speaker, name_map),
                    'speaker': speaker,
                    'language': language,
                    'text': text,
                }
                lines.append(entry)
    return lines


def extract_tether(name_map: dict) -> list[dict]:
    if not TETHER_LINES.is_file():
        return []
    payload = json.loads(TETHER_LINES.read_text(encoding='utf-8'))
    lines = []
    for item in payload.get('lines') or []:
        language = item['language']
        speaker = item['speaker']
        text = item['text']
        lines.append({
            'id': line_id(language, speaker, text),
            'chapter': item.get('chapter') or 'tether',
            'node': item.get('node') or item.get('code'),
            'source': 'tether/radio',
            'character': character_for(speaker, name_map),
            'speaker': speaker,
            'language': language,
            'text': text,
        })
    return lines


def build_manifest() -> dict:
    name_map, _fallback = load_characters()
    lines = extract_campaign(name_map) + extract_tether(name_map)
    by_id = {}
    for entry in lines:
        by_id[entry['id']] = entry
    ordered = sorted(by_id.values(), key=lambda row: (row['language'], row['chapter'], row['node'] or ''))
    return {
        'version': 1,
        'count': len(ordered),
        'lines': ordered,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-o', '--output', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--chapter', action='append', default=[],
                        help='Only keep these chapter ids (repeatable).')
    parser.add_argument('--language', action='append', default=[],
                        help='Only keep these language codes (repeatable).')
    args = parser.parse_args(argv)
    manifest = build_manifest()
    lines = manifest['lines']
    if args.chapter:
        wanted = set(args.chapter)
        lines = [row for row in lines if row['chapter'] in wanted]
    if args.language:
        wanted = set(args.language)
        lines = [row for row in lines if row['language'] in wanted]
    manifest['lines'] = lines
    manifest['count'] = len(lines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {manifest["count"]} lines to {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
