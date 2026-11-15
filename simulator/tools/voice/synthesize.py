#!/usr/bin/env python3
"""Synthesize radio voice clips with OpenAI TTS, then apply radio FX and Opus encode.

Reads OPENAI_API_KEY from the environment only. Never logs or writes the key.
Skips ids that already have an output file so only changed lines are regenerated.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VOICE_DIR = ROOT / 'viewer' / 'audio' / 'voice'
DEFAULT_MANIFEST = VOICE_DIR / 'voice_manifest.json'
CHARACTERS = Path(__file__).resolve().parent / 'characters.json'
API_URL = 'https://api.openai.com/v1/audio/speech'
MAX_FILE_BYTES = 2 * 1024 * 1024


def require_api_key() -> str:
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        print(
            'ERROR: OPENAI_API_KEY is not set.\n'
            'Export your OpenAI API key in the environment, then re-run.\n'
            'The key must not be written into files, logs, or commits.',
            file=sys.stderr,
        )
        sys.exit(2)
    return key


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def character_settings(table: dict, character: str) -> dict:
    entry = table.get('characters', {}).get(character)
    if entry:
        return entry
    return table.get('fallback') or {
        'voice': 'alloy',
        'instructions': 'Speak clearly over a workboat radio.',
    }


def request_speech(api_key: str, model: str, voice: str, instructions: str, text: str,
                   destination: Path) -> None:
    body = json.dumps({
        'model': model,
        'voice': voice,
        'input': text,
        'instructions': instructions,
        'response_format': 'wav',
    }).encode('utf-8')
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            destination.write_bytes(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')[:500]
        raise RuntimeError(f'OpenAI TTS HTTP {error.code}: {detail}') from error


def run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg failed: {result.stderr[-800:]}')


def radio_process(raw_wav: Path, output_opus: Path) -> None:
    """Band-pass, light crush, PTT clicks, loudness −18 LUFS, mono Opus ~32 kbps."""
    with tempfile.TemporaryDirectory(prefix='rov-voice-') as tmp:
        tmp_path = Path(tmp)
        click = tmp_path / 'click.wav'
        mixed = tmp_path / 'mixed.wav'
        run_ffmpeg([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi',
            '-i', 'anoisesrc=color=white:amplitude=0.35:duration=0.045',
            '-af', 'afade=t=out:st=0.02:d=0.025',
            str(click),
        ])
        # Concatenate click + processed voice + click, then loudnorm and Opus.
        filter_complex = (
            '[0:a]aformat=sample_fmts=fltp:channel_layouts=mono,'
            'highpass=f=300,lowpass=f=3200,'
            'acrusher=bits=10:mode=log:aa=1:samples=128,'
            'volume=1.35[voice];'
            '[1:a]aformat=sample_fmts=fltp:channel_layouts=mono,volume=0.55[c0];'
            '[2:a]aformat=sample_fmts=fltp:channel_layouts=mono,volume=0.45[c1];'
            '[c0][voice][c1]concat=n=3:v=0:a=1,'
            'loudnorm=I=-18:TP=-1.5:LRA=11:linear=true[out]'
        )
        run_ffmpeg([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-i', str(raw_wav), '-i', str(click), '-i', str(click),
            '-filter_complex', filter_complex,
            '-map', '[out]', '-ar', '48000', '-ac', '1',
            str(mixed),
        ])
        output_opus.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-i', str(mixed),
            '-c:a', 'libopus', '-b:a', '32k', '-ac', '1', '-ar', '48000',
            '-application', 'voip',
            str(output_opus),
        ])


def clip_path(language: str, line_id: str) -> Path:
    return VOICE_DIR / language / f'{line_id}.opus'


def write_index(languages: set[str]) -> None:
    index = {}
    for language in sorted(languages):
        folder = VOICE_DIR / language
        if not folder.is_dir():
            continue
        index[language] = sorted(path.stem for path in folder.glob('*.opus'))
    (VOICE_DIR / 'index.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--chapter', action='append', default=[])
    parser.add_argument('--language', action='append', default=['zh-TW'])
    parser.add_argument('--force', action='store_true', help='Regenerate even if the file exists.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)

    api_key = None if args.dry_run else require_api_key()
    table = load_json(CHARACTERS)
    model = table.get('model') or 'gpt-4o-mini-tts'
    manifest = load_json(args.manifest)
    lines = manifest.get('lines') or []
    if args.chapter:
        wanted = set(args.chapter)
        lines = [row for row in lines if row['chapter'] in wanted]
    if args.language:
        wanted = set(args.language)
        lines = [row for row in lines if row['language'] in wanted]

    created = 0
    skipped = 0
    languages = set()
    for row in lines:
        language = row['language']
        languages.add(language)
        out = clip_path(language, row['id'])
        if out.is_file() and not args.force:
            skipped += 1
            continue
        settings = character_settings(table, row.get('character') or 'unknown')
        print(f"Synthesize {row['id']} [{row['speaker']}] {row['text'][:40]}…")
        if args.dry_run:
            created += 1
            continue
        with tempfile.TemporaryDirectory(prefix='rov-tts-') as tmp:
            raw = Path(tmp) / 'raw.wav'
            request_speech(
                api_key, model, settings['voice'], settings['instructions'], row['text'], raw)
            radio_process(raw, out)
        size = out.stat().st_size
        if size > MAX_FILE_BYTES:
            out.unlink(missing_ok=True)
            raise RuntimeError(f'{out} is {size} bytes (limit {MAX_FILE_BYTES})')
        created += 1

    if not args.dry_run:
        write_index(languages | {path.name for path in VOICE_DIR.iterdir() if path.is_dir()})
    total = 0
    for language in sorted(languages):
        folder = VOICE_DIR / language
        for path in folder.glob('*.opus') if folder.is_dir() else []:
            total += path.stat().st_size
    print(f'Done. created={created} skipped={skipped} opus_bytes={total}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
