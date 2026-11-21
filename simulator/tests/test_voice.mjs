// Radio voice: stable content hashes, manifest extract parity, missing-clip fallback.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash as nodeHash} from 'node:crypto';
import {readFileSync, existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createHash} from '../viewer/audio/voice_hash.js';
import {
  lineId, resolveClip, clipUrl, _resetVoiceForTests
} from '../viewer/audio/voice.js';

import {mkdtempSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const EXTRACT = fileURLToPath(new URL('../tools/voice/extract_lines.py', import.meta.url));
const SHIPPED_MANIFEST = fileURLToPath(new URL('../viewer/audio/voice/voice_manifest.json', import.meta.url));

function pythonLineId(language, speaker, text) {
  const material = `${language}\0${speaker}\0${text}`;
  return nodeHash('sha256').update(material, 'utf8').digest('hex').slice(0, 20);
}

test('voice_hash matches Node crypto SHA-256', () => {
  const sample = 'zh-TW\0林岑\0很好。慢慢來，先往前。';
  assert.equal(createHash(sample), nodeHash('sha256').update(sample, 'utf8').digest('hex'));
});

test('line ids are stable across JS and the extract tool algorithm', () => {
  const language = 'zh-TW';
  const speaker = '林岑';
  const text = '今天池裡認識搭檔。先檢查。';
  assert.equal(lineId(language, speaker, text), pythonLineId(language, speaker, text));
  assert.equal(lineId(language, speaker, text), lineId(language, speaker, text));
  assert.notEqual(lineId(language, speaker, text), lineId(language, speaker, text + '。'));
});

test('extract_lines writes a manifest with prologue zh-TW dialogue hashes', () => {
  const dir = mkdtempSync(join(tmpdir(), 'rov-voice-'));
  const manifestPath = join(dir, 'voice_manifest.json');
  try {
    const result = spawnSync(
      'python3',
      [EXTRACT, '-o', manifestPath, '--chapter', 'prologue', '--language', 'zh-TW'],
      {cwd: ROOT, encoding: 'utf8'},
    );
    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.equal(existsSync(manifestPath), true);
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    assert.ok(manifest.count >= 7, manifest.count);
    for (const row of manifest.lines) {
      assert.equal(row.language, 'zh-TW');
      assert.equal(row.chapter, 'prologue');
      assert.equal(row.id, pythonLineId(row.language, row.speaker, row.text));
      assert.ok(row.speaker);
      assert.ok(row.text);
    }
    const speakers = new Set(manifest.lines.map(row => row.speaker));
    assert.ok(speakers.has('林岑'));
    assert.ok(speakers.has('周楷'));
    assert.ok(speakers.has('方晴'));
    assert.ok(speakers.has('馬力'));
    assert.equal(speakers.has('阿禾'), false);
  } finally {
    rmSync(dir, {recursive: true, force: true});
  }
});

test('shipped voice_manifest lists stable ids when present', () => {
  if (!existsSync(SHIPPED_MANIFEST)) return;
  const manifest = JSON.parse(readFileSync(SHIPPED_MANIFEST, 'utf8'));
  for (const row of manifest.lines.slice(0, 20)) {
    assert.equal(row.id, pythonLineId(row.language, row.speaker, row.text));
  }
});

test('resolveClip falls back when the id is absent from the index', () => {
  _resetVoiceForTests();
  const missing = resolveClip({ 'zh-TW': [] }, 'zh-TW', '林岑', '沒有這句。');
  assert.equal(missing.missing, true);
  assert.equal(missing.url, null);
  assert.ok(missing.id);
  const id = lineId('zh-TW', '林岑', '有這句。');
  const found = resolveClip({ 'zh-TW': [id] }, 'zh-TW', '林岑', '有這句。');
  assert.equal(found.missing, false);
  assert.equal(found.url, clipUrl('zh-TW', id));
});

test('clip URLs stay under the language directory', () => {
  assert.match(clipUrl('zh-TW', 'abc'), /voice\/zh-TW\/abc\.opus$/);
  assert.match(clipUrl('en', 'xyz'), /voice\/en\/xyz\.opus$/);
});

test('flight fallback selects a local matching voice and honours mixer mute and stop', async t => {
  const {installVoice} = await import('../viewer/audio/voice.js');
  const {getFidelity} = await import('../viewer/fidelity.js');
  _resetVoiceForTests();
  const local = {lang: 'zh-TW', localService: true};
  const spoken = [];
  let cancelled = 0;
  const synth = {
    getVoices: () => [{lang: 'zh-TW', localService: false}, local],
    speak: line => spoken.push(line),
    cancel: () => { cancelled++; }
  };
  const globals = {document: {hidden: false}, speechSynthesis: synth,
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } }};
  for (const [name, value] of Object.entries(globals)) {
    const original = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {value, configurable: true});
    t.after(() => {
      if (original) Object.defineProperty(globalThis, name, original);
      else delete globalThis[name];
    });
  }
  t.mock.method(globalThis, 'fetch', async () => ({ok: true, json: async () => ({})}));
  const settings = {master: 0.5, voice: 0.8, mute: false};
  const voice = installVoice({engine: {settings, ctx: {state: 'running'}, isPaused: () => false}});
  const call = {speaker: '林岑', text: '向潮－指揮，機身碰到了。先穩住。', language: 'zh-TW', localRate: 0.92};
  const fidelity = getFidelity();
  try {
    assert.equal(fidelity.get('osVoice'), false);
    assert.equal((await voice.playLine(call)).played, false);
    assert.equal(spoken.length, 0);
    fidelity.set('osVoice', true);
    assert.ok((await voice.playLine(call)).local);
    assert.equal(spoken[0].voice, local);
    assert.equal(spoken[0].volume, 0.4);
    voice.stop();
    assert.equal(cancelled, 1);
    settings.mute = true;
    assert.equal((await voice.playLine(call)).played, false);
    assert.equal(spoken.length, 1);
  } finally {
    fidelity.set('osVoice', false);
    voice.stop();
    _resetVoiceForTests();
  }
});
